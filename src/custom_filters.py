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
from telegram.ext.filters import BaseFilter
from captcha_manager import CaptchaManager, MaxCaptchaTriesError,\
        CaptchaFloodError
from custom_dataclasses import User
from custom_logging import user_log_str


logger = logging.getLogger(__name__)


class ActiveUsersFilter(BaseFilter):
    '''
    This class allows the messages/commands of active users
    '''
    def __init__(self, database_manager):
        self._db_man = database_manager
        self.update_filter = True

    def filter(self, update):
        tg_user = update.message.from_user
        if User(self._db_man, tg_user.id).is_active:
            return True
        else:
            logger.debug(
                f'{user_log_str(update)} Update ({update.message.text}) '
                'was filtered because he\'s not active'
            )
            return False


class UnbannedUsersFilter(BaseFilter):
    '''
    This class filters the messages/commands of banned users
    '''
    def __init__(self, database_manager):
        self._db_man = database_manager
        self.update_filter = True

    def filter(self, update):
        tg_user = update.message.from_user
        if not User(self._db_man, tg_user.id).is_banned:
            return True
        else:
            logger.debug(
                f'{user_log_str(update)} banned user has tried to use the bot'
            )
            update.message.reply_text('You have been banned from the bot')
            return False


class ValidPermissionsFilter(BaseFilter):
    '''
    This class filters the messages/commands of users that don't have the
    necessary permissions
    '''

    def __init__(self, database_manager):
        self._db_man = database_manager
        self.update_filter = True

    def filter(self, update):
        tg_user = update.message.from_user()
        user = User(self._db_man, tg_user.id)

        has_permissions = False
        if has_permissions:
            return True
        else:
            update.message.reply('You do not have the necessary permissions')
            logger.debug(f'{user_log_str(update)} has tried to send a message '
                         'with invalid permissions')
            return False


class PassedCaptchaFilter(BaseFilter):
    '''
    This class filters the messages/commands of users that didn't pass the
    captcha verification
    '''

    def __init__(self, database_manager, captcha_manager):
        self._db_man = database_manager
        self.update_filter = True
        self._captcha_manager = captcha_manager

    def filter(self, update):
        tg_user = update.message.from_user
        user = User(self._db_man, tg_user.id)
        if user.captcha_status.passed:
            return True
        else:
            # Proceed with captcha verification
            if user.captcha_status.current_value:
                try:
                    self._captcha_manager.submit_captcha(
                        user,
                        update.message.text
                    )
                    if user.captcha_status.passed:
                        logger.info(f'{user_log_str(update)} has passed the '
                                    'captcha challenge')
                        update.message.reply_text('You passed the captcha')
                    else:
                        update.message.reply_text('Wrong captcha')
                        max_tries = self._captcha_manager._config["Captcha"]\
                                ["MaxCaptchaTries"]
                        logger.info(
                            f'{user_log_str(update)} has failed the '
                            'captcha challenge'
                            f' ({user.captcha_status.failed_attempts}/'
                            f'{max_tries})')
                except MaxCaptchaTriesError as e:
                    update.message.reply_text(
                        'You have been banned until'
                        f'{e.end_date} for failing the captcha auth too many'
                        'times'
                    )
                    logger.info(f'{user_log_str(update)} has been banned until'
                                f'{e.end_date} for failing captcha auth too'
                                'may times')
                except CaptchaFloodError:
                    logger.info(f'{user_log_str(update)} is flooding the'
                                'captcha')
                    delay = self._captcha_manager.\
                        _config["Captcha"]["TimeDelayBetweenAttempts"]
                    update.message.reply_text(
                        f'You can try once every {delay}'
                    )
            elif not user.captcha_status.current_value and \
                    user.captcha_status.passed:
                return True

            captcha_img = self._captcha_manager.start_captcha_session(user)
            if captcha_img:
                logger.info(f'{user_log_str(update)} generated '
                            f'new captcha {user.captcha_status.current_value}')
                update.message.reply_photo(
                    captcha_img,
                    caption='Please complete the captcha challenge (no spaces)'
                )
            else:
                update.message.reply_text(
                    'Please complete the captcha challenge (no spaces)'
                )
            return False
