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


logger = logging.getLogger(__name__)


class UserResolverError(Exception):
    pass


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


class InvalidPermissionsError(Exception):
    pass
