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


from enum import IntFlag, auto, unique
import utils


@utils.with_limits
@unique
class Permissions(IntFlag,
                  metaclass=utils.CustomEnumMetaForCaseInsensiviSubscript):
    '''
    An enum that represents the current user's permissions
    NOTE TO DEVS: ONLY APPEND NEW PERMISSIONS, OTHERWISE THE PERMISSIONS STORED
    IN THE DATABASE WILL BE GARBLED
    '''
    def __str__(self):
        return ", ".join(
            super().__str__()
            .replace('Permissions.', '')
            .replace('_', ' ')
            .lower()
            .split('|')
        )

    def _perm_generator(self):
        for perm in Permissions:
            if perm in self:
                yield perm

    def __iter__(self):
        return self._perm_generator()

    # Basic permissions
    # Permission to receive message
    RECEIVE = auto()

    # ----------------------------- [TEXT PERMISSIONS] ------------------------

    SEND_SIMPLE_TEXT = auto()
    SEND_MENTION = auto()
    SEND_HASHTAG = auto()
    SEND_CASHTAG = auto()
    SEND_PHONE_NUMBER = auto()
    SEND_EMAIL = auto()
    SEND_BOLD = auto()
    SEND_ITALIC = auto()
    SEND_CODE = auto()
    SEND_UNDERLINE = auto()
    SEND_STRIKETHROUGH = auto()

    SEND_CODE_BLOCK = auto()
    SEND_URL = auto()
    SEND_TEXT_LINK = auto()
    SEND_TEXT_MENTION = auto()

    # ---------------------------- [MEDIA PERMISSIONS] ------------------------

    # requires send_document to work
    SEND_ANIMATION = auto()
    SEND_PHOTO = auto()
    SEND_CONTACT = auto()
    SEND_DICE = auto()
    SEND_DOCUMENT = auto()
    SEND_LOCATION = auto()
    SEND_VIDEO = auto()
    SEND_VIDEO_NOTE = auto()
    SEND_AUDIO = auto()
    SEND_VOICE = auto()
    SEND_STICKER = auto()

    # Non anon polls are not accepted
    SEND_ANON_POLL = auto()

    FORWARD = auto()

    # -------------------------------- [COMMANDS] -----------------------------

    SEND_CMD = auto()

    # ---------------------------- [LOGS MANAGEMENT] --------------------------

    VIEW_LOGS = auto()
    VIEW_USER_INFO = auto()

    # ---------------------------- [ADMINISTRATION] ---------------------------

    KICK = auto()
    BAN = auto()
    DELETE_MESSAGE = auto()
    VIEW_CLEAR_MSGS = auto()

    # ----------------------------- [PERMISSIONS] -----------------------------

    SET_USER_PERMISSIONS = auto()
    SET_DEFAULT_PERMISSIONS = auto()
    SHOW_DEFAULT_PERMISSIONS = auto()
    SHOW_ALL_PERMISSIONS = auto()

    # ------------------------------- [ROLES] ---------------------------------

    SET_USER_ROLE = auto()
    SET_DEFAULT_ROLE = auto()
    EDIT_ROLE = auto()
    CREATE_ROLE = auto()
    DELETE_ROLE = auto()

    # ------------------------------ [CAPTCHA] --------------------------------

    WAIVE_CAPTCHA = auto()
    RESET_CAPTCHA = auto()
    BYPASS_CAPTCHA = auto()

    # ----------------------------- [ANTIFLOOD] -------------------------------

    BYPASS_ANTIFLOOD = auto()
    SET_USER_CHAT_DELAY = auto()

    # ------------------------------ [BANNER] ---------------------------------

    SET_BANNERS = auto()

    # ------------------------------- [PURGE] ---------------------------------

    SET_PURGE_INTERVAL = auto()
    PURGE_MESSAGES = auto()

    # ------------------------ [GROUPED PERMISSIONS] --------------------------
    SEND_TEXT = SEND_MENTION | SEND_HASHTAG | SEND_CASHTAG |\
        SEND_PHONE_NUMBER | SEND_UNDERLINE | SEND_EMAIL | SEND_BOLD |\
        SEND_ITALIC | SEND_CODE | SEND_STRIKETHROUGH | SEND_SIMPLE_TEXT

    SEND_LINKS = SEND_URL | SEND_TEXT_LINK

    SEND_MEDIA = SEND_ANIMATION | SEND_PHOTO | SEND_VIDEO | SEND_AUDIO
