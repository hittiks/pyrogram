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

import pytest

from pyrogram import raw
from .conftest import (
    INLINE_MESSAGE_DC_ID,
    INLINE_MESSAGE_ID,
    RAW_INLINE_MESSAGE_ID,
    InlineGameClient,
)


@pytest.mark.asyncio
async def test_asks_the_inline_message_dc_for_high_scores() -> None:
    client = InlineGameClient(
        response=raw.types.messages.HighScores(
            scores=[
                raw.types.HighScore(
                    pos=1,
                    user_id=7,
                    score=1000,
                )
            ],
            users=[raw.types.User(id=7)],
        )
    )

    result = await client.get_inline_game_high_scores(
        INLINE_MESSAGE_ID,
        user_id=7,
    )

    assert [(score.user.id, score.score, score.position) for score in result] == [(7, 1000, 1)]
    assert client.requested_dc_ids == [INLINE_MESSAGE_DC_ID]
    assert client.session.sent == [
        raw.functions.messages.GetInlineGameHighScores(
            id=RAW_INLINE_MESSAGE_ID,
            user_id=raw.types.InputUser(
                user_id=7,
                access_hash=0,
            ),
        ).write()
    ]
