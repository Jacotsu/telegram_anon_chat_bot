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
        role_name TEXT PRIMARY KEY,
        role_power INTEGER NOT NULL DEFAULT 0,
        role_permissions INTEGER NOT NULL DEFAULT 0
    );
'''

# 1 role per user
CREATE_USER_ASSIGNED_ROLES = '''
    CREATE TABLE IF NOT EXISTS assigned_roles (
        user_id INTEGER PRIMARY KEY,
        role_name TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(role_name) REFERENCES roles(role_name)
    ) WITHOUT ROWID;
'''

CREATE_CAPTCHA_LOG_TABLE = '''
    CREATE TABLE IF NOT EXISTS captcha_status (
        user_id INTEGER PRIMARY KEY,
        failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK(failed_attempts >= 0),
        total_failed_attempts INTEGER NOT NULL DEFAULT 0
        CHECK(total_failed_attempts >= failed_attempts),
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
        unix_end_date INTEGER NOT NULL DEFAULT 9223372036854775807
        CHECK(unix_end_date >= unix_start_date),
        reason TEXT DEFAULT "",
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
'''

# Delay is stored in milliseconds
CREATE_CHAT_DELAYS_TABLE = '''
    CREATE TABLE IF NOT EXISTS chat_delays (
        user_id INTEGER PRIMARY KEY,
        chat_delay INTEGER NOT NULL DEFAULT 200 CHECK(chat_delay >= 0),
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    ) WITHOUT ROWID;
'''


CREATE_MESSAGES_TABLE = '''
    CREATE TABLE IF NOT EXISTS message_log (
        sender_id INTEGER,
        receiver_id INTEGER,
        unix_sent_date INTEGER NOT NULL,
        sender_message_id INTEGER NOT NULL,
        receiver_message_id INTEGER NOT NULL,
        FOREIGN KEY(sender_id) REFERENCES users(user_id),
        FOREIGN KEY(receiver_id) REFERENCES users(user_id)
    );
'''

CREATE_ADMINISTRATIVE_POLLS_TABLE = '''
    CREATE TABLE IF NOT EXISTS admin_polls (
        poll_id INTEGER PRIMARY KEY,
        poll_type INTEGER NOT NULL,
        creator_user_id INTEGER NOT NULL,
        extra_data BLOB,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    ) WITHOUT ROWID;
'''

# ----------------------------[VIEWS CREATION]---------------------------------

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

# Selects only unbanned users that passed the captcha and
# whose joined date is more recent than their
# quit date (this means that they rejoined or first joined)
# CREATE AFTER BANNED_USERS_VIEW
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
    HAVING IFNULL(MAX(unix_join_date), 0) > IFNULL(MAX(unix_quit_date), 0)
    AND user_id NOT IN (SELECT user_id FROM banned_users)
    AND (SELECT passed FROM captcha_status WHERE user_id = user_id);
'''

# ------------------------------ [TRIGGERS] -----------------------------------

# Set the user's permissions to the role permissions
USER_ROLE_CHANGED = '''
    CREATE TRIGGER IF NOT EXISTS user_role_change_trigger
        BEFORE UPDATE
        ON assigned_roles
    BEGIN
        REPLACE INTO permissions(user_id, permissions)
        VALUES (
            OLD.user_id
            (SELECT role_permissions
             FROM roles
             WHERE role_name = NEW.role_name)
        );
    END;
'''

# When a User is banned return him to the default role, which is the role with
# the lowest power
USER_BANNED = '''
    CREATE TRIGGER IF NOT EXISTS user_ban_trigger
        BEFORE UPDATE
        ON ban_log
    BEGIN
        REPLACE INTO permissions(user_id, permissions)
        VALUES (
            OLD.user_id
            (SELECT role_permissions
             FROM roles
             WHERE role_name = NEW.role_name
             ORDER BY power ASC
             LIMIT 1
             )
        );
    END;
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
    WITH new (user_id, failed_attempts) AS (VALUES(:user_id, :failed_attempts))
    REPLACE INTO captcha_status (user_id, failed_attempts,
        total_failed_attempts, passed)
    SELECT new.user_id, new.failed_attempts, old.total_failed_attempts,
        old.passed
    FROM new
    LEFT JOIN captcha_status AS old USING (user_id);
'''

SET_USER_TOTAL_FAILED_ATTEMPTS_FROM_CAPTCHA_STATUS = '''
    WITH new (user_id, total_failed_attempts) AS (VALUES(:user_id,
        :total_failed_attempts))
    REPLACE INTO captcha_status (user_id, failed_attempts,
        total_failed_attempts, passed)
    SELECT new.user_id, old.failed_attempts, new.total_failed_attempts,
        old.passed
    FROM new
    LEFT JOIN captcha_status AS old USING (user_id);
'''

SET_USER_PASSED_FROM_CAPTCHA_STATUS = '''
    WITH new (user_id, passed) AS (VALUES(:user_id, :passed))
    REPLACE INTO captcha_status (user_id, failed_attempts,
        total_failed_attempts, passed)
    SELECT new.user_id, old.failed_attempts, old.total_failed_attempts,
        new.passed
    FROM new
    LEFT JOIN captcha_status AS old USING (user_id);
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
    WITH new (user_id, current_value) AS (VALUES(:user_id,
        :current_value))
    REPLACE INTO active_captcha_storage (user_id, current_value,
        unix_creation_time_date, unix_last_try_time_date)
    SELECT new.user_id, new.current_value, old.unix_creation_time_date,
        old.unix_last_try_time_date
    FROM new
    LEFT JOIN active_captcha_storage AS old USING (user_id);
'''

SET_USER_CURRENT_CAPTCHA_CREATION_TIME_DATE = '''
    WITH new (user_id, unix_creation_time_date) AS (VALUES(:user_id,
        :unix_creation_time_date))
    REPLACE INTO active_captcha_storage (user_id, current_value,
        unix_creation_time_date, unix_last_try_time_date)
    SELECT new.user_id, old.current_value, new.unix_creation_time_date,
        old.unix_last_try_time_date
    FROM new
    LEFT JOIN active_captcha_storage AS old USING (user_id);
'''

SET_USER_CURRENT_CAPTCHA_LAST_TRY_TIME_DATE = '''

    WITH new (user_id, unix_last_try_time_date) AS (VALUES(:user_id,
        :unix_last_try_time_date))
    REPLACE INTO active_captcha_storage (user_id, current_value,
        unix_creation_time_date, unix_last_try_time_date)
    SELECT new.user_id, old.current_value, old.unix_creation_time_date,
        new.unix_last_try_time_date
    FROM new
    LEFT JOIN active_captcha_storage AS old USING (user_id);
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

CREATE_DEFAULT_ROLE = '''
    REPLACE INTO roles (role_name, role_power, role_permissions)
    VALUES ('default', 0, 0);
'''

CREATE_UPDATE_ROLE = '''
    REPLACE INTO roles (role_name, role_power, role_permissions)
    VALUES (:role_name, :role_power, :role_permissions);
'''

GET_ROLES = '''
    SELECT role_name
    FROM roles;
'''

DELETE_ROLE = '''
    DELETE FROM roles
    WHERE role_name = :role_name;
'''

SET_USER_ROLE = '''
    REPLACE INTO assigned_roles(user_id, role_name)
    VALUES (:user_id, :role_name);
'''

GET_USER_ROLE = '''
    SELECT role_name
    FROM assigned_roles
    WHERE user_id = :user_id;
'''

GET_USERS_BY_ROLE = '''
    SELECT user_id
    FROM assigned_roles
    WHERE role_name = :role_name;
'''

GET_AVAILABLE_ROLES = '''
    SELECT role_name
    FROM roles;
'''

GET_ROLE_PERMISSIONS = '''
    SELECT role_permissions
    FROM roles
    WHERE role_name = :role_name;
'''

GET_ROLE_POWER = '''
    SELECT role_power
    FROM roles
    WHERE role_name = :role_name;
'''

SET_ROLE_PERMISSIONS = '''
    WITH new (role_name, role_permissions) AS (VALUES(:role_name,
        :permissions))
    REPLACE INTO roles (role_name, role_power, role_permissions)
    SELECT new.role_name, old.role_power, new.role_permissions
    FROM new
    LEFT JOIN roles AS old USING (role_name);
'''

SET_ROLE_POWER = '''
    WITH new (role_name, role_power) AS (VALUES(:role_name, :role_power))
    REPLACE INTO roles (role_name, role_power, role_permissions)
    SELECT new.role_name, new.role_power, old.role_permissions
    FROM new
    LEFT JOIN roles AS old USING (role_name);
'''

DOES_ROLE_EXIST = '''
    SELECT 1
    FROM roles
    WHERE role_name = :role_name
'''

# ------------------------------- [ANTIFLOOD] ---------------------------------

GET_USER_CHAT_DELAY = '''
    SELECT chat_delay
    FROM chat_delays
    WHERE user_id = :user_id;
'''

SET_USER_CHAT_DELAY = '''
    REPLACE INTO chat_delays (user_id, chat_delay)
    VALUES (:user_id, :chat_delay);
'''
RESET_USER_CHAT_DELAY = '''
    DELETE FROM chat_delays
    WHERE user_id = :user_id;
'''

# ------------------------------ [CHAT PURGE] ---------------------------------

REGISTER_MESSAGE = '''
    INSERT INTO message_log(sender_id, receiver_id, unix_sent_date,
        sender_message_id, receiver_message_id)
    VALUES (:sender_id, :receiver_id, :unix_sent_date, :sender_message_id,
    :receiver_message_id);
'''

GET_MESSAGES_TO_PURGE = '''
    SELECT receiver_id, receiver_message_id
    FROM message_log
    WHERE unix_sent_date < :unix_utc_timedate;
'''

PURGE_MESSAGES = '''
    DELETE FROM message_log
    WHERE unix_sent_date < :unix_utc_timedate;
'''

# ------------------------- [ADMINISTRATIVE POLLS] ----------------------------

REGISTER_ADMIN_POLL = '''
    REPLACE INTO admin_polls(poll_id, poll_type, creator_user_id, extra_data)
    VALUES (:poll_id, :poll_type, :user_id, :extra_data);
'''

DELETE_ADMIN_POLL = '''
    DELETE FROM admin_polls
    WHERE poll_id = :poll_id;
'''

GET_ADMIN_POLL = '''
    SELECT poll_type, creator_user_id, extra_data
    FROM admin_polls
    WHERE poll_id = :poll_id;
'''
