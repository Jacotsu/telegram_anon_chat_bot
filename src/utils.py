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
import sys
from math import ceil
from enum import EnumMeta
from operator import or_ as _or_
from functools import reduce
from typing import List
from telegram import Message, Update
from custom_logging import user_log_str
import permissions


logger = logging.getLogger(__name__)


class CustomEnumMetaForCaseInsensiviSubscript(EnumMeta):
    # https://stackoverflow.com/questions/24716723/
    # issue-extending-enum-and-redefining-getitem
    def __getitem__(self, cls):
        if isinstance(cls, str):
            return super().__getitem__(cls.upper())
        else:
            return super().__getitem__(cls)


def with_limits(enumeration):
    # https://stackoverflow.com/questions/42251081/
    # representation-of-all-values-in-flag-enum
    "add NONE and ALL psuedo-members to enumeration"
    none_mbr = enumeration(0)
    all_mbr = enumeration(reduce(_or_, enumeration))
    enumeration._member_map_['NONE'] = none_mbr
    enumeration._member_map_['ALL'] = all_mbr
    return enumeration


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


def chunk_string(string: str, chunk_size: int):
    number_of_chunks = ceil(len(string) / chunk_size)
    for i in range(number_of_chunks):
        yield string[i::chunk_size]


def get_permissions_from_config_section(config_section):
    perms = permissions.Permissions.NONE
    for perm in config_section.split():
        try:
            perms |= permissions.Permissions[perm.strip()]
        except KeyError:
            logger.error('Invalid default permission in users '
                         f'permissions {perm}')
            sys.exit(1)
    return perms


def create_and_register_poll(
    database_manager,
    update_or_message,
    question: str,
    options: List[str],
    poll_type,
    allows_multiple_answers=True,
    open_period=20
):
    if isinstance(update_or_message, Message):
        message = update_or_message
    elif isinstance(update_or_message, Update):
        message = update_or_message.message
    else:
        raise ValueError('Invalid message/update passed')

    sent_msg = message.reply_poll(
        question=question,
        options=options,
        allows_multiple_answers=True,
        open_period=20
    )

    database_manager.register_admin_poll(
        sent_msg.poll.poll_id,
        poll_type,
        message.from_user.id
    )


class SingletonDecorator:
    '''
    https://python-3-patterns-idioms-test.readthedocs.io/en/latest/
    Singleton.html
    '''
    def __init__(self, klass):
        self.klass = klass
        self.instance = None

    def __call__(self,*args,**kwds):
        if not self.instance:
            self.instance = self.klass(*args, **kwds)
        return self.instance
