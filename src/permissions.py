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


from enum import IntFlag, auto, EnumMeta, unique
from operator import or_ as _or_
from functools import reduce


class CustomEnumMetaForCaseInsensiviSubscript(EnumMeta):
    # https://stackoverflow.com/questions/24716723/
    # issue-extending-enum-and-redefining-getitem
    def __getitem__(self, value):
        if type(value) == str:
            return super().__getitem__(value.upper())
        else:
            return super().__getitem__(value)


def with_limits(enumeration):
    # https://stackoverflow.com/questions/42251081/
    # representation-of-all-values-in-flag-enum
    "add NONE and ALL psuedo-members to enumeration"
    none_mbr = enumeration(0)
    all_mbr = enumeration(reduce(_or_, enumeration))
    enumeration._member_map_['NONE'] = none_mbr
    enumeration._member_map_['ALL'] = all_mbr
    return enumeration


@with_limits
@unique
class Permissions(IntFlag, metaclass=CustomEnumMetaForCaseInsensiviSubscript):
    # Basic permissions
    # Permission to receive message
    RECEIVE = auto()
    # Permission to send text messages
    SEND_TEXT = auto()
    #ALL_TYPES = [
    #    HASHTAG, CASHTAG, PHONE_NUMBER, BOT_COMMAND, URL,
    #    EMAIL, PRE, TEXT_LINK, TEXT_MENTION
    #]

    # Permission to send URLs
    SEND_URL = auto()
    # Permission to send media
    SEND_MEDIA = auto()
    # Permission to send stickers and gifs
    SEND_STICKERS_GIFS = auto()
    # Permission to embed links
    EMBED_LINKS = auto()
    # Permission to send polls
    SEND_POLLS = auto()
    # Permission to bypass captcha
    BYPASS_CAPTCHA = auto()

    # Chat management
    # Permission to pin messages
    PIN_MESSAGES = auto()
    # Permission to view logs
    VIEW_LOGS = auto()
    # Permission to view deanonimized messages
    VIEW_CLEAR_MSGS = auto()
    # Permission to kick
    KICK = auto()
    # Permission to ban
    BAN = auto()

    # Administration
    # Permission to set role
    SET_ROLE = auto()
    # Permission to waive captcha
    WAIVE_CAPTCHA = auto()
    # Permission to reset captcha
    RESET_CAPTCHA = auto()

