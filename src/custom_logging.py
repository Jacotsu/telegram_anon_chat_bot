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
from telegram import Update


def user_log_str(update_or_message):
    format_str = '{first_name} {last_name} @{username} ({id}):'
    if isinstance(update_or_message, Update):
        msg = update_or_message.message
    elif isinstance(update_or_message, dict):
        return format_str.format(**update_or_message)
    else:
        msg = update_or_message

    return format_str.format(
        first_name=msg.from_user.first_name,
        last_name=msg.from_user.last_name,
        username=msg.from_user.username,
        id=msg.from_user.id)


class CustomFormatter(logging.Formatter):
    # https://stackoverflow.com/questions/1343227/#
    # can-pythons-logging-format-be-modified-depending-on-the-message-log-level

    default_fmt = logging.Formatter('[%(asctime)s]:%(levelname)s:%(message)s')
    debug_fmt = logging.Formatter(
        '%(levelname)s:%(name)s:%(funcName)s@%(lineno)d:%(message)s'
    )

    def format(self, record):
        if record.levelno == logging.DEBUG:
            return self.debug_fmt.format(record)
        else:
            return self.default_fmt.format(record)
