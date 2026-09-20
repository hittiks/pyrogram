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

"""The Telegram Markdown style, read and written.

Reading rewrites the markup into the HTML style and hands it to `HTML.parse`, which owns
the offsets. Blockquotes go first, because they are decided a line at a time; the rest is
one scan for delimiters, a pass deciding which of them pair, and a rebuild. A delimiter
that pairs with nothing stays in the message as the character it is.

The delimiters themselves live in `entities.py`, once.
"""

from __future__ import annotations as _annotations

import html
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Final

import pyrogram
from pyrogram import types
from pyrogram.enums import MessageEntityType

from . import utils
from .entities import (
    BLOCKQUOTE_EXPANDABLE_END,
    BLOCKQUOTE_EXPANDABLE_MARKER,
    BLOCKQUOTE_MARKER,
    CUSTOM_EMOJI,
    DATE_TIME,
    FIXED_WIDTH_DELIMITERS,
    MARKDOWN_DELIMITERS,
    PRE,
    TEXT_LINK,
    EntitySpec,
    Insertion,
    InsertionKind,
    spec_for_delimiter,
    spec_for_type,
    valid_date_time_format,
)
from .html import HTML

_DELIMITER_PATTERN: Final[str] = "|".join(re.escape(delimiter) for delimiter in MARKDOWN_DELIMITERS)

MARKDOWN_RE: Final[re.Pattern[str]] = re.compile(
    r"\\(?P<escaped>[\s\S])"
    rf"|(?P<delimiter>{_DELIMITER_PATTERN})"
    r"|(?P<image>!?)\[(?P<label>.+?)\]\((?P<url>.+?)\)"
)

# The characters that read as a delimiter when they stand in a run: `**`, `__`, `--`,
#  `~~` and `||` are all doubled characters, so a single one is always literal text.
_PAIRABLE_CHARS: Final[str] = "*_~|-"

# What `unparse` escapes inside a text chunk: the characters that are markup on their
#  own (`\`, a backtick, `[`, `]`), and any run of a pairable character.
_CHUNK_ESCAPE_RE: Final[re.Pattern[str]] = re.compile(r"[\\`\[\]]|([*_~|-])\1+")

_QUOTE_AFTER_NEWLINE_RE: Final[re.Pattern[str]] = re.compile(r"(?<=\n)>")

# The line prefixes `_wrap_blockquotes` reads a marker after: nothing, or the `**` a
#  bold delimiter just wrote, which a following `>` would turn into `**>`.
_MARKER_PRONE_PREFIXES: Final[frozenset[str]] = frozenset({"", "**"})


def _escape_each(match: re.Match[str]) -> str:
    return "".join(f"\\{character}" for character in match.group(0))


def _escape_chunk(chunk: str, *, line_prefix: str, following: str) -> str:
    """The chunk with everything `parse` would read back as markup escaped.

    Single pairable characters stay as typed, so `snake_case` and `5 > 3` survive
    unescaped; what gets escaped is what would pair, open a link, or start a quote.
    """
    escaped = _CHUNK_ESCAPE_RE.sub(_escape_each, chunk)
    escaped = _QUOTE_AFTER_NEWLINE_RE.sub(r"\\>", escaped)

    if line_prefix in _MARKER_PRONE_PREFIXES and escaped.startswith(">"):
        escaped = f"\\{escaped}"

    # A single trailing pairable character merges with the delimiter written right
    #  after it: `a*` before a `**` close becomes `***`, and the pair then closes one
    #  character early.
    trailing = chunk[-1:]

    if (
        trailing
        and trailing in _PAIRABLE_CHARS
        and trailing == following[:1]
        and not escaped.endswith(f"\\{trailing}")
    ):
        escaped = f"{escaped[:-1]}\\{trailing}"

    return escaped


@dataclass(frozen=True, slots=True, order=True)
class _PlacedInsertion:
    """One insertion with its place in the document order.

    Offset first; at one offset the `InsertionKind` rank applies; a longer entity
    opens earlier and closes later than a shorter one, so the delimiters nest; and
    among equals the order Telegram sent the entities in decides, reversed for the
    closes because what opened last must close first.
    """

    offset: int
    rank: InsertionKind
    nesting: int
    arrival: int
    insertion: Insertion = field(compare=False)


def _place(insertion: Insertion, *, length: int, index: int) -> _PlacedInsertion:
    if insertion.kind is InsertionKind.CLOSE:
        return _PlacedInsertion(
            offset=insertion.offset,
            rank=insertion.kind,
            nesting=length,
            arrival=-index,
            insertion=insertion,
        )

    return _PlacedInsertion(
        offset=insertion.offset,
        rank=insertion.kind,
        nesting=-length,
        arrival=index,
        insertion=insertion,
    )


def _advance_line_prefix(prefix: str, *, piece: str) -> str:
    """What the current output line starts with, capped at what the checks compare to."""
    combined = f"{prefix}{piece}"
    newline = combined.rfind("\n")

    if newline != -1:
        combined = combined[newline + 1 :]

    return combined[:3]


# Splitting on the capture keeps every `\X` pair as its own odd-indexed piece.
_BACKSLASH_PAIR_RE: Final[re.Pattern[str]] = re.compile(r"(\\.)")


def _escape(line: str, *, strict: bool) -> str:
    if not strict:
        return line

    # `html.escape` must not reach inside a backslash pair: `\>` would become `\&gt;`,
    #  and the escaped branch of `MARKDOWN_RE` then reads `\&` instead of `\>`, leaving
    #  a literal `gt;` in the message.
    pieces = _BACKSLASH_PAIR_RE.split(line)

    return "".join(piece if index % 2 else html.escape(piece) for index, piece in enumerate(pieces))


def _strip_marker(line: str, *, marker: str) -> str:
    if not line.startswith(marker):
        return line

    return line[len(marker) :].removeprefix(" ")


def _blockquote(lines: list[str], *, expandable: bool) -> str:
    attribute = " expandable" if expandable else ""

    return f"<blockquote{attribute}>{chr(10).join(lines)}</blockquote>"


def _wrap_blockquotes(text: str, *, strict: bool) -> str:
    """Every quoted run becomes one `<blockquote>`, and in strict mode the text is escaped.

    `split` rather than `splitlines`, which drops a trailing newline and shifts every offset
    after it. Escaping happens here because the markers are read before `>` becomes `&gt;`.
    """
    lines: list[str] = []
    quoted: list[str] = []
    inside: bool = False
    expandable: bool = False

    for raw_line in text.split("\n"):
        if inside:
            # A plain quote ends at the first line that does not carry the marker; an
            #  expandable one runs until its end marker, whatever the lines look like.
            if not expandable and not raw_line.startswith(BLOCKQUOTE_MARKER):
                lines.append(_blockquote(quoted, expandable=False))
                lines.append(_escape(raw_line, strict=strict))

                quoted = []
                inside = False
                continue

            content = _strip_marker(raw_line, marker=BLOCKQUOTE_MARKER)

        elif raw_line.startswith(BLOCKQUOTE_EXPANDABLE_MARKER):
            inside = True
            expandable = True
            content = _strip_marker(raw_line, marker=BLOCKQUOTE_EXPANDABLE_MARKER)

        elif raw_line.startswith(BLOCKQUOTE_MARKER):
            inside = True
            expandable = False
            content = _strip_marker(raw_line, marker=BLOCKQUOTE_MARKER)

        else:
            lines.append(_escape(raw_line, strict=strict))
            continue

        # The opening line may carry the end marker too, which is what `**> quote||` is.
        if expandable and content.endswith(BLOCKQUOTE_EXPANDABLE_END):
            quoted.append(
                _escape(
                    content[: -len(BLOCKQUOTE_EXPANDABLE_END)],
                    strict=strict,
                )
            )
            lines.append(_blockquote(quoted, expandable=True))

            quoted = []
            inside = False
            continue

        quoted.append(_escape(content, strict=strict))

    if inside:
        lines.append(_blockquote(quoted, expandable=expandable))

    return "\n".join(lines)


def _pair(matches: list[re.Match[str]]) -> dict[int, int]:
    """Which delimiters pair. Anything inside a fixed-width run is left alone."""
    closes: dict[int, int] = {}
    opened: dict[str, int] = {}
    fixed_width: str | None = None

    for index, match in enumerate(matches):
        delimiter = match.group("delimiter")

        if delimiter is None:
            continue

        if fixed_width is not None:
            if delimiter == fixed_width:
                closes[opened.pop(delimiter)] = index
                fixed_width = None

            continue

        if delimiter in opened:
            closes[opened.pop(delimiter)] = index
            continue

        opened[delimiter] = index

        if delimiter in FIXED_WIDTH_DELIMITERS:
            fixed_width = delimiter

    return closes


def _link_markup(label: str, *, url: str, image: bool) -> str | None:
    """The HTML a `[label](url)` pair becomes, or `None` where it is not markup at all."""
    if not image:
        entity = types.MessageEntity(
            type=MessageEntityType.TEXT_LINK,
            offset=0,
            length=0,
            url=url,
        )

        return f"{TEXT_LINK.html_open(entity)}{label}{TEXT_LINK.html_close(entity)}"

    parsed = urllib.parse.urlparse(url)
    parameters = urllib.parse.parse_qs(parsed.query)

    # Validated before any tag is written: a link that fails here has to survive as the
    #  text the sender typed, not as an invented literal tag.
    if parsed.netloc == "emoji":
        emoji_id: str = parameters.get("id", [""])[0]

        if not emoji_id.isdigit():
            return None

        entity = types.MessageEntity(
            type=MessageEntityType.CUSTOM_EMOJI,
            offset=0,
            length=0,
            custom_emoji_id=emoji_id,
        )

        return f"{CUSTOM_EMOJI.html_open(entity)}{label}{CUSTOM_EMOJI.html_close(entity)}"

    if parsed.netloc == "time":
        unix_time: str = parameters.get("unix", [""])[0]
        date_time_format: str = parameters.get("format", [""])[0]

        if not unix_time.isdigit() or not valid_date_time_format(date_time_format):
            return None

        entity = types.MessageEntity(
            type=MessageEntityType.DATE_TIME,
            offset=0,
            length=0,
            unix_time=unix_time,
            date_time_format=date_time_format,
        )

        return f"{DATE_TIME.html_open(entity)}{label}{DATE_TIME.html_close(entity)}"

    return None


def _delimiter_entity(spec: EntitySpec, *, language: str) -> types.MessageEntity:
    return types.MessageEntity(
        type=spec.type,
        offset=0,
        length=0,
        language=language,
    )


def _convert_inline(text: str) -> str:
    """Delimiters and links become HTML tags. Everything unpaired stays as it was typed."""
    matches = list(MARKDOWN_RE.finditer(text))
    pairs = _pair(matches)
    closings: dict[int, str] = {}

    parts: list[str] = []
    written: int = 0

    for index, match in enumerate(matches):
        if match.start() < written:
            continue

        chunk = text[written : match.start()]
        written = match.end()

        escaped = match.group("escaped")

        if escaped is not None:
            # As a character reference, so that an escaped delimiter cannot be read as one
            #  on the way through the HTML pass that follows.
            parts.append(chunk)
            parts.append(f"&#{ord(escaped)};")
            continue

        delimiter = match.group("delimiter")

        if delimiter is None:
            markup = _link_markup(
                match.group("label"),
                url=match.group("url"),
                image=bool(match.group("image")),
            )

            parts.append(chunk)
            parts.append(match.group(0) if markup is None else markup)
            continue

        closing_tag = closings.pop(index, None)

        if closing_tag is not None:
            # A fence closes on its own line, and that newline is syntax rather than text.
            if spec_for_delimiter(delimiter) is PRE:
                chunk = chunk.removesuffix("\n")

            parts.append(chunk)
            parts.append(closing_tag)
            continue

        closing_index = pairs.get(index)

        if closing_index is None:
            parts.append(chunk)
            parts.append(delimiter)
            continue

        spec = spec_for_delimiter(delimiter)
        language: str = ""

        # An opening fence owns the rest of its line: the language, and the newline that
        #  ends it. Both are syntax, so neither reaches the message.
        if spec is PRE:
            line_end = text.find("\n", match.end())

            if line_end != -1 and line_end < matches[closing_index].start():
                language = text[match.end() : line_end]
                written = line_end + 1

        entity = _delimiter_entity(spec, language=language)
        closings[closing_index] = spec.html_close(entity)

        parts.append(chunk)
        parts.append(spec.html_open(entity))

    parts.append(text[written:])

    return "".join(parts)


class Markdown:
    def __init__(self, client: pyrogram.Client | None):
        self.html = HTML(client)

    async def parse(self, text: str, *, strict: bool = False) -> dict:
        return await self.html.parse(_convert_inline(_wrap_blockquotes(text, strict=strict)))

    @staticmethod
    def unparse(text: str, *, entities: list[types.MessageEntity]) -> str:
        text = utils.add_surrogates(text)
        placed: list[_PlacedInsertion] = []

        for index, entity in enumerate(entities):
            spec = spec_for_type(entity.type)

            if spec is None:
                continue

            placed.extend(
                _place(
                    insertion,
                    length=entity.length,
                    index=index,
                )
                for insertion in spec.markdown_insertions(entity, message=text)
            )

        parts: list[str] = []
        written: int = 0
        line_prefix: str = ""

        for item in sorted(placed):
            insertion = item.insertion
            chunk = _escape_chunk(
                text[written : insertion.offset],
                line_prefix=line_prefix,
                following=insertion.text,
            )

            parts.append(chunk)
            parts.append(insertion.text)

            line_prefix = _advance_line_prefix(line_prefix, piece=f"{chunk}{insertion.text}")
            written = insertion.offset

        parts.append(
            _escape_chunk(
                text[written:],
                line_prefix=line_prefix,
                following="",
            )
        )

        return utils.remove_surrogates("".join(parts))
