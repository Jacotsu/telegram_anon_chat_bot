#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# OpsecAnonChatBot is a telegram bot whose main function is to manage an
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
import sys
from telegram.ext import CommandHandler
from utils import log_action
from custom_logging import user_log_str
from custom_filters import ActiveUsersFilter, UnbannedUsersFilter,\
        PassedCaptchaFilter
from database import DatabaseManager
from custom_dataclasses import User
from permissions import Permissions

logger = logging.getLogger(__name__)


class CommandExecutor:
    def __init__(self,
                 config,
                 updater,
                 database_manager,
                 message_broker,
                 captcha_manager):
        self._config = config
        self._db_man = database_manager
        self._updater = updater
        self._msg_broker = message_broker
        self._captcha_manager = captcha_manager

        self._default_permissions = Permissions.NONE
        for perm in self._config["Users"]["DefaultPermissions"].split():
            try:
                self._default_permissions |= Permissions[perm.strip()]
            except KeyError:
                logger.error('Invalid permission in default users '
                             f'permissions {perm}')
                sys.exit(1)

        self.commands = {
            'join': {
                'description': 'Join the chat',
                'permissions_required': Permissions.NONE,
                'usage': '/join',
                'min_args': 0,
                'max_args': 0,
                'filters': UnbannedUsersFilter(self._db_man) &
                PassedCaptchaFilter(self._db_man, self._captcha_manager),
                'callback': self.join
            },
            'quit': {
                'description': 'Quits the chat',
                'permissions_required': Permissions.NONE,
                'usage': '/quit',
                'min_args': 0,
                'max_args': 0,
                'filters': ActiveUsersFilter(self._db_man) &
                UnbannedUsersFilter(self._db_man),
                'callback': self.quit
            },
            'help': {
                'description': 'Shows the help page',
                'permissions_required': Permissions.NONE,
                'usage': '/help',
                'min_args': 0,
                'max_args': 0,
                'filters': ActiveUsersFilter(self._db_man) &
                UnbannedUsersFilter(self._db_man),
                'callback': self.help
            },
            'ping': {
                'description': 'Shows if the bot is online',
                'permissions_required': Permissions.NONE,
                'usage': '/ping',
                'min_args': 0,
                'max_args': 0,
                'filters': ActiveUsersFilter(self._db_man) &
                UnbannedUsersFilter(self._db_man),
                'callback': self.ping
            }
        }

        message_dispatcher = updater.dispatcher
        for cmd_name, cmd_dict in self.commands.items():
            message_dispatcher.add_handler(
                CommandHandler(cmd_name,
                               cmd_dict['callback'],
                               filters=cmd_dict['filters'])
            )
            logger.debug(f'Registered {cmd_name}: {cmd_dict["callback"]}')

        bot = updater.bot

        # Sets the public commands
        public_commands = map(lambda x: (x[0],
                                         x[1]['description']),
                              filter(lambda x:
                                     x[1]['permissions_required'] ==
                                     Permissions.NONE,
                                     self.commands.items()))
        bot.set_my_commands([*public_commands])


    # General commands
    @log_action(logger)
    def join(self, update, context):
        tg_user = update.message.from_user
        # Creates a new user if it doesn't exist

        if self._db_man.user_exists(tg_user.id):
            logger.info(
                f'{user_log_str(update)} rejoined the chat'
            )
            update.message.reply_text('Welcome back')
        else:
            logger.info(
                f'{user_log_str(update)} joined the chat'
            )
            update.message.reply_text('Congratulations you have joined the'
                                      'opsec chat')

        User(self._db_man, tg_user.id, self._default_permissions).join()

    @log_action(logger)
    def quit(self, update, context):
        tg_user = update.message.from_user
        User(self._db_man, tg_user.id).quit()
        update.message.reply_text('K, Bye')
        logger.info(
            f'{user_log_str(update)} quit the chat'
        )

    @log_action(logger)
    def ping(self, update, context):
        update.message.reply_text("pong")

    @log_action(logger)
    def help(self, update, context):
        '''
        Sends the help text to the user based on what permissions he has
        '''
        user = User(self._db_man,
                    update.message.from_user.id,
                    update.message.chat.id)
        user_permissions = user.permissions
        msg_string = 'OpsecAnonChatBot help page: \n'
        for cmd_name, cmd_dict in self.commands.items():
            if cmd_dict['permissions_required'] in user_permissions:
                msg_string += f'*{cmd_name}*:\nusage: `{cmd_dict["usage"]}`\n'\
                        f'```\n{cmd_dict["description"]}\n```\n'
        update.message.reply_markdown(msg_string)

    # Admin commands

    @log_action(logger)
    def ban(self, update, context):
        user_id = update.message.id

        replied_msg = update.message.reply_to_message

        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        if split_cmd_len == 2:
            if not replied_msg:
                update.message.reply('Wrong number of parameters passed to '
                                     'ban')
            else:
                user_id = replied_msg.from_user.id
        elif split_cmd_len == 3:
            user_id = split_cmd[1]
        else:
            update.message.reply('Wrong number of parameters passed to ban')

        #User(self._db_man, user_id).ban()

    @log_action(logger)
    def kick(self, update, context):
        pass

    @log_action(logger)
    def set_permissions(self, update, context):
        pass
