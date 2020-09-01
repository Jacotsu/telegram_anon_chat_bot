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
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable
from telegram import User as tg_User
import database
from permissions import Permissions
from utils import get_permissions_from_config_section
from custom_exceptions import UserResolverError

logger = logging.getLogger(__name__)


@dataclass
class Role:
    def __init__(self,
                 db_man,
                 name: str,
                 power: int = 0,
                 permissions: Permissions = Permissions.NONE):

        self._db_man = db_man
        self.name = name

        # Creates role if it doesn't exist
        if not self._db_man.does_role_exist(name):
            self._db_man.create_role(name, power)
            self.permissions = permissions

        if permissions not in (Permissions.NONE, self.permissions):
            self.permissions = permissions

        if power > 0 and power not in (0, self.power):
            self.power = power

    def __str__(self):
        return f'{self.name}({self.power}): {str(self.permissions)}'

    @classmethod
    def init_roles_from_config(cls, database_manager, config):
        for role_name in config['Roles'].sections:
            Role(
                database_manager,
                role_name,
                int(config['Roles'][role_name]['Power']),
                get_permissions_from_config_section(
                    config['Roles'][role_name]['Permissions']
                )
            )

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

    def delete(self):
        self._db_man.delete_role(self.name)


@dataclass
class DateInterval:
    start_date: datetime
    end_date: datetime
    time_format: str = '%x %X'

    def __str__(self):
        fmt_start_date = self.start_date.strftime(self.time_format) \
            if self.start_date else None
        fmt_end_date = self.end_date.strftime(self.time_format) \
            if self.end_date else None
        return f'{fmt_start_date} -> {fmt_end_date}'


@dataclass
class BanLogEntry:
    interval: DateInterval
    reason: str

    def __str__(self):
        return f'{str(self.interval)}: {self.reason}'


@dataclass
class CaptchaStatus:
    _db_man: 'database.DatabaseManager'
    _user: 'User'

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
                 database_manager: 'database.DatabaseManager',
                 user: 'User'):
        self._db_man = database_manager
        self._user = user
        logger.debug(f'Initializing CaptchaStatus for {user}')
        try:
            self.failed_attempts
        except ValueError:
            logger.debug(f'No data available for {user}, setting default'
                         'values')
            self.failed_attempts = 0
            self.total_failed_attempts = 0
            self.passed = False
            self.creation_time = datetime.utcfromtimestamp(0)
            self.last_try_time = datetime.utcfromtimestamp(0)
            self.current_value = ''
        logger.debug(f'Initialized CaptchaStatus for {user}')

    @property
    def failed_attempts(self) -> int:
        return self._db_man.\
                get_user_failed_attempts_from_captcha_status(self._user.id)

    @failed_attempts.setter
    def failed_attempts(self, failed_attempts_no: int):
        self._db_man.set_user_failed_attempts_from_captcha_status(
            self._user.id, failed_attempts_no)

    @property
    def total_failed_attempts(self) -> int:
        return self._db_man.get_user_total_failed_attempts_from_captcha_status(
            self._user.id)

    @total_failed_attempts.setter
    def total_failed_attempts(self, total_failed_attempts_no: int):
        self._db_man.set_user_total_failed_attempts_from_captcha_status(
            self._user.id, total_failed_attempts_no)

    @property
    def passed(self) -> bool:
        return self._db_man.get_user_passed_from_captcha_status(self._user.id)

    @passed.setter
    def passed(self, passed: int = 0):
        self._db_man.set_user_passed_from_captcha_status(self._user.id, passed)

    @property
    def creation_time(self) -> datetime:
        return self._db_man.get_user_current_captcha_creation_time_date(
            self._user.id)

    @creation_time.setter
    def creation_time(self, creation_timedate: datetime = datetime.utcnow()):
        return self._db_man.set_user_current_captcha_creation_time_date(
            self._user.id, creation_timedate)

    @property
    def last_try_time(self) -> datetime:
        return self._db_man.get_user_current_captcha_last_try_time_date(
            self._user.id)

    @last_try_time.setter
    def last_try_time(self, last_try_timedate: datetime = datetime.utcnow()):
        return self._db_man.set_user_current_captcha_last_try_time_date(
            self._user.id, last_try_timedate)

    @property
    def current_value(self) -> str:
        return self._db_man.get_user_current_captcha_value(self._user.id)

    @current_value.setter
    def current_value(self, value: str) -> str:
        return self._db_man.set_user_current_captcha_value(self._user.id,
                                                           value)


@dataclass
class User:
    _db_man: 'database.DatabaseManager'
    user_id: int

    def __init__(self,
                 db_man,
                 user_id_or_user_obj,
                 permissions: Permissions = Permissions.NONE,
                 resolver: 'UserResolver' = None,
                 role_name_or_role: 'Role' = 'default'
                 ):
        self._db_man = db_man
        self.first_name = ''
        self.last_name = ''
        self.username = ''

        if isinstance(user_id_or_user_obj, int) and user_id_or_user_obj > 0:
            self.id = user_id_or_user_obj
            self._fmt_str = '[{id}]'
            try:
                if resolver:
                    info = resolver.get_user_info(self.id)
                    self.first_name = info['first_name']
                    self.last_name = info['last_name']
                    self.username = info['username']
                    self._fmt_str = '[{first_name}{last_name}{username}({id})]'

            except UserResolverError:
                pass

        elif isinstance(user_id_or_user_obj, tg_User):
            self.first_name = user_id_or_user_obj.first_name
            self.last_name = user_id_or_user_obj.last_name
            self.username = user_id_or_user_obj.username
            self.id = user_id_or_user_obj.id
            self._fmt_str = '[{first_name}{last_name}{username}({id})]'
        else:
            raise ValueError('Invalid user id/user object '
                             f'{user_id_or_user_obj}')

        # Creates user if it doesn't exist
        if not self._db_man.user_exists(self.id):
            self._db_man.create_user(self.id)
            if isinstance(role_name_or_role, str):
                self.role = Role(self._db_man, role_name_or_role)
            elif isinstance(role_name_or_role, Role):
                self.role = role_name_or_role
            self.permissions = permissions
            self.captcha_status

    def __str__(self):
        data = {
            'first_name': f'{self.first_name} ',
            'last_name': f'{self.last_name} ',
            'username': f'@{self.username} ',
            'id': self.id
        }
        return self._fmt_str.format_map(data)

    def __eq__(self, other):
        if isinstance(other, User):
            return self.id == other.id
        return False

    @property
    def captcha_status(self) -> CaptchaStatus:
        return CaptchaStatus(self._db_man, self)

    @property
    def permissions(self) -> Permissions:
        return self._db_man.get_user_permissions(self.id)

    @permissions.setter
    def permissions(self, new_permissions: Permissions):
        self._db_man.update_user_permissions(self.id, new_permissions)

    @property
    def is_banned(self) -> int:
        return self._db_man.is_user_banned(self.id)

    @property
    def is_active(self) -> bool:
        return self._db_man.is_user_active(self.id)

    @property
    def chat_delay(self) -> timedelta:
        return self._db_man.get_user_chat_delay(self.id)

    @chat_delay.setter
    def chat_delay(self, delta: timedelta):
        if delta > 0:
            self._db_man.set_user_chat_delay(self.id, delta)
        else:
            raise ValueError(f'The chat delay delta must be > 0 ({delta})')

    @property
    def role(self) -> Role:
        return self._db_man.get_user_role(self.id)

    @role.setter
    def role(self, new_role: Role):
        self._db_man.set_user_role(self.id, new_role.name)

    @property
    def join_quit_log(self) -> Iterable[DateInterval]:
        return self._db_man.get_join_quit_log(self.id)

    @property
    def ban_log(self) -> Iterable[BanLogEntry]:
        return self._db_man.get_ban_log(self.id)

    def join(self):
        self._db_man.log_join(self.id)

    def ban(self, reason: str = '', end_date: datetime = datetime.max,
            start_date: datetime = None):
        if not start_date:
            start_date = datetime.utcnow()
        self._db_man.ban(self.id, start_date, end_date, reason)
        self.quit()

    def unban(self, reason: str = ''):
        self._db_man.unban(self.id, reason)

    def kick(self):
        self._db_man.kick_user(self.id)

    def reset_chat_delay(self):
        self._db_man.reset_chat_delay(self.id)

    # Quit is basically the same as kicking
    def quit(self):
        self.kick()
