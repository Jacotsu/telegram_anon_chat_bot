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
from telegram.update import Update
from custom_dataclasses import User
from custom_logging import user_log_str


logger = logging.getLogger(__name__)


def validate_number_command_args(f):
    # The first argumentss should be the class instance
    def wrap(*args, **kwargs):
        msg = args[1]['message']
        split_cmd = msg.text.split()
        cmd_dict = args[0].commands[split_cmd[0]]
        if cmd_dict['min_args'] < len(split_cmd) - 1 <\
           cmd_dict['max_args']:
            f(*args, **kwargs)
        else:
            logger.error(
                f'User {user_log_str(args[0])} has tried to execute '
                f'{split_cmd[0]} with the wrong number of arguments'
            )
            msg.reply_text(
                f'Wrong number of arguments for {split_cmd[0]}\n'
                f'{args[0].commands[split_cmd[0]]["usage"]}'
            )


def log_action(logger=logging.getLogger(__name__)):
    def wrap(f):
        def wrapped_f(*args, **kwargs):
            f(*args, **kwargs)
            args_list = [*args]
            for arg in args_list:
                if type(arg) == Update:
                    try:
                        user = arg['message'].from_user
                        data = arg['message'].text
                    except AttributeError:
                        user = arg['callback_query'].from_user
                        data = arg['callback_query'].data
                    logger.info(
                        f'{user_log_str(arg)} {f.__name__} \"{data}\"'
                    )
                    break

        return wrapped_f
    return wrap


def get_user_by_reply_username_rawid(update_msg):
    replied_msg = update_msg.reply_to_message
    if replied_msg:
        user_id = replied_msg.from_user.id
    elif '@' in update_msg.text:
        # TODO
        user_id = update_msg.text.split()[1]
        pass
    else:
        # is raw id
        user_id = update_msg.text.split()[1]

    # Make sure that None doesn't end up in the database
    return User(user_id, None)
