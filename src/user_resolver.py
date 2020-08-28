#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
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

import logging
from telegram import Update, Message
from telethon.sync import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from utils import SingletonDecorator
import custom_dataclasses

logger = logging.getLogger(__name__)


class UserResolverError(Exception):
    pass


@SingletonDecorator
class UserResolver:
    def __init__(self, database_manager, config):
        self._db_man = database_manager
        api_id = config["UsernameResolver"]["ApiId"]
        api_hash = config["UsernameResolver"]["ApiHash"]

        if api_id and api_hash:
            self._tg_client = TelegramClient('anon chat bot user resolver',
                                             api_id, api_hash)
            logger.debug('Initialized user resolver with username support')
        else:
            self._tg_client = None

    def acquire_target_user_from_cmd(
            self,
            update: Update,
            target_position: int = 0) -> custom_dataclasses.User:
        '''
        If update is a reply to a message the sender of the original message
        is returned, otherwise it takes the text at the specified position
        and tries to resolve it if it's a username
        '''
        replied_msg = update.message.reply_to_message
        # Remove the issued command from the command line and then split it
        split_cmd = " ".join(update.message.text.split()[1:]).split(',')
        split_cmd_len = len(split_cmd)

        if replied_msg:
            return custom_dataclasses.User(self._db_man, replied_msg.from_user)
        else:
            if split_cmd_len > target_position:
                return self.resolve(split_cmd[target_position].strip())
            else:
                raise ValueError('The command string is too short to contain'
                                 'the target word '
                                 f'(target_position={target_position})')

    def resolve(self, value_or_update) -> custom_dataclasses.User:
        if type(value_or_update) == int:
            return custom_dataclasses.User(
                self._db_man, value_or_update, resolver=self)
        elif type(value_or_update) == str:
            if self._tg_client:
                with self._tg_client as tg_client:
                    peer_id = tg_client.get_peer_id(value_or_update)
                    if peer_id:
                        return custom_dataclasses.User(
                            self._db_man, peer_id, resolver=self)
                    else:
                        raise ValueError(f'{value_or_update} is an '
                                         'invalid username')
            else:
                raise UserResolverError('Username resolution is not '
                                        'configured')
        elif type(value_or_update) == Update:
            return custom_dataclasses.User(
                self._db_man, value_or_update.message.from_user)
        elif type(value_or_update) == Message:
            return custom_dataclasses.User(
                self._db_man, value_or_update.from_user)
        else:
            raise ValueError(f'{value_or_update}\'s type is wrong')

    def get_user_info(self, username_or_id):
        if self._tg_client:
            with self._tg_client as tg_client:
                info = tg_client(GetFullUserRequest(username_or_id))
                return {
                    'first_name': info.user.first_name,
                    'last_name': info.user.last_name,
                    'username': info.user.username,
                    'id': info.user.id
                }
        else:
            raise UserResolverError('Username resolution is not '
                                    'configured')
