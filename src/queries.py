#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# OpsecAnonChatBot is a telegram bot whose main function is to manage an
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


# ----------------------------[TABLES CREATION]--------------------------------
CREATE_USERS_TABLE = '''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY
    ) WITHOUT ROWID;
'''

CREATE_JOIN_LOG_TABLE = '''
    CREATE TABLE IF NOT EXISTS join_log (
        user_id INTEGER,
        unix_join_date INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
'''
CREATE_QUIT_LOG_TABLE = '''
    CREATE TABLE IF NOT EXISTS quit_log (
        user_id INTEGER,
        unix_quit_date INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
'''

CREATE_PERMISSIONS_TABLE = '''
    CREATE TABLE IF NOT EXISTS permissions (
        user_id INTEGER PRIMARY KEY,
        permissions INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    ) WITHOUT ROWID;
'''

CREATE_ROLES_TABLE = '''
    CREATE TABLE IF NOT EXISTS roles (
        role_id INTEGER PRIMARY KEY,
        role_name TEXT,
        role_power INTEGER NOT NULL DEFAULT 0,
        permissions INTEGER NOT NULL DEFAULT 0
    );
'''

# 1 role per user
CREATE_USER_ASSIGNED_ROLES = '''
    CREATE TABLE IF NOT EXISTS assigned_roles (
        user_id INTEGER PRIMARY KEY,
        role_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(role_id) REFERENCES roles(role_id)
    ) WITHOUT ROWID;
'''

CREATE_CAPTCHA_LOG_TABLE = '''
    CREATE TABLE IF NOT EXISTS captcha_status (
        user_id INTEGER PRIMARY KEY,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        total_failed_attempts INTEGER NOT NULL DEFAULT 0,
        passed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    ) WITHOUT ROWID;
'''

CREATE_ACTIVE_CAPTCHA_TABLE = '''
    CREATE TABLE IF NOT EXISTS active_captcha_storage (
        user_id INTEGER PRIMARY KEY,
        current_value TEXT NOT NULL DEFAULT '',
        unix_creation_time_date INTEGER NOT NULL DEFAULT 0,
        unix_last_try_time_date INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    ) WITHOUT ROWID;
'''

CREATE_BAN_LOG_TABLE = '''
    CREATE TABLE IF NOT EXISTS ban_log (
        user_id INTEGER,
        unix_start_date INTEGER NOT NULL,
        unix_end_date INTEGER NOT NULL DEFAULT 9223372036854775807,
        reason TEXT DEFAULT "",
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
'''

# ----------------------------[VIEWS CREATION]---------------------------------

# Selects only the users where their joined date is more recent than their
# quit date (this means that they rejoined or first joined)
CREATE_ACTIVE_USERS_VIEW = '''
    CREATE VIEW IF NOT EXISTS active_users (user_id)
    AS
    SELECT
        user_id
    FROM
        users
    INNER JOIN join_log USING (user_id)
    LEFT JOIN quit_log USING (user_id)
    GROUP BY user_id
    HAVING IFNULL(MAX(unix_join_date), 0) > IFNULL(MAX(unix_quit_date), 0);
'''

CREATE_BANNED_USERS_VIEW = '''
    CREATE VIEW IF NOT EXISTS banned_users (user_id,
        unix_start_date, unix_end_date)
        AS
        SELECT
            user_id, unix_start_date, unix_end_date
        FROM
            ban_log
        WHERE
        strftime("%s", 'now')*1000000 >= IFNULL(unix_start_date, 0)
        AND strftime("%s", 'now')*1000000 <=
        IFNULL(unix_end_date, 9223372036854775807);
'''

# ---------------------------[USER MANAGEMENT]---------------------------------

CREATE_USER = '''
    INSERT INTO users(user_id)
    VALUES (:user_id);
'''

DOES_USER_EXIST = '''
    SELECT
        CASE WHEN (
            SELECT user_id
            FROM users
            WHERE user_id = :user_id)
        THEN
            1
        ELSE
            0
        END;
'''

GET_ACTIVE_USERS = '''
    SELECT user_id
    FROM active_users;
'''

GET_USER = '''
    SELECT user_id
    FROM users
    WHERE user_id = :user_id;
'''


BAN_USER = '''
    INSERT INTO ban_log (user_id, unix_start_date, unix_end_date, reason)
    VALUES (:user_id, :unix_start_date, :unix_end_date, :reason);
'''

IS_USER_BANNED = '''
SELECT 1 as banned
FROM banned_users
WHERE user_id = :user_id;
'''

IS_USER_ACTIVE = '''
    SELECT
        CASE WHEN (
            SELECT 1
            FROM active_users
            WHERE user_id = :user_id)
        THEN
            1
        ELSE
            0
        END;
'''

# ------------------------ [PERMISSIONS] ---------------------

UPDATE_USER_PERMISSIONS = '''
    REPLACE INTO permissions(user_id, permissions)
    VALUES (:user_id, :permissions);
'''

GET_USER_PERMISSIONS = '''
    SELECT permissions
    FROM permissions
    WHERE user_id = :user_id;
'''

# ----------------------- [CAPTCHA] --------------------------

SET_USER_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS = '''
    REPLACE INTO captcha_status (user_id, failed_attempts)
    VALUES (:user_id, :failed_attempts);
'''

SET_USER_TOTAL_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS = '''
    REPLACE INTO captcha_status (user_id, total_failed_attempts)
    VALUES (:user_id, :total_failed_attempts);
'''

SET_USER_PASSED_FROM_CAPTCHA_STATUS = '''
    REPLACE INTO captcha_status (user_id, passed)
    VALUES (:user_id, :passed);
'''

GET_USER_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS = '''
    SELECT failed_attempts
    FROM captcha_status
    WHERE user_id = :user_id;
'''

GET_USER_TOTAL_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS = '''
    SELECT total_failed_attempts
    FROM captcha_status
    WHERE user_id = :user_id;
'''

GET_USER_PASSED_FROM_CAPTCHA_STATUS = '''
    SELECT passed
    FROM captcha_status
    WHERE user_id = :user_id;
'''

SET_USER_CURRENT_CAPTCHA_VALUE = '''
    REPLACE INTO active_captcha_storage (user_id, current_value)
    VALUES (:user_id, :current_value);
'''

SET_USER_CURRENT_CAPTCHA_CREATION_TIME_DATE = '''
    REPLACE INTO active_captcha_storage (user_id, unix_creation_time_date)
    VALUES (:user_id, :unix_creation_time_date);
'''

SET_USER_CURRENT_CAPTCHA_LAST_TRY_TIME_DATE = '''
    REPLACE INTO active_captcha_storage (user_id, unix_last_try_time_date)
    VALUES (:user_id, :unix_last_try_time_date);
'''
GET_USER_CURRENT_CAPTCHA_VALUE = '''
    SELECT (current_value)
    FROM active_captcha_storage
    WHERE user_id = :user_id;
'''
GET_USER_CURRENT_CAPTCHA_CREATION_TIME_DATE = '''
    SELECT (unix_creation_time_date)
    FROM active_captcha_storage
    WHERE user_id = :user_id;
'''
GET_USER_CURRENT_CAPTCHA_LAST_TRY_TIME_DATE = '''
    SELECT (unix_last_try_time_date)
    FROM active_captcha_storage
    WHERE user_id = :user_id;
'''

# -------------------- [LOGGING] ------------------
GET_USER_BAN_LOG = '''
    SELECT unix_start_date, unix_end_date
    FROM users
    INNER JOIN ban_log USING(user_id)
    ORDER BY start_date DESC
    WHERE user_id = :user_id;
'''

GET_USER_JOIN_QUIT_LOG = '''
    SELECT unix_join_date, unix_quit_date
    FROM users
    INNER JOIN join_log USING(user_id)
    INNER JOIN quit_log USING(user_id)
    ORDER BY unix_join_date DESC
    WHERE user_id = :user_id;
'''

INSERT_QUIT_ENTRY = '''
    INSERT INTO quit_log (user_id, unix_quit_date)
    VALUES (:user_id, :unix_quit_date);
'''

INSERT_JOIN_ENTRY = '''
    INSERT INTO join_log (user_id, unix_join_date)
    VALUES (:user_id, :unix_join_date);
'''

# ------------------------ [ROLES MANAGEMENT] ---------------------------------

CREATE_UPDATE_ROLE = '''

'''

DELETE_ROLE = '''

'''

SET_ROLE = '''

'''
