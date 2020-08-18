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


from typing import Iterable
import logging
from telegram.ext import MessageHandler, Filters
from custom_filters import ActiveUsersFilter, UnbannedUsersFilter,\
        PassedCaptchaFilter
from permissions import Permissions
from custom_dataclasses import User

logger = logging.getLogger(__name__)


class MessageBroker:
    '''
    This class' main purpose is to send messages to valid users
    '''
    def __init__(self, updater, database_manager, captcha_manager):
        self._db_man = database_manager
        self._updater = updater
        self._captcha_manager = captcha_manager

        self._updater.dispatcher.add_handler(
            MessageHandler(
                UnbannedUsersFilter(self._db_man) &
                ~Filters.command &
                PassedCaptchaFilter(self._db_man, self._captcha_manager),
                callback=self.process_message))

    def process_message(self, update, context):
        # Do things
        self.send_message(update.message.text)

    def send_message(self,
                     message,
                     users: Iterable[User] = None,
                     permissions: Permissions = Permissions.RECEIVE):
        '''
        @param permissions The permissions required to receive the message

        '''
        # Filter banned users, users that stopped the bot and those who
        # didn't pass the captcha
        if users:
            effective_users = filter(lambda x:
                                     permissions in x.permissions and
                                     x.captcha_status.passed
                                     and x.is_active,
                                     users)
        else:
            effective_users = filter(lambda x:
                                     permissions in x.permissions and
                                     x.captcha_status.passed
                                     and x.is_active,
                                     self._db_man.get_active_users())

        for user in effective_users:
            logger.debug(f'Relaying message to {user.user_id}')
            self._updater.bot.send_message(user.user_id, message)
