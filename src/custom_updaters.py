#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import logging
from signal import SIGINT, SIGTERM, SIGABRT
from telegram.ext import Updater

logger = logging.getLogger('OpsecAnonChatBot')


class UpdaterWithStatusMessages(Updater):
    def __init__(self, config, base_url=None, workers=4, bot=None,
                 private_key=None, private_key_password=None,
                 user_sig_handler=None, request_kwargs=None, persistence=None,
                 defaults=None, use_context=False, dispatcher=None,
                 base_file_url=None):
        super().__init__(config["Bot"]["Token"], base_url, workers, bot,
                         private_key, private_key_password, user_sig_handler,
                         request_kwargs, persistence, defaults, use_context,
                         dispatcher, base_file_url)
        self._config = config

    def start_polling(self, poll_interval=0.0, timeout=10, clean=False,
                      bootstrap_retries=-1, read_latency=2.0,
                      allowed_updates=None):
        super().start_polling(poll_interval, timeout, clean, bootstrap_retries,
                              read_latency, allowed_updates)
                              "OpsecAnonChatBot is online")

    def start_webhook(self,
                      listen='127.0.0.1',
                      port=80,
                      url_path='',
                      cert=None,
                      key=None,
                      clean=False,
                      bootstrap_retries=0,
                      webhook_url=None,
                      allowed_updates=None):
        super().start_webhook(listen, port, url_path, cert, key, clean,
                              bootstrap_retries, webhook_url, allowed_updates)
        logger.info(f"Bot started in webhook mode {listen}:{port}{url_path}")

    def stop(self):
        logger.info("Bot shutdown")
        Updater.stop(self)

    def idle(self, stop_signals=(SIGINT, SIGTERM, SIGABRT)):
        super().idle(stop_signals)
