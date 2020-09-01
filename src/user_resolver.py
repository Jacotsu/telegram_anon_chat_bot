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
import asyncio
import threading
from os.path import exists
from telegram import Update, Message
from telethon.sync import TelegramClient
from utils import SingletonDecorator, split_cmd_line
import custom_dataclasses
from custom_exceptions import UserResolverError

logger = logging.getLogger(__name__)

# Mixing telethon and python telegram bot is not ideal since the former
# uses asyncio and the latter threads. Asyncio should be more efficient but
# the python telegram bot's filters are really handy. This hybrid form will do
# for the moment
@SingletonDecorator
class UserResolver:
    def __init__(self, database_manager, config):
        self._db_man = database_manager
        self._api_id = config["UsernameResolver"]["ApiId"]
        self._api_hash = config["UsernameResolver"]["ApiHash"]
        self._session_path = config["UsernameResolver"]["SessionPath"]
        self._threads_data = {}

    def _init_thread_event_loop(self):
        '''
        !!!MESS ALERT!!
        Every thread needs its own telethon client because telethon is not
        thread safe
        '''
        thread_id = threading.get_ident()
        if thread_id not in self._threads_data:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if self._api_id and self._api_hash and exists(self._session_path):
                client = TelegramClient(
                    self._session_path, self._api_id, self._api_hash, timeout=2
                )
                logger.debug('Initialized user resolver with username support')
            else:
                client = None
                logger.info('User resolver is disabled')

            self._threads_data[thread_id] = {
                'loop': loop,
                'client': client
            }

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
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        if replied_msg:
            user = self._db_man.get_message_sender(replied_msg)
            return self.resolve(user.id)
        else:
            if split_cmd_len > target_position:
                return self.resolve(split_cmd[target_position].strip())
            else:
                raise ValueError('The command string is too short to contain'
                                 'the target word '
                                 f'(target_position={target_position})')

    def resolve(self, value_or_update) -> custom_dataclasses.User:
        if type(value_or_update) == str or type(value_or_update) == int:
            try:
                return custom_dataclasses.User(
                    self._db_man, int(value_or_update), resolver=self)
            except ValueError:
                self._init_thread_event_loop()
                thread_id = threading.get_ident()
                if self._threads_data[thread_id]['client']:
                    with self._threads_data[thread_id]['client'] as tg_client:
                        try:
                            peer_id = tg_client.get_peer_id(value_or_update)
                            return custom_dataclasses.User(
                                self._db_man, peer_id, resolver=self)
                        except ValueError:
                            raise UserResolverError('Invalid username/user_id')
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

        thread_id = threading.get_ident()
        self._init_thread_event_loop()
        if self._threads_data[thread_id]['client']:
            with self._threads_data[thread_id]['client'] as tg_client:
                try:
                    telethon_user = tg_client.get_entity(username_or_id)
                except ValueError:
                    raise UserResolverError('Invalid username/user_id')
                return {
                    'first_name': telethon_user.first_name,
                    'last_name': telethon_user.last_name,
                    'username': telethon_user.username,
                    'id': telethon_user.id
                }
        else:
            raise UserResolverError('Username resolution is not configured')
