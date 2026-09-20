#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.

"""The Bot API HTML style, read and written.

Reading runs in three passes: `Parser` turns the markup into a flat list of tokens, `_pair`
decides which start tag each end tag closes, and `_build` walks the tokens once to produce
the message and its entities together. Every offset is therefore known when the entity is
constructed, and a tag that pairs with nothing survives in the message text as written.

The tags themselves live in `entities.py`, once. https://core.telegram.org/bots/api#html-style
"""

from __future__ import annotations as _annotations

import html
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from typing import TypeAlias

import pyrogram
from pyrogram import raw, types
from pyrogram.errors import PeerIdInvalid

from . import utils
from .entities import EntitySpec, Insertion, InsertionKind, spec_for_tag, spec_for_type


@dataclass(frozen=True, slots=True)
class TextToken:
    """Text between tags, with its character references already resolved."""

    text: str


@dataclass(frozen=True, slots=True)
class StartToken:
    """A start tag. `spec` is `None` for a tag that opens no entity."""

    tag: str
    attributes: dict[str, str]
    source: str
    spec: EntitySpec | None


@dataclass(frozen=True, slots=True)
class EndToken:
    tag: str
    source: str


TokenType: TypeAlias = TextToken | StartToken | EndToken


@dataclass(frozen=True, slots=True)
class ParsedMarkup:
    message: str
    entities: list[raw.base.MessageEntity]


class Parser(HTMLParser):
    """Markup in, tokens out. Nothing here knows about offsets or entities."""

    def __init__(self) -> None:
        # `convert_charrefs` resolves `&amp;` before `handle_data` sees it. Unescaping a
        #  second time there turned `&amp;lt;` into `<` instead of `&lt;`.
        super().__init__(convert_charrefs=True)

        self.tokens: list[TokenType] = []

        # One entry per open `code` tag, saying whether it was folded into a `pre`.
        self.code_folded: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]], /) -> None:
        # A valueless attribute such as the `expandable` of a blockquote parses as `None`.
        attributes = {name: value or "" for name, value in attrs}

        if tag == "code":
            folded = self._fold_into_pre(attributes)
            self.code_folded.append(folded)

            if folded:
                return

        self.tokens.append(
            StartToken(
                tag=tag,
                attributes=attributes,
                source=self.get_starttag_text() or "",
                spec=spec_for_tag(tag, attributes=attributes),
            )
        )

    def _fold_into_pre(self, attributes: dict[str, str]) -> bool:
        """Whether this `code` tag is the language of the `pre` it opens, and was folded in.

        `<pre><code class="language-python">` is one `pre` entity carrying a language, and is
        the only way the Bot API spells one. The two tags have to be adjacent, as they are in
        everything Telegram writes. https://core.telegram.org/bots/api#html-style
        """
        previous = self.tokens[-1] if self.tokens else None

        if not isinstance(previous, StartToken) or previous.tag != "pre":
            return False

        language = attributes.get("class", "").removeprefix("language-")
        self.tokens[-1] = replace(
            previous,
            attributes={**previous.attributes, "language": language},
        )

        return True

    def handle_endtag(self, tag: str, /) -> None:
        if tag == "code" and self.code_folded and self.code_folded.pop():
            return

        self.tokens.append(
            EndToken(
                tag=tag,
                source=f"</{tag}>",
            )
        )

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]], /) -> None:
        del tag, attrs

        # No entity tag is self-closing, so `<br/>` is text and stays text.
        self.tokens.append(TextToken(text=self.get_starttag_text() or ""))

    def handle_data(self, data: str) -> None:
        self.tokens.append(TextToken(text=data))

    def handle_comment(self, data: str) -> None:
        self.tokens.append(TextToken(text=f"<!--{data}-->"))

    def handle_decl(self, decl: str) -> None:
        self.tokens.append(TextToken(text=f"<!{decl}>"))

    def handle_pi(self, data: str) -> None:
        self.tokens.append(TextToken(text=f"<?{data}>"))

    def unknown_decl(self, data: str) -> None:
        self.tokens.append(TextToken(text=f"<![{data}]>"))


def _pair(tokens: list[TokenType]) -> dict[int, int]:
    """Which end token closes which start token, by index into `tokens`.

    One stack per tag name, so `<b><i>x</b></i>` still yields both entities rather than
    discarding the pair that crosses.
    """
    open_by_tag: dict[str, list[int]] = {}
    pairs: dict[int, int] = {}

    for index, token in enumerate(tokens):
        if isinstance(token, StartToken) and token.spec is not None:
            open_by_tag.setdefault(token.tag, []).append(index)

        elif isinstance(token, EndToken):
            opened = open_by_tag.get(token.tag)

            if opened:
                pairs[opened.pop()] = index

    return pairs


def _build(tokens: list[TokenType]) -> ParsedMarkup:
    """The message text and its entities, in one left-to-right sweep."""
    pairs = _pair(tokens)
    closing: dict[int, raw.base.MessageEntity] = {}

    parts: list[str] = []
    offset: int = 0
    entities: list[raw.base.MessageEntity] = []

    for index, token in enumerate(tokens):
        if isinstance(token, EndToken):
            entity = closing.pop(index, None)

            if entity is None:
                parts.append(token.source)
                offset += len(token.source)
                continue

            entity.length = offset - entity.offset
            continue

        if isinstance(token, StartToken):
            end_index = pairs.get(index)

            if end_index is None or token.spec is None:
                parts.append(token.source)
                offset += len(token.source)
                continue

            entity = token.spec.raw_type(
                offset=offset,
                length=0,
                **token.spec.raw_arguments(token.attributes),
            )
            closing[end_index] = entity
            entities.append(entity)
            continue

        parts.append(token.text)
        offset += len(token.text)

    return ParsedMarkup(
        message="".join(parts),
        entities=entities,
    )


class HTML:
    def __init__(self, client: pyrogram.Client | None):
        self.client = client

    async def parse(self, text: str) -> dict:
        parser = Parser()
        parser.feed(utils.add_surrogates(text))
        parser.close()

        parsed = _build(parser.tokens)
        entities = []

        for entity in parsed.entities:
            if not entity.length:
                continue

            if isinstance(entity, raw.types.InputMessageEntityMentionName) and self.client:
                try:
                    entity.user_id = await self.client.resolve_peer(entity.user_id)

                except PeerIdInvalid:
                    continue

            entities.append(entity)

        return {
            "message": utils.remove_surrogates(parsed.message),
            "entities": sorted(entities, key=lambda entity: entity.offset) or None,
        }

    @staticmethod
    def unparse(text: str, *, entities: list[types.MessageEntity]) -> str:
        ordered = sorted(entities, key=lambda entity: (entity.offset, -entity.length))
        insertions: list[Insertion] = []

        def nest(entity_index: int) -> int:
            """Write one entity and every entity inside it, innermost tag last.

            Returns how many entities of `ordered` that consumed, so the caller advances
            past the whole nest without sorting the insertions afterwards.
            """
            entity = ordered[entity_index]
            spec = spec_for_type(entity.type)

            if spec is None:
                return 1

            end: int = entity.offset + entity.length

            insertions.append(
                Insertion(
                    text=spec.html_open(entity),
                    offset=entity.offset,
                    kind=InsertionKind.OPEN,
                )
            )

            inner_index: int = entity_index + 1

            while inner_index < len(ordered) and ordered[inner_index].offset < end:
                inner_index += nest(inner_index)

            insertions.append(
                Insertion(
                    text=spec.html_close(entity),
                    offset=end,
                    kind=InsertionKind.CLOSE,
                )
            )

            return inner_index - entity_index

        index: int = 0

        while index < len(ordered):
            index += nest(index)

        text = utils.add_surrogates(text)

        # `nest` appends nested runs in document order, but an entity that CROSSES another
        #  (starts inside it, ends outside) lands its closing tag out of order, and the sweep
        #  below would then re-emit the text between the two ends. A stable sort keeps the
        #  nested order at equal offsets and puts a crossing close where it belongs; the
        #  crossed tags it writes are exactly what `_pair`'s per-tag stacks read back.
        parts: list[str] = []
        written: int = 0

        for insertion in sorted(insertions, key=lambda item: item.offset):
            parts.append(html.escape(text[written : insertion.offset]))
            parts.append(insertion.text)
            written = insertion.offset

        parts.append(html.escape(text[written:]))

        return utils.remove_surrogates("".join(parts))
