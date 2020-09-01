#!/usr/bin/env python3
# anon_chat_bot is a telegram bot whose main function is to manage an
# anonymous chat lounge
# Copyright (C) <2020>  <jacotsu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


from telethon.sync import TelegramClient

api_id = input('Insert your api id: ')
api_hash = input('Insert your api hash: ')

tg_client = TelegramClient('tg_session.session', api_id, api_hash)
with tg_client as tg_session:
    me = tg_session.get_me()
    tg_session.send_message(me, 'username resolver configured')
