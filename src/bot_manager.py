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
from message_broker import MessageBroker
from command_executor import CommandExecutor
from captcha_manager import CaptchaManager
from database import DatabaseManager
from custom_dataclasses import Role
from security import load_role_users_from_config_section

logger = logging.getLogger(__name__)


class BotManager:
    def __init__(self, config):
        self._config = config
        self._db_man = DatabaseManager(config["Bot"]["DatabasePath"])
        if logger.getEffectiveLevel == logging.DEBUG:
            self._updater = Updater(config["Bot"]["Token"],
                                    workers=1, use_context=True)
        else:
            self._updater = Updater(config["Bot"]["Token"], use_context=True)
        self._captcha_manager = CaptchaManager(config, self._db_man)
        self._msg_broker = MessageBroker(self._updater,
                                         self._db_man,
                                         self._captcha_manager,
                                         self._config)
        self._cmd_executor = CommandExecutor(
            self._config,
            self._updater,
            self._db_man,
            self._msg_broker,
            self._captcha_manager)

        Role.init_roles_from_config(self._db_man, config)
        load_role_users_from_config_section(self._db_man, config)

    def start(self):
        '''
        Starts the bot
        '''
        if self._config["Bot"]["UpdateMethod"] == 'polling':
            logger.info("Bot started in polling mode")
            self._updater.bot.delete_webhook()
            self._updater.start_polling(1)
        else:
            if self._config["Bot"]["Webhook"]["UrlPath"]:
                self._updater.start_webhook(
                    listen=self._config["Bot"]["Webhook"]["ListenIp"],
                    port=self._config["Bot"]["Webhook"]["Port"],
                    url_path=self._config["Bot"]["Webhook"]["UrlPath"])
                self._updater.bot.set_webhook(
                    self._config["Bot"]["Webhook"]["WebhookUrl"])

                logger.info("Bot started in webhook mode"
                            f"{self._config['Bot']['ListenIp']}:"
                            f"{self._config['Bot']['Port']}"
                            f"{self._config['Bot']['UrlPath']}")

            else:
                raise ValueError("The webhook UrlPath is empty")

        self._msg_broker.broadcast_message('Bot started')

    def stop(self):
        '''
        Stops the bot
        '''
        self._msg_broker.broadcast_message('Bot stopped')
        self._updater.stop()
        logger.info("Bot stopped")

    def idle(self):
        '''
        Keeps the bot running until a SIGINT is received
        '''
        self._updater.idle()
