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

from operator import attrgetter
from typing import Final

import pytest

import pyrogram
from pyrogram import raw, types

_ADMIN_ID: Final[int] = 7
_ABSENT_ID: Final[int] = 99
_ADMIN: Final[raw.types.User] = raw.types.User(
    id=_ADMIN_ID,
    first_name="Admin",
    usernames=[],
    restriction_reason=[],
)


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        pytest.param(
            raw.types.ChannelAdminLogEventActionChangeLocation(
                prev_value=raw.types.ChannelLocationEmpty(),
                new_value=raw.types.ChannelLocation(
                    geo_point=raw.types.GeoPointEmpty(),
                    address="Somewhere",
                ),
            ),
            {
                "location_changed.old_location": None,
                "location_changed.new_location.address": "Somewhere",
                "location_changed.new_location.longitude": None,
            },
            id="location-set-without-a-point",
        ),
        pytest.param(
            raw.types.ChannelAdminLogEventActionChangeLocation(
                prev_value=raw.types.ChannelLocation(
                    geo_point=raw.types.GeoPoint(
                        long=1.5,
                        lat=2.5,
                        access_hash=0,
                    ),
                    address="Somewhere",
                ),
                new_value=raw.types.ChannelLocationEmpty(),
            ),
            {
                "location_changed.old_location.longitude": 1.5,
                "location_changed.old_location.address": "Somewhere",
                "location_changed.new_location": None,
            },
            id="location-removed",
        ),
        pytest.param(
            raw.types.ChannelAdminLogEventActionChangeLinkedChat(
                prev_value=0,
                new_value=0,
            ),
            {
                "linked_chat_changed.old_linked_chat": None,
                "linked_chat_changed.new_linked_chat": None,
            },
            id="linked-chat-unlinked",
        ),
        pytest.param(
            raw.types.ChannelAdminLogEventActionChangeEmojiStatus(
                prev_value=raw.types.EmojiStatus(document_id=5),
                new_value=raw.types.EmojiStatusEmpty(),
            ),
            {
                "emoji_status_changed.old_emoji_status.custom_emoji_id": "5",
                "emoji_status_changed.new_emoji_status": None,
            },
            id="emoji-status-cleared",
        ),
        pytest.param(
            raw.types.ChannelAdminLogEventActionChangeAvailableReactions(
                prev_value=raw.types.ChatReactionsAll(),
                new_value=raw.types.ChatReactionsNone(),
            ),
            {
                "available_reactions_changed.old_available_reactions.all_are_enabled": True,
                "available_reactions_changed.new_available_reactions": None,
            },
            id="reactions-disabled",
        ),
        pytest.param(
            raw.types.ChannelAdminLogEventActionPinTopic(
                new_topic=raw.types.ForumTopicDeleted(id=3),
            ),
            {"forum_topic_pinned.old_topic_info": None, "forum_topic_pinned.new_topic_info.id": 3},
            id="first-topic-pinned",
        ),
        pytest.param(
            raw.types.ChannelAdminLogEventActionParticipantJoinByInvite(
                invite=raw.types.ChatInvitePublicJoinRequests(),
            ),
            {"member_joined_by_invite_link.invite_link": None},
            id="joined-by-public-request-link",
        ),
        pytest.param(
            raw.types.ChannelAdminLogEventActionParticipantJoinByRequest(
                invite=raw.types.ChatInvitePublicJoinRequests(),
                approved_by=_ABSENT_ID,
            ),
            {"member_joined_by_invite_link.approver_user": None},
            id="approver-not-in-users",
        ),
        pytest.param(
            raw.types.ChannelAdminLogEventActionParticipantVolume(
                participant=raw.types.GroupCallParticipant(
                    peer=raw.types.PeerUser(user_id=_ABSENT_ID),
                    date=0,
                    source=0,
                    volume=5,
                ),
            ),
            {
                "video_chat_participant_volume_level_changed.participant": None,
                "video_chat_participant_volume_level_changed.volume_level": 5,
            },
            id="participant-not-in-users",
        ),
    ],
)
@pytest.mark.asyncio
async def test_an_event_with_an_empty_or_unknown_value_parses(
    action: raw.base.ChannelAdminLogEventAction,
    expected: dict[str, str | float | None],
) -> None:
    event = raw.types.ChannelAdminLogEvent(
        id=1,
        date=0,
        user_id=_ADMIN_ID,
        action=action,
    )

    client = pyrogram.Client(
        "test",
        api_id=1,
        api_hash="0" * 32,
        in_memory=True,
    )

    parsed = await types.ChatEvent._parse(client, event, {_ADMIN_ID: _ADMIN}, {})

    assert parsed.member.id == _ADMIN_ID
    # Parsing alone is not enough: an empty value has to come out as `None` and a
    #  full one beside it has to keep its data.
    assert {path: attrgetter(path)(parsed) for path in expected} == expected


@pytest.mark.asyncio
async def test_an_edited_invite_link_keeps_both_links() -> None:
    event = raw.types.ChannelAdminLogEvent(
        id=1,
        date=0,
        user_id=_ADMIN_ID,
        action=raw.types.ChannelAdminLogEventActionExportedInviteEdit(
            prev_invite=raw.types.ChatInviteExported(
                link="https://t.me/+old",
                admin_id=_ADMIN_ID,
                date=0,
            ),
            new_invite=raw.types.ChatInviteExported(
                link="https://t.me/+new",
                admin_id=_ADMIN_ID,
                date=0,
            ),
        ),
    )

    client = pyrogram.Client(
        "test",
        api_id=1,
        api_hash="0" * 32,
        in_memory=True,
    )

    parsed = await types.ChatEvent._parse(client, event, {_ADMIN_ID: _ADMIN}, {})

    assert (
        parsed.invite_link_edited.old_invite_link.invite_link,
        parsed.invite_link_edited.new_invite_link.invite_link,
    ) == ("https://t.me/+old", "https://t.me/+new")
