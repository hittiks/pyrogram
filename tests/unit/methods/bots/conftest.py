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

import base64
import struct
from typing import Final

from pyrogram import raw
from pyrogram.methods.bots.get_inline_game_high_scores import GetInlineGameHighScores
from pyrogram.methods.bots.set_inline_game_score import SetInlineGameScore

INLINE_MESSAGE_DC_ID: Final[int] = 4

# The Bot API packs `inline_message_id` as unpadded url-safe base64 of `<iqq`: DC, message id,
#  access hash. Packed here from that layout rather than by the code under test.
INLINE_MESSAGE_ID: Final[str] = (
    base64.urlsafe_b64encode(struct.pack("<iqq", INLINE_MESSAGE_DC_ID, 42, 7)).decode().rstrip("=")
)

RAW_INLINE_MESSAGE_ID: Final[raw.types.InputBotInlineMessageID] = raw.types.InputBotInlineMessageID(
    dc_id=INLINE_MESSAGE_DC_ID,
    id=42,
    access_hash=7,
)


class FakeSession:
    """Records the wire bytes of every query sent through it and answers with a canned response.

    Bytes, because `TLObject.__eq__` never compares the type: `InputUserSelf() == InputUser(user_id=7,
    access_hash=0)` is `True`, so a query-to-query assert passes with the user dropped.
    """

    def __init__(self, response: raw.core.TLObject | bool) -> None:
        self.response = response
        self.sent: list[bytes] = []

    async def invoke(
        self,
        query: raw.core.TLObject,
        *,
        sleep_threshold: float,
    ) -> raw.core.TLObject | bool:
        self.sent.append(query.write())

        return self.response


class InlineGameClient(SetInlineGameScore, GetInlineGameHighScores):
    """A client whose only session is a `FakeSession`, recording which DC was asked for."""

    sleep_threshold: float = 10

    def __init__(self, response: raw.core.TLObject | bool) -> None:
        self.session = FakeSession(response)
        self.requested_dc_ids: list[int] = []

    async def get_session(self, dc_id: int, *, is_media: bool) -> FakeSession:
        self.requested_dc_ids.append(dc_id)

        return self.session

    async def resolve_peer(self, peer_id: int | str) -> raw.types.InputUser:
        return raw.types.InputUser(
            user_id=int(peer_id),
            access_hash=0,
        )
