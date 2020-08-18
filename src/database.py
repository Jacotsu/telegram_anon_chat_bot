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

import sqlite3
import threading
from datetime import datetime, timezone
import logging
from typing import Iterable
import queries
import custom_dataclasses
from permissions import Permissions


logger = logging.getLogger(__name__)


class DatabaseManager:
    '''
    An internal class that is used to manage the database
    '''
    def __init__(self, db_path):
        logger.debug("Started database initialization!")
        self._db_path = db_path
        self._conn = {}
        self._get_connection()
        logger.debug("Database initialized!")

    def _get_connection(self):
        try:
            return self._conn[threading.get_ident()]
        except KeyError:
            self._conn[threading.get_ident()] = sqlite3.connect(self._db_path)
            self._conn[threading.get_ident()].row_factory = sqlite3.Row
            with self._conn[threading.get_ident()] as conn:
                table_creation_queries = [
                    queries.CREATE_USERS_TABLE,
                    queries.CREATE_JOIN_LOG_TABLE,
                    queries.CREATE_QUIT_LOG_TABLE,
                    queries.CREATE_PERMISSIONS_TABLE,
                    queries.CREATE_ROLES_TABLE,
                    queries.CREATE_USER_ASSIGNED_ROLES,
                    queries.CREATE_CAPTCHA_LOG_TABLE,
                    queries.CREATE_ACTIVE_CAPTCHA_TABLE,
                    queries.CREATE_BAN_LOG_TABLE
                ]

                view_creation_queries = [
                    queries.CREATE_ACTIVE_USERS_VIEW,
                    queries.CREATE_BANNED_USERS_VIEW
                ]
                for query in table_creation_queries + view_creation_queries:
                    conn.execute(query)
            return self._conn[threading.get_ident()]

    @staticmethod
    def _get_single_row_from_cursor(cursor, error_message):
        # row count is bugged
        for row in cursor:
            return row
        raise ValueError(error_message)

    def _execute_simple_get_query(self, query, param_dict: dict = {}):
        with self._get_connection() as conn:
            logger.debug(f"Executing query {query} \n with {param_dict}")
            cursor = conn.execute(query, param_dict)
            logger.debug(f"Query executed")
            return cursor

    def _execute_simple_set_query(self, query, param_dict):
        with self._get_connection() as conn:
            logger.debug(f"Executing query {query} \n with {param_dict}")
            conn.execute(query, param_dict)
            logger.debug(f"Query executed")

    def _execute_get_query_for_1_row(self,
                                     query,
                                     param_dict: dict = {},
                                     error_message: str = ''):
        '''
        @returns The first row of a cursor
        @raises ValueError if no row is available
        '''
        row = self._get_single_row_from_cursor(
            self._execute_simple_get_query(
                query,
                param_dict),
            error_message
        )
        return row

    def get_active_users(self):
        '''
        @returns An iterable of User instances
        '''
        logger.debug('Getting active users')
        cursor = self._execute_simple_get_query(queries.GET_ACTIVE_USERS)
        return map(lambda x: custom_dataclasses.User(self,
                                                     user_id=x['user_id']),
                   cursor)

    def get_user(self, user_id):
        '''
        @returns An User object
        '''
        logging.debug(f'Getting user {user_id}')

        row = self._execute_get_query_for_1_row(
            queries.GET_USER,
            {'user_id': user_id},
            f'User id: {user_id} is not present in the users database'
        )

        return custom_dataclasses.User(
            self,
            user_id,
            self.get_user_permissions(user_id))

    def user_exists(self, user_id):
        try:
            row = self._execute_get_query_for_1_row(
                queries.DOES_USER_EXIST,
                {'user_id': user_id},
                f'User id: {user_id} is not present in the users database'
            )
            if row[0]:
                return True
            else:
                return False
        except ValueError:
            return False

    def is_user_active(self, user_id):
        try:
            row = self._execute_get_query_for_1_row(
                queries.IS_USER_ACTIVE,
                {'user_id': user_id},
                f'User id: {user_id} is not present in the active users '
                'database'
            )
            if row[0]:
                return True
            else:
                return False
        except ValueError:
            return False


    def create_user(self, user_id):
        logger.debug(f'Creating user {user_id}')
        self._execute_simple_set_query(
            queries.CREATE_USER,
            {'user_id': user_id}
        )
        logger.debug(f'Created user {user_id}')

    def log_join(self, user_id: int,
                 date_time: datetime = None):
        if not date_time:
            date_time = datetime.utcnow()
        self._execute_simple_set_query(
            queries.INSERT_JOIN_ENTRY,
            {'user_id': user_id,
             'unix_join_date': int(date_time.replace(tzinfo=timezone.utc)
                                   .timestamp()*1E6)}
        )

    def log_quit(self, user_id,
                 date_time: datetime = None):
        if not date_time:
            date_time = datetime.utcnow()
        self._execute_simple_set_query(
            queries.INSERT_QUIT_ENTRY,
            {'user_id': user_id,
             'unix_quit_date': int(date_time.replace(tzinfo=timezone.utc)
                                   .timestamp()*1E6)}
        )

    def get_join_quit_log(self, user_id):
        with self._get_connection() as conn:
            cursor = conn.execute(queries.GET_USER_JOIN_QUIT_LOG,
                                  {'user_id': user_id})

            return map (lambda x: custom_dataclasses.
                        DateIntervalLog(x['join_date']/1E6,
                                        x['quit_date'])/1E6, cursor)

    def get_ban_log(self, user_id: int) -> Iterable:
        with self._get_connection() as conn:
            cursor = conn.execute(queries.GET_USER_BAN_LOG,
                                  {'user_id': user_id})

            return map(lambda x: custom_dataclasses.
                       DateIntervalLog(x['start_date']/1E6,
                                       x['end_date'])/1E6, cursor)

# ------------------------------ [MODERATION] ---------------------------------


    def kick_user(self, user_id: int):
        self.log_quit(user_id)

    def ban(self,
            user_id: int,
            start_date: datetime = datetime.utcnow(),
            end_date: datetime = datetime.max,
            reason: str = ''):
        if start_date > end_date:
            raise ValueError('End date must be greater than start date')

        self._execute_simple_set_query(
            queries.BAN_USER,
            {'user_id': user_id,
             'unix_start_date': int(start_date.replace(tzinfo=timezone.utc)
                                    .timestamp()*1E6),
             'unix_end_date': int(start_date.replace(tzinfo=timezone.utc)
                                  .timestamp()*1E6),
             'reason': reason
             }
        )

    def is_user_banned(self, user_id: int) -> int:
        try:
            row = self._execute_get_query_for_1_row(
                queries.IS_USER_BANNED,
                {'user_id': user_id}
            )
        except ValueError:
            return False
        if row['banned']:
            return True

# -------------------------- [CAPTCHA MANAGEMENT] -----------------------------

    def get_user_failed_attempts_from_captcha_status(self,
                                                     user_id: int) -> int:
        row = self._execute_get_query_for_1_row(
            queries.GET_USER_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS,
            {'user_id': user_id},
            f'User id: {user_id} is not present in the captcha status table'
        )
        return int(row['failed_attempts'])

    def get_user_total_failed_attempts_from_captcha_status(
            self,
            user_id: int) -> int:

        row = self._execute_get_query_for_1_row(
            queries.GET_USER_TOTAL_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS,
            {'user_id': user_id},
            f'User id: {user_id} is not present in the captcha status table'
        )
        return int(row['total_failed_attempts'])

    def get_user_passed_from_captcha_status(self, user_id: int) -> bool:

        row = self._execute_get_query_for_1_row(
            queries.GET_USER_PASSED_FROM_CAPTCHA_STATUS,
            {'user_id': user_id},
            f'User id: {user_id} is not present in the captcha status table'
        )
        if row["passed"]:
            return True
        else:
            return False

    def get_user_current_captcha_value(self, user_id: int) -> str:
        row = self._execute_get_query_for_1_row(
            queries.GET_USER_CURRENT_CAPTCHA_VALUE,
            {'user_id': user_id},
            f'User id: {user_id} is not present in the captchas table'
        )
        return str(row["current_value"])

    def get_user_current_captcha_creation_time_date(
            self,
            user_id: int) -> datetime:
        row = self._execute_get_query_for_1_row(
            queries.GET_USER_CURRENT_CAPTCHA_CREATION_TIME_DATE,
            {'user_id': user_id},
            f'User id: {user_id} is not present in the captchas table'
        )
        return datetime.utcfromtimestamp(row["unix_creation_time_date"]/1E6)

    def get_user_current_captcha_last_try_time_date(
            self,
            user_id: int) -> datetime:

        row = self._execute_get_query_for_1_row(
            queries.GET_USER_CURRENT_CAPTCHA_LAST_TRY_TIME_DATE,
            {'user_id': user_id},
            f'User id: {user_id} is not present in the captchas table'
        )

        return datetime.utcfromtimestamp(row["unix_last_try_time_date"]/1E6)

    def set_user_failed_attempts_from_captcha_status(self,
                                                     user_id: int,
                                                     failed_attempts_no: int):
        if failed_attempts_no >= 0:
            self._execute_simple_set_query(
                queries.SET_USER_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS,
                {'user_id': user_id,
                 'failed_attempts': failed_attempts_no},
            )
        else:
            raise ValueError("failed_attempts_no must be >= 0")

    def set_user_total_failed_attempts_from_captcha_status(
            self,
            user_id: int,
            total_failed_attempts_no: int):

        if total_failed_attempts_no >= 0:
            self._execute_simple_set_query(
                queries.SET_USER_TOTAL_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS,
                {'user_id': user_id,
                 'total_failed_attempts': total_failed_attempts_no},
            )
        else:
            raise ValueError("total_failed_attempts_no must be >= 0")

    def set_user_passed_from_captcha_status(self, user_id: int, passed: int):
        self._execute_simple_set_query(
            queries.SET_USER_PASSED_FROM_CAPTCHA_STATUS,
            {'user_id': user_id, 'passed': passed == True}
        )

    def set_user_current_captcha_value(self, user_id: int, value: str):
        self._execute_simple_set_query(
            queries.SET_USER_CURRENT_CAPTCHA_VALUE,
            {'user_id': user_id, 'current_value': value}
        )

    def set_user_current_captcha_creation_time_date(
            self,
            user_id: int,
            creation_time_date: datetime = None):

        if not creation_time_date:
            creation_time_date = datetime.utcnow()
        self._execute_simple_set_query(
            queries.SET_USER_CURRENT_CAPTCHA_CREATION_TIME_DATE,
            {'user_id': user_id,
             'unix_creation_time_date': int(creation_time_date
                                            .replace(tzinfo=timezone.utc)
                                            .timestamp()*1E6)
             }
        )

    def set_user_current_captcha_last_try_time_date(
            self,
            user_id: int,
            last_try_time_date: datetime = None):

        if not last_try_time_date:
            last_try_time_date = datetime.utcnow()
        self._execute_simple_set_query(
            queries.SET_USER_CURRENT_CAPTCHA_LAST_TRY_TIME_DATE,
            {'user_id': user_id,
             'unix_last_try_time_date': int(last_try_time_date
                                            .replace(tzinfo=timezone.utc)
                                            .timestamp()*1E6)
             }
        )

# ------------------------------ [PERMISSIONS] --------------------------------
    def update_user_permissions(self,
                                user_id: int,
                                permissions: Permissions = Permissions.NONE):
        logger.debug(f'Setting user {user_id} permissions to {permissions}')
        self._execute_simple_set_query(
            queries.UPDATE_USER_PERMISSIONS,
            {'user_id': user_id,
             'permissions': int(permissions)}
        )
        logger.debug(f'Set user {user_id} permissions to {permissions}')

    def get_user_permissions(self, user_id: int) -> Permissions:
        row = self._execute_get_query_for_1_row(
            queries.GET_USER_PERMISSIONS,
            {'user_id': user_id},
            f'User id: {user_id} is not present in the permissions table'
        )
        return Permissions(row["permissions"])

# -------------------------------- [ROLES] ------------------------------------

    def register_role(self, role):
        raise NotImplementedError

    def delete_role(self, role):
        raise NotImplementedError

    def set_role(self, user_id, role):
        raise NotImplementedError
