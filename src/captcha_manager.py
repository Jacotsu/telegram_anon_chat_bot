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
    def __init__(self, reason, is_ban=False, is_kick=False, end_date=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reason = reason
        self.is_ban = is_ban
        self.is_kick = is_kick
        self.end_date = end_date


class CaptchaFloodError(Exception):
    pass


class CaptchaManager:
    def __init__(self, config, database_manager: DatabaseManager):
        self._config = config
        self._db_man = database_manager
        self._last_attempt_dict = {}

    def start_captcha_session(self, user: User):
        captcha_status = user.captcha_status
        creation_time = captcha_status.creation_time
        now = datetime.utcnow()
        time_delta = timedelta(seconds=timeparse(self._config["Captcha"]
                                                 ["ExpirationTime"]))

        if user.captcha_status.failed_attempts % \
           int(self._config["Captcha"]["FailuresToGenerateNewCaptcha"]) == 0 \
           or now - creation_time > time_delta:
            self._generate_captcha_value(user)

        return self.get_captcha_image(user)

    def submit_captcha(self, user: User, value: str):
        captcha_status = user.captcha_status
        last_attempt = captcha_status.last_try_time
        now = datetime.utcnow()
        logger.debug(f'{user} submitted {value} actual value is '
                     f'{user.captcha_status.current_value}')

        action_for_failure = self._config["Captcha"]["ActionOnFailedCaptcha"]
        ban_time_delta = self._config["Captcha"]["FailedCaptchaBanDuration"]

        time_delta = timedelta(seconds=timeparse(self._config["Captcha"]
                                                 ["TimeDelayBetweenAttempts"]))

        if now - last_attempt > time_delta:
            captcha_status.last_try_time = now
            if captcha_status.current_value == value.upper():
                captcha_status.failed_attempts = 0
                captcha_status.passed = True
                captcha_status.current_value = ''
            else:
                captcha_status.total_failed_attempts += 1
                captcha_status.failed_attempts += 1
                if captcha_status.failed_attempts > int(self._config["Captcha"]
                   ["MaxCaptchaTries"]):
                    captcha_status.failed_attempts = 0
                    captcha_status.current_value = ''

                    if action_for_failure.lower() == 'ban':
                        user.ban(end_date=now + ban_time_delta,
                                 reason='Too many captcha failures')
                        raise MaxCaptchaTriesError(
                            f'You have been banned until {now+time_delta}'
                            ' for failing the captcha'
                            'authentication too many times',
                            is_ban=True,
                            end_date=now + ban_time_delta
                        )
                        raise MaxCaptchaTriesError(now + time_delta)
                    elif action_for_failure.lower() == 'kick':
                        user.kick()
                        raise MaxCaptchaTriesError(
                            'You have been kicked for failing the captcha'
                            'authentication too many times',
                            is_kick=True
                        )
        else:
            raise CaptchaFloodError()

    def _generate_captcha_value(self, user: User, length: int = 8):
        user.captcha_status.current_value = \
                ''.join(random.choices(string.ascii_uppercase +
                                       string.digits, k=length))
        user.captcha_status.creation_time = datetime.utcnow()

    def get_captcha_image(self, user: User):
        image = ImageCaptcha(width=400, height=200)
        logger.debug('Generate captcha image from '
                     f'{user.captcha_status.current_value}')
        return image.generate(user.captcha_status.current_value)
