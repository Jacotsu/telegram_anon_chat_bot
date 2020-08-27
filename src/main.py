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
import argparse
from custom_logging import CustomFormatter
from bot_manager import BotManager
from custom_config import load_config


hdlr = logging.StreamHandler()
hdlr.setFormatter(CustomFormatter())
logging.root.addHandler(hdlr)
logger = logging.getLogger(__name__)


def main():
    '''
    Main entry point
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbosity', default='info',
                        choices=['debug', 'info', 'warning'],
                        help='sets the verbosity level')
    args = parser.parse_args()

    root_logger = logging.getLogger()
    if args.verbosity == 'debug':
        root_logger.setLevel(logging.DEBUG)
    elif args.verbosity == 'warning':
        root_logger.setLevel(logging.WARNING)
    else:
        root_logger.setLevel(logging.INFO)

    # DO NOT REMOVE THIS
    # if you do not use the root logging facility once, per module logging
    # wont work
    logging.warning(f'Log level set to {args.verbosity}')

    config = load_config()
    bot_mgr = BotManager(config)
    bot_mgr.start()
    bot_mgr.idle()


if __name__ == "__main__":
    main()
