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
import random
import string
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
from captcha.image import ImageCaptcha
from custom_dataclasses import User
from database import DatabaseManager


logger = logging.getLogger(__name__)


class MaxCaptchaTriesError(Exception):
    def __init__(self, end_date: datetime, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.end_date = end_date


class CaptchaFloodError(Exception):
    pass


class CaptchaManager:
    def __init__(self, config, database_manager: DatabaseManager):
        self._config = config
        self._db_man = database_manager

    def start_captcha_session(self, user: User):
        if user.captcha_status.failed_attempts % int(self._config["Captcha"]
           ["FailuresToGenerateNewCaptcha"]) == 0:
            self._generate_captcha_value(user)
            return self.get_captcha_image(user)
        else:
            return None

    def submit_captcha(self, user: User, value: str):
        captcha_status = user.captcha_status
        last_attempt = captcha_status.last_try_time
        now = datetime.utcnow()
        logger.debug(f'{user} submitted {value} actual value is '
                     f'{user.captcha_status.current_value}')

        time_delta = timedelta(seconds=timeparse(self._config["Captcha"]
                                                 ["TimeDelayBetweenAttempts"]))

        if now - last_attempt > time_delta:
            captcha_status.last_try_time = now
            print(captcha_status)
            if captcha_status.current_value == value.upper():
                captcha_status.failed_attempts = 0
                captcha_status.passed = True
                captcha_status.current_value = ''
            else:
                captcha_status.failed_attempts += 1
                captcha_status.total_failed_attempts += 1
                if captcha_status.failed_attempts > int(self._config["Captcha"]
                   ["MaxCaptchaTries"]):
                    captcha_status.failed_attempts = 0
                    captcha_status.current_value = ''
                    raise MaxCaptchaTriesError(now + time_delta)
        else:
            raise CaptchaFloodError()

    def _generate_captcha_value(self, user: User):
        user.captcha_status.current_value = \
                ''.join(random.choices(string.ascii_uppercase +
                                       string.digits, k=8))
        user.captcha_status.creation_time = datetime.utcnow()

    def get_captcha_image(self, user: User):
        image = ImageCaptcha(width=400, height=200)
        print(user.captcha_status.current_value + '\n\n\n\n\n\n\n\n')
        logger.debug('Generate captcha image from '
                     f'{user.captcha_status.current_value}')
        return image.generate(user.captcha_status.current_value)
