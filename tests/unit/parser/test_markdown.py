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

import pyrogram
from pyrogram.parser.markdown import Markdown


# expected: the expected unparsed Markdown
# text: original text without entities
# entities: message entities coming from the server


def test_markdown_unparse_bold() -> None:
    expected: str = "**bold**"
    text: str = "bold"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.BOLD, offset=0, length=4
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_italic() -> None:
    expected: str = "__italic__"
    text: str = "italic"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.ITALIC, offset=0, length=6
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_strike() -> None:
    expected: str = "~~strike~~"
    text: str = "strike"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.STRIKETHROUGH, offset=0, length=6
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_spoiler() -> None:
    expected: str = "||spoiler||"
    text: str = "spoiler"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.SPOILER, offset=0, length=7
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_url() -> None:
    expected: str = "[URL](https://pyrogram.org/)"
    text: str = "URL"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.TEXT_LINK,
                offset=0,
                length=3,
                url="https://pyrogram.org/",
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_emoji() -> None:
    expected: str = "![🥲](tg://emoji?id=5195264424893488796) im crying"
    text: str = "🥲 im crying"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.CUSTOM_EMOJI,
                offset=0,
                length=2,
                custom_emoji_id=5195264424893488796,
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_code() -> None:
    expected: str = "`code`"
    text: str = "code"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.CODE, offset=0, length=4
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_pre() -> None:
    expected: str = """```python
for i in range(10):
    print(i)
```"""

    text: str = """for i in range(10):
    print(i)"""

    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.PRE, offset=0, length=32, language="python"
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_blockquote() -> None:
    expected: str = """> Hello
> from

> pyrogram!"""

    text: str = """Hello\nfrom\n\npyrogram!"""

    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.BLOCKQUOTE, offset=0, length=10
            ),
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.BLOCKQUOTE, offset=12, length=9
            ),
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_mixed() -> None:
    expected: str = (
        "**aaaaaaa__aaabbb**__~~dddddddd||ddeee~~||||eeeeeeefff||ffff`fffggggggg`ggghhhhhhhhhh"
    )
    text: str = "aaaaaaaaaabbbddddddddddeeeeeeeeeeffffffffffgggggggggghhhhhhhhhh"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.BOLD, offset=0, length=13
            ),
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.ITALIC, offset=7, length=6
            ),
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.STRIKETHROUGH, offset=13, length=13
            ),
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.SPOILER, offset=21, length=5
            ),
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.SPOILER, offset=26, length=10
            ),
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.CODE, offset=40, length=10
            ),
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_no_entities() -> None:
    expected: str = "text"
    text: str = "text"
    entities: list[pyrogram.types.MessageEntity] = []

    assert Markdown.unparse(text=text, entities=entities) == expected


def test_markdown_unparse_html() -> None:
    expected: str = "__This works, it's ok__ <b>This shouldn't</b>"
    text: str = "This works, it's ok <b>This shouldn't</b>"
    entities = pyrogram.types.List(
        [
            pyrogram.types.MessageEntity(
                type=pyrogram.enums.MessageEntityType.ITALIC, offset=0, length=19
            )
        ]
    )

    assert Markdown.unparse(text=text, entities=entities) == expected
