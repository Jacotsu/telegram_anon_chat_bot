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


from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable
import logging
from permissions import Permissions
import database

logger = logging.getLogger(__name__)


@dataclass
class Role:
    def __init__(self,
                 db_man,
                 name: str,
                 permissions: Permissions = Permissions.NONE):

        self._db_man = db_man
        self.name = name
        # Creates role if it doesn't exist

        #if not self._db_man.user_exists(user_id):
        #    self._db_man.create_user(user_id)
        #    self.permissions = permissions
        #    self.captcha_status

    @property
    def permissions(self) -> Permissions:
        return self._db_man.get_role_permissions(self.name)

    @permissions.setter
    def permissions(self, new_permissions: Permissions = Permissions.NONE):
        self._db_man.set_role_permissions(self.name, new_permissions)

    @property
    def power(self) -> int:
        return self._db_man.get_role_power(self.name)

    @power.setter
    def power(self, new_power: int):
        return self._db_man.set_role_power(self.name, new_power)


@dataclass
class DateIntervalLog:
    start_date: datetime
    end_date: datetime

    def __str__(self):
        return f'from {self.start_date} until'


@dataclass
class DateLog:
    date: datetime


@dataclass
class CaptchaStatus:
    _db_man: database.DatabaseManager
    user_id: int

    def __str__(self):
        attribute_values = [
            ("failed_attempt", self.failed_attempts),
            ("total_failed_attempt", self.total_failed_attempts),
            ("passed", self.passed),
            ("creation_time", self.creation_time),
            ("last_try_time", self.last_try_time),
            ("current_value", self.current_value),
        ]
        attribute_values = ", ".join(map(lambda x: f"{x[0]}={x[1]}",
                                         attribute_values))

        return f'{self.__class__}({attribute_values})'

    def __init__(self,
                 database_manager: database.DatabaseManager,
                 user_id: int):
        self._db_man = database_manager
        self.user_id = user_id
        logger.debug(f'Initializing CaptchaStatus for {user_id}')
        try:
            self.failed_attempts
        except ValueError:
            logger.debug(f'No data available for {user_id}, setting default'
                         'values')
            self.failed_attempts = 0
            self.total_failed_attempts = 0
            self.passed = False
            self.creation_time = datetime.utcfromtimestamp(0)
            self.last_try_time = datetime.utcfromtimestamp(0)
            self.current_value = ''
        logger.debug(f'Initialized CaptchaStatus for {user_id}')

    @property
    def failed_attempts(self) -> int:
        return self._db_man.\
                get_user_failed_attempts_from_captcha_status(self.user_id)

    @failed_attempts.setter
    def failed_attempts(self, failed_attempts_no: int):
        self._db_man.set_user_failed_attempts_from_captcha_status(
            self.user_id, failed_attempts_no)

    @property
    def total_failed_attempts(self) -> int:
        return self._db_man.get_user_total_failed_attempts_from_captcha_status(
            self.user_id)

    @total_failed_attempts.setter
    def total_failed_attempts(self, total_failed_attempts_no: int):
        self._db_man.set_user_total_failed_attempts_from_captcha_status(
            self.user_id, total_failed_attempts_no)

    @property
    def passed(self) -> bool:
        return self._db_man.get_user_passed_from_captcha_status(self.user_id)

    @passed.setter
    def passed(self, passed: int = 0):
        self._db_man.set_user_passed_from_captcha_status(self.user_id, passed)

    @property
    def creation_time(self) -> datetime:
        return self._db_man.get_user_current_captcha_creation_time_date(
            self.user_id)

    @creation_time.setter
    def creation_time(self, creation_timedate: datetime = datetime.utcnow()):
        return self._db_man.set_user_current_captcha_creation_time_date(
            self.user_id, creation_timedate)

    @property
    def last_try_time(self) -> datetime:
        return self._db_man.get_user_current_captcha_last_try_time_date(
            self.user_id)

    @last_try_time.setter
    def last_try_time(self, last_try_timedate: datetime = datetime.utcnow()):
        return self._db_man.set_user_current_captcha_last_try_time_date(
            self.user_id, last_try_timedate)

    @property
    def current_value(self) -> str:
        return self._db_man.get_user_current_captcha_value(self.user_id)

    @current_value.setter
    def current_value(self, value: str) -> str:
        return self._db_man.set_user_current_captcha_value(self.user_id, value)


@dataclass
class User:
    _db_man: database.DatabaseManager
    user_id: int

    def __init__(self,
                 db_man,
                 user_id: int,
                 permissions: Permissions = Permissions.NONE):
        self._db_man = db_man
        self.user_id = user_id
        # Creates user if it doesn't exist

        if not self._db_man.user_exists(user_id):
            self._db_man.create_user(user_id)
            self.permissions = permissions
            self.captcha_status

    @property
    def captcha_status(self) -> CaptchaStatus:
        return CaptchaStatus(self._db_man, self.user_id)

    @property
    def permissions(self) -> Permissions:
        return self._db_man.get_user_permissions(self.user_id)

    @permissions.setter
    def permissions(self, new_permissions: Permissions):
        self._db_man.update_user_permissions(self.user_id, new_permissions)

    @property
    def is_banned(self) -> int:
        return self._db_man.is_user_banned(self.user_id)

    @property
    def is_active(self) -> bool:
        return self._db_man.is_user_active(self.user_id)

    def join(self):
        self._db_man.log_join(self.user_id)

    def ban(self, end_date: datetime, reason: str = None,
            start_date: datetime = datetime.utcnow()):
        self._db_man.ban(self.user_id, start_date, end_date, reason)

    def kick(self):
        self._db_man.kick_user(self.user_id)

    def reset_chat_delay(self):
        self._db_man.reset_chat_delay(self.user_id)

    @property
    def chat_delay(self) -> timedelta:
        return self._db_man.get_user_chat_delay(self.user_id)

    @chat_delay.setter
    def chat_delay(self, delta: timedelta):
        if delta > 0:
            self._db_man.set_user_chat_delay(self.user_id, delta)
        else:
            raise ValueError(f'The chat delay delta must be > 0 ({delta})')

    @property
    def role(self) -> Role:
        raise NotImplementedError()

    @role.setter
    def role(self, new_role: Role):
        raise NotImplementedError()

    # Quit is basically the same as kicking
    def quit(self):
        self.kick()

    @property
    def join_quit_log(self) -> Iterable[DateIntervalLog]:
        return self._db_man.get_join_quit_log(self.user_id)

    @property
    def ban_log(self) -> Iterable[DateIntervalLog]:
        return self._db_man.get_ban_log(self.user_id)
