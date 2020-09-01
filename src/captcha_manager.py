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
from custom_exceptions import MaxCaptchaTriesError, CaptchaFloodError


logger = logging.getLogger(__name__)


def ban_user_and_raise_max_tries(user: User, duration):
    now = datetime.utcnow()
    user.ban(end_date=now + duration, reason='Too many captcha failures')
    logger.info(
        f'{user} has been banned until {now + duration} for failing captcha '
        'auth too may times')
    raise MaxCaptchaTriesError(
        f'You have been banned until {now+duration}'
        ' for failing the captcha'
        'authentication too many times',
        is_ban=True,
        end_date=now + duration
    )


def kick_user_and_raise_max_tries(user: User):
    user.kick()
    logger.info(f'{user} has been kicked for failing captcha auth too may '
                'times')
    raise MaxCaptchaTriesError(
        'You have been kicked for failing the captcha authentication too '
        'many times',
        is_kick=True
    )


class CaptchaManager:
    def __init__(self, config, database_manager: DatabaseManager):
        action_map = {
            'kick': lambda x, y: kick_user_and_raise_max_tries(x),
            'ban': ban_user_and_raise_max_tries,
            'none': lambda x, y: None
        }

        self._config = config
        self._db_man = database_manager
        self.delay = timedelta(
            seconds=timeparse(
                self._config["Captcha"]["TimeDelayBetweenAttempts"]
            )
        )

        self.action_for_failure = action_map[
            self._config["Captcha"]["ActionOnFailedCaptcha"].lower()
        ]

        self.ban_delay = timedelta(
            seconds=timeparse(
                self._config["Captcha"]["FailedCaptchaBanDuration"]
            )
        )

        self.captcha_expiration_delay = timedelta(
            seconds=timeparse(self._config["Captcha"]["ExpirationTime"])
        )

        self.max_tries = int(self._config["Captcha"]["MaxCaptchaTries"])

        self._last_attempt_dict = {}

    def start_captcha_session(self, user: User):
        captcha_status = user.captcha_status
        creation_time = captcha_status.creation_time
        now = datetime.utcnow()

        if user.captcha_status.failed_attempts % \
           int(self._config["Captcha"]["FailuresToGenerateNewCaptcha"]) == 0 \
           or now - creation_time > self.captcha_expiration_delay:
            self._generate_captcha_value(user)

            return self.get_captcha_image(user)
        return None

    def submit_captcha(self, user: User, value: str):
        captcha_status = user.captcha_status
        last_attempt = captcha_status.last_try_time
        now = datetime.utcnow()
        logger.debug(f'{user} submitted {value} actual value is '
                     f'{user.captcha_status.current_value}')

        if now - last_attempt > self.delay:
            captcha_status.last_try_time = now
            if captcha_status.current_value == value.upper():
                captcha_status.failed_attempts = 0
                captcha_status.passed = True
                captcha_status.current_value = ''
            else:
                captcha_status.total_failed_attempts += 1
                captcha_status.failed_attempts += 1
                if captcha_status.failed_attempts > self.max_tries:
                    captcha_status.failed_attempts = 0
                    captcha_status.current_value = ''
                    self.action_for_failure(user, now + self.ban_delay)
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
