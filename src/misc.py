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
from custom_dataclasses import Role


logger = logging.getLogger(__name__)


def user_join(user, config, msg_broker):
    try:
        next(user.join_quit_log)
        logger.info(
            f'{user} rejoined the chat'
        )
        msg_broker.send_or_forward_msg(
            user,
            config['Banners']['Rejoin']
        )
    except StopIteration:
        logger.info(
            f'{user} joined the chat'
        )
        msg_broker.send_or_forward_msg(
            user,
            config['Banners']['Join']
        )
        default_role_name = config['Roles']['DefaultRole']
        user.role = Role(user._db_man, default_role_name)

    user.join()
