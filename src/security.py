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
from custom_dataclasses import User, Role

logger = logging.getLogger(__name__)


def is_hierarchy_respected(agent: User, target: User):
    if target.role.power < agent.role.power:
        return True
    return False

def is_role_hierarchy_respected(agent: User, target_role: Role):
    if agent.role.power > target_role.power:
        if target_role.permissions in agent.permissions:
            return True
    return False

def load_role_users_from_config_section(database_manager, config):
    for role_name in config['Roles'].sections:
        for user_id in config['Roles'][role_name]['UserIds']:
            User(database_manager, int(user_id)).role = \
                Role(database_manager, role_name)
