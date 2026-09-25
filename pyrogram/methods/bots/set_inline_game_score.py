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
from pyrogram import raw, utils


class SetInlineGameScore:
    async def set_inline_game_score(
        self: pyrogram.Client,
        inline_message_id: str,
        *,
        user_id: int | str,
        score: int,
        force: bool | None = None,
        disable_edit_message: bool | None = None,
    ) -> bool:
        """Set the score of the specified user in a game sent via inline mode.

        .. include:: /_includes/usable-by/bots.rst

        Parameters:
            inline_message_id (``str``):
                Identifier of the inline message.

            user_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target user.
                For a contact that exists in your Telegram address book you can use his phone number (str).

            score (``int``):
                New score, must be non-negative.

            force (``bool``, *optional*):
                Pass True, if the high score is allowed to decrease.
                This can be useful when fixing mistakes or banning cheaters.

            disable_edit_message (``bool``, *optional*):
                Pass True, if the game message should not be automatically edited to include the current scoreboard.

        Returns:
            ``bool``: On success, True is returned.

        Example:
            .. code-block:: python

                # Set new score
                await app.set_inline_game_score(inline_message_id, user_id=user_id, score=1000)

                # Force set new score
                await app.set_inline_game_score(inline_message_id, user_id=user_id, score=25, force=True)
        """
        unpacked = utils.unpack_inline_message_id(inline_message_id)

        session = await self.get_session(unpacked.dc_id, is_media=True)

        return await session.invoke(
            raw.functions.messages.SetInlineGameScore(
                id=unpacked,
                user_id=await self.resolve_peer(user_id),
                score=score,
                force=force,
                edit_message=not disable_edit_message,
            ),
            sleep_threshold=self.sleep_threshold,
        )
