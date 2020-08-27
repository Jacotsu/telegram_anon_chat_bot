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
from os.path import dirname, join, exists
from telegram import Bot
from configobj import ConfigObj, ConfigObjError
#from validate import Validator, VdtValueError


logger = logging.getLogger(__name__)


#def telegram_token(token):
#    if Bot._validate_token(token):
#        return token
#    else:
#        raise VdtValueError(f'Invalid token format: {token}')
#
#
#def hex_int(number, default=''):
#    try:
#        return int(number, 16)
#    except ValueError:
#        raise VdtValueError(f'Invalid hash: {number}')
#
#
#def path(path, default=''):
#    if exists(path):
#        return path
#    else:
#        raise VdtValueError(f'Path doesn\'t exist: {path}')
#
#
#def time_delta(time_delta_str, default=''):
#    pass


def load_config():
    #vtor = Validator(
    #    {
    #        'telegram_token': telegram_token,
    #        'path': path,
    #        'hex_integer': hex_int,
    #        'time_delta': time_delta
    #    }
    #)

    #config = ConfigObj(filename, configspec=filename2)
    #test = config.validate(vtor)
    #if test == True:
    #    print 'Succeeded.'

    for path in ['config.ini', '/etc/anon_chat_bot/config.ini']:
        try:
            config = ConfigObj(
                path,
                configspec=join(dirname(__file__), 'configspec.ini')
            )
            if config.keys():
                return config
        except ConfigObjError:
            logger.error("{path}: Config file is malformed")
            sys.exit(1)

    if not config.keys():
        logger.error(
            "Config file is empty, non existent or has wrong "
            "permissions make sure that either config.ini or "
            "/etc/anon_chat_bot/config.ini exist and have correct"
            "permissions")
        sys.exit(1)
