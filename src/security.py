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
from telegram.ext import Updater

logger = logging.getLogger(__name__)

def has_permissions(logger=logging.getLogger(__name__)):
    def wrap(f):
        def wrapped_f(*args, **kwargs):
            f(*args, **kwargs)
            try:
                user = args[0]['message'].from_user
                data = args[0]['message'].text
            except AttributeError:
                user = args[0]['callback_query'].from_user
                data = args[0]['callback_query'].data

            logger.info(f"{user['username']} ({user['id']}) Has executed: "
                        f"{f.__name__} \"{data}\"")
        return wrapped_f
    return wrap


def check_captcha(f):
    def wrap(*args, **kwargs):
        f(*args, **kwargs)
    return wrap


class CaptchaManager:
    pass
