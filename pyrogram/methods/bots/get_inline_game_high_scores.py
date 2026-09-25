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

import pyrogram
from pyrogram import raw, types, utils


class GetInlineGameHighScores:
    async def get_inline_game_high_scores(
        self: pyrogram.Client,
        inline_message_id: str,
        *,
        user_id: int | str,
    ) -> list[types.GameHighScore]:
        """Get data for high score tables of a game sent via inline mode.

        .. include:: /_includes/usable-by/bots.rst

        Parameters:
            inline_message_id (``str``):
                Identifier of the inline message.

            user_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target user.
                For a contact that exists in your Telegram address book you can use his phone number (str).

        Returns:
            List of :obj:`~pyrogram.types.GameHighScore`: On success.

        Example:
            .. code-block:: python

                scores = await app.get_inline_game_high_scores(inline_message_id, user_id=user_id)
                print(scores)
        """
        unpacked = utils.unpack_inline_message_id(inline_message_id)

        session = await self.get_session(unpacked.dc_id, is_media=True)

        high_scores = await session.invoke(
            raw.functions.messages.GetInlineGameHighScores(
                id=unpacked,
                user_id=await self.resolve_peer(user_id),
            ),
            sleep_threshold=self.sleep_threshold,
        )

        return types.List(
            [
                await types.GameHighScore._parse(self, score, high_scores.users)
                for score in high_scores.scores
            ]
        )
