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

from __future__ import annotations as _annotations

from typing import Final

import pytest

import pyrogram
from pyrogram import enums, raw, types
from pyrogram.types.messages_and_media.message import Str

CHANNEL_ID = 1000000000
USER_ID = 777000
DATE = 1755100000
_BUTTON_URL: Final[str] = "https://example.com"


def client():
    return pyrogram.Client("test", api_id=1, api_hash="0" * 32, in_memory=True)


def monoforum_chat():
    return raw.types.Channel(
        id=CHANNEL_ID,
        title="Direct messages",
        photo=raw.types.ChatPhotoEmpty(),
        date=DATE,
        broadcast=True,
        monoforum=True,
        access_hash=0,
        usernames=[],
        restriction_reason=[],
    )


def message(*, saved_peer_id=None):
    return raw.types.Message(
        id=1,
        peer_id=raw.types.PeerChannel(channel_id=CHANNEL_ID),
        from_id=raw.types.PeerUser(user_id=USER_ID),
        saved_peer_id=saved_peer_id,
        date=DATE,
        message="hi",
        entities=[],
        restriction_reason=[],
    )


@pytest.mark.asyncio
async def test_a_direct_message_without_a_topic_parses():
    parsed = await types.Message._parse(
        client(), message(), users={}, chats={CHANNEL_ID: monoforum_chat()}
    )

    assert parsed.chat.type == enums.ChatType.DIRECT
    assert parsed.direct_messages_topic_id is None
    assert parsed.topic is None


@pytest.mark.asyncio
async def test_a_direct_message_with_a_topic_keeps_its_id():
    parsed = await types.Message._parse(
        client(),
        message(saved_peer_id=raw.types.PeerUser(user_id=USER_ID)),
        users={},
        chats={CHANNEL_ID: monoforum_chat()},
    )

    assert parsed.direct_messages_topic_id == USER_ID


def message_with_url_button(label: str) -> types.Message:
    keyboard = types.InlineKeyboardMarkup(
        [[types.InlineKeyboardButton(label, url=_BUTTON_URL)]],
    )

    return types.Message(
        id=1,
        reply_markup=keyboard,
    )


@pytest.mark.asyncio
async def test_a_button_is_found_by_its_label() -> None:
    keyboard_message = message_with_url_button("Open")

    assert await keyboard_message.click("Open") == _BUTTON_URL


@pytest.mark.asyncio
async def test_an_unknown_button_label_names_the_label() -> None:
    keyboard_message = message_with_url_button("Open")

    with pytest.raises(ValueError, match="The button with label 'Close' doesn't exist"):
        await keyboard_message.click("Close")


@pytest.mark.asyncio
async def test_an_unknown_button_index_names_the_index() -> None:
    keyboard_message = message_with_url_button("Open")

    with pytest.raises(ValueError, match="The button at index 9 doesn't exist"):
        await keyboard_message.click(9)


_EMOJI_TEXT: Final[str] = "😀 250"


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        pytest.param(0, "😀", id="leading-half"),
        pytest.param(1, "😀", id="trailing-half"),
        pytest.param(2, " ", id="after-the-pair"),
        pytest.param(-1, "0", id="from-the-end"),
    ],
)
def test_an_index_inside_a_surrogate_pair_gives_the_whole_code_point(
    item: int,
    *,
    expected: str,
) -> None:
    assert Str(_EMOJI_TEXT)[item] == expected


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        pytest.param(slice(0, 1), "😀", id="leading-half-only"),
        pytest.param(slice(1, 2), "😀", id="trailing-half-only"),
        pytest.param(slice(0, 2), "😀", id="the-whole-pair"),
        pytest.param(slice(1, 3), "😀 ", id="opening-inside-the-pair"),
        pytest.param(slice(2, None), " 250", id="past-the-pair"),
        pytest.param(slice(None, None, -1), "052 😀", id="reversed"),
    ],
)
def test_a_slice_cutting_a_surrogate_pair_widens_to_the_whole_code_point(
    item: slice,
    *,
    expected: str,
) -> None:
    assert Str(_EMOJI_TEXT)[item] == expected


def test_an_entity_offset_still_indexes_the_text_that_entity_marks() -> None:
    entity = types.MessageEntity(
        type=enums.MessageEntityType.BOLD,
        offset=3,
        length=4,
    )
    text = Str("😀 bold").init([entity])

    assert text[entity.offset : entity.offset + entity.length] == "bold"


@pytest.mark.asyncio
async def test_a_basic_group_message_sent_as_a_channel_names_the_channel() -> None:
    group_id: int = 5
    group = raw.types.Chat(
        id=group_id,
        title="Group",
        photo=raw.types.ChatPhotoEmpty(),
        participants_count=2,
        date=DATE,
        version=1,
    )
    raw_message = raw.types.Message(
        id=1,
        peer_id=raw.types.PeerChat(chat_id=group_id),
        from_id=raw.types.PeerChannel(channel_id=CHANNEL_ID),
        date=DATE,
        message="hi",
        entities=[],
        restriction_reason=[],
    )
    channel = monoforum_chat()
    channel.monoforum = False

    parsed = await types.Message._parse(
        client(),
        raw_message,
        users={},
        chats={group_id: group, CHANNEL_ID: channel},
    )

    assert (parsed.chat.type, parsed.sender_chat.type) == (
        enums.ChatType.GROUP,
        enums.ChatType.CHANNEL,
    )


@pytest.mark.asyncio
async def test_an_unknown_user_sender_is_not_taken_for_the_group() -> None:
    # The sender's id was looked up in the map picked by the group's own peer
    #  type, so a user with the same id as the group named the group as the sender.
    group_id: int = 5
    group = raw.types.Chat(
        id=group_id,
        title="Group",
        photo=raw.types.ChatPhotoEmpty(),
        participants_count=2,
        date=DATE,
        version=1,
    )
    raw_message = raw.types.Message(
        id=1,
        peer_id=raw.types.PeerChat(chat_id=group_id),
        from_id=raw.types.PeerUser(user_id=group_id),
        date=DATE,
        message="hi",
        entities=[],
        restriction_reason=[],
    )

    parsed = await types.Message._parse(
        client(),
        raw_message,
        users={},
        chats={group_id: group},
    )

    assert (parsed.chat.type, parsed.sender_chat) == (enums.ChatType.GROUP, None)


def broadcast_channel() -> raw.types.Channel:
    channel = monoforum_chat()
    channel.monoforum = False

    return channel


def raw_message_of_kind(
    kind: str,
    *,
    from_id: raw.base.Peer | None,
) -> raw.types.Message | raw.types.MessageService | raw.types.EphemeralMessage:
    peer_id = raw.types.PeerChannel(channel_id=CHANNEL_ID)

    if kind == "message":
        return raw.types.Message(
            id=1,
            peer_id=peer_id,
            from_id=from_id,
            date=DATE,
            message="hi",
            entities=[],
            restriction_reason=[],
        )

    if kind == "service":
        return raw.types.MessageService(
            id=1,
            peer_id=peer_id,
            from_id=from_id,
            date=DATE,
            action=raw.types.MessageActionChatEditTitle(title="Channel"),
        )

    # An ephemeral message always names its sender.
    return raw.types.EphemeralMessage(
        id=1,
        from_id=from_id or peer_id,
        peer_id=peer_id,
        receiver_id=USER_ID,
        date=DATE,
        message="hi",
    )


@pytest.mark.parametrize("kind", ["message", "service", "ephemeral"])
@pytest.mark.parametrize(
    ("from_id", "expected"),
    [
        pytest.param(None, (None, enums.ChatType.CHANNEL), id="channel"),
        pytest.param(
            raw.types.PeerUser(user_id=CHANNEL_ID),
            (CHANNEL_ID, None),
            id="user",
        ),
    ],
)
@pytest.mark.asyncio
async def test_the_sender_is_looked_up_by_its_own_peer_type(
    kind: str,
    *,
    from_id: raw.base.Peer | None,
    expected: tuple[int | None, enums.ChatType | None],
) -> None:
    # User and channel ids overlap, so a lookup by raw id alone took a channel for the user.
    user = raw.types.User(
        id=CHANNEL_ID,
        first_name="User",
        access_hash=0,
    )

    parsed = await types.Message._parse(
        client(),
        raw_message_of_kind(kind, from_id=from_id),
        users={CHANNEL_ID: user},
        chats={CHANNEL_ID: broadcast_channel()},
    )

    assert (
        parsed.from_user.id if parsed.from_user else None,
        parsed.sender_chat.type if parsed.sender_chat else None,
    ) == expected


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("message", id="message"),
        pytest.param("service", id="service"),
        pytest.param("ephemeral", id="ephemeral"),
    ],
)
@pytest.mark.asyncio
async def test_the_chat_is_the_peer_and_not_the_sender(kind: str) -> None:
    user = raw.types.User(
        id=USER_ID,
        first_name="User",
        access_hash=0,
    )

    parsed = await types.Message._parse(
        client(),
        raw_message_of_kind(kind, from_id=raw.types.PeerUser(user_id=USER_ID)),
        users={USER_ID: user},
        chats={CHANNEL_ID: broadcast_channel()},
    )

    assert parsed.chat.type == enums.ChatType.CHANNEL


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("message", id="message"),
        pytest.param("service", id="service"),
        pytest.param("ephemeral", id="ephemeral"),
    ],
)
@pytest.mark.asyncio
async def test_a_sender_answered_as_user_empty_is_left_out(kind: str) -> None:
    # The `users.getUsers` fallback merges `userEmpty` for a sender with no user behind it.
    #  The id differs from `USER_ID`, which an ephemeral message names as its receiver.
    sender_id: int = USER_ID + 1

    parsed = await types.Message._parse(
        client(),
        raw_message_of_kind(kind, from_id=raw.types.PeerUser(user_id=sender_id)),
        users={sender_id: raw.types.UserEmpty(id=sender_id)},
        chats={CHANNEL_ID: broadcast_channel()},
    )

    assert (parsed.chat.type, parsed.from_user, parsed.sender_chat) == (
        enums.ChatType.CHANNEL,
        None,
        None,
    )
