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
from telegram import Update
from custom_dataclasses import User, Role
from utils import user_log_str

logger = logging.getLogger(__name__)


def execute_if_hierarchy_is_respected(
    agent: User,
    receiver: User,
    function,
    update: Update,
    agent_message_on_success: str = None,
    agent_message_on_failure: str = None,
    log_message_on_success: str = None,
    log_message_on_failure: str = None,
    callback_on_success = None,
    callback_on_failure = None
):

    if receiver.role.power < agent.role.power:
        function()
        if agent_message_on_success:
            update.message.reply_text(agent_message_on_success)
        if log_message_on_success:
            logger.info(log_message_on_success)
        if callback_on_success:
            callback_on_success()
    else:
        if agent_message_on_failure:
            update.message.reply_text(agent_message_on_failure)
        if log_message_on_failure:
            logger.warning(log_message_on_failure)
        if callback_on_failure:
            callback_on_failure()

def execute_if_role_hierarchy_is_preserved(
    agent: User,
    target_role: Role,
    function,
    update: Update,
    agent_message_on_success: str = None,
    log_message_on_success: str = None,
    callback_on_success = None,
    callback_on_failure = None
):
    if agent.role.power > target_role.power:
        if target_role.permissions in agent.permissions:
            function()
            if callback_on_success:
                callback_on_success()
        else:
            update.message.reply_text(
                'You can\'t set a role whose permissions are '
                'more than yours'
            )
            logger.warning(
                f'{user_log_str(update)} has tried to set a role '
                'whose permissions are higher than his'
            )
    else:
        update.message.reply_text(
            'You can\'t set a role whose power is higher '
            'than yours as default'
        )
        logger.warning(
            f'{user_log_str(update)} has tried to set a role '
            'whose power is higher than his as default role'
        )

    if callback_on_failure:
        callback_on_failure()



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
