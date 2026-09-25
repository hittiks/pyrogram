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
async def test_sends_the_score_to_the_inline_message_dc() -> None:
    client = InlineGameClient(response=True)

    result = await client.set_inline_game_score(
        INLINE_MESSAGE_ID,
        user_id=7,
        score=1000,
    )

    assert result is True
    assert client.requested_dc_ids == [INLINE_MESSAGE_DC_ID]
    assert client.session.sent == [
        raw.functions.messages.SetInlineGameScore(
            id=RAW_INLINE_MESSAGE_ID,
            user_id=raw.types.InputUser(
                user_id=7,
                access_hash=0,
            ),
            score=1000,
            edit_message=True,
        ).write()
    ]


@pytest.mark.asyncio
async def test_forced_score_without_message_edit() -> None:
    client = InlineGameClient(response=True)

    await client.set_inline_game_score(
        INLINE_MESSAGE_ID,
        user_id=7,
        score=25,
        force=True,
        disable_edit_message=True,
    )

    assert client.session.sent == [
        raw.functions.messages.SetInlineGameScore(
            id=RAW_INLINE_MESSAGE_ID,
            user_id=raw.types.InputUser(
                user_id=7,
                access_hash=0,
            ),
            score=25,
            force=True,
            edit_message=False,
        ).write()
    ]
