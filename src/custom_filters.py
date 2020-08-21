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
from telegram.ext import Filters
from permissions import Permissions, InvalidPermissionsError
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
from captcha_manager import CaptchaManager, MaxCaptchaTriesError,\
        CaptchaFloodError
from custom_dataclasses import User
from custom_logging import user_log_str


logger = logging.getLogger(__name__)


class AnonPollFilter(Filters._Poll):
    def filter(self, message):
        return super().filter(message) and bool(message.poll.is_anonymous)




class SimpleTextFilter(BaseFilter):
    def filter(self, message):
        return bool(message.text)


class AntiFloodFilter(BaseFilter):
    def __init__(self, database_manager, config):
        super().__init__()
        self._db_man = database_manager
        self._default_time_delta = timedelta(
            config["AntiFloodFilter"]["MinimumDelayBetweenMessages"]
        )
        self._last_message_dict = {}

    def filter(self, message):
        tg_user = message.from_user
        user = User(self._db_man, tg_user.id)
        if Permissions.BYPASS_ANTIFLOOD in user.permissions:
            return True
        else:
            try:
                delay = user.chat_delay
            except ValueError:
                delay = self._default_time_delta

            now = datetime.utcnow()
            try:
                elapsed_time = now - self._last_message_dict[tg_user.id]
                if elapsed_time > delay:
                    # sent_warning is necessary to avoid a DOS by malicious
                    # users that try to flood anyway
                    self._last_message_dict[tg_user.id] = {
                        'last_msg': now,
                        'sent_warning': False
                    }
                    return True
            except KeyError:
                self._last_message_dict[tg_user.id] = {
                    'last_msg': now,
                    'sent_warning': False
                }
                return True

            if not self._last_message_dict[tg_user.id]['sent_warning']:
                logger.info(f'{user_log_str(message)} is trying to flood '
                            'the chat')
                message.reply_text('You must waith {delay - elapsed_time} '
                                   'before sending another message or command')
            return False

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


class MessagePermissionsFilter(BaseFilter):
    '''
    This class filters the messages/commands of users that don't have the
    necessary permissions
    '''

    def __init__(self, database_manager):
        self._db_man = database_manager
        self.update_filter = True

        self._filter_map = {

            Permissions.SEND_SIMPLE_TEXT: {
                'filter': Filters.entity('mention'),
                'user_msg': 'You cannot send messages',
                'log_msg': '{user_log_str} has tried to send a message'
                           'with invalid permissions ({user_perm}) '
                           '{message}'
            },
            Permissions.SEND_MENTION: {
                'filter': Filters.entity('mention'),
                'user_msg': 'You cannot mention people',
                'log_msg': '{user_log_str} has tried to mention a user'
                           'with invalid permissions ({user_perm}) '
                           '{message}'
            },
            Permissions.SEND_HASHTAG: {
                'filter': Filters.entity('hashtag'),
                'user_msg': 'You cannot send hashtags',
                'log_msg': '{user_log_str} has tried to send an '
                           'hashtag with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_CASHTAG: {
                'filter': Filters.entity('cashtag'),
                'user_msg': 'You cannot send chashtags',
                'log_msg': '{user_log_str} has tried to send a '
                           'chashtag with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_PHONE_NUMBER: {
                'filter': Filters.entity('phone_number'),
                'user_msg': 'You cannot send phone numbers',
                'log_msg': '{user_log_str} has tried to send a '
                           'phone number with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_EMAIL: {
                'filter': Filters.entity('email'),
                'user_msg': 'You cannot send email addresses',
                'log_msg': '{user_log_str} has tried to send an '
                           'email address with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_BOLD: {
                'filter': Filters.entity('bold'),
                'user_msg': 'You cannot send bold text',
                'log_msg': '{user_log_str} has tried to send '
                           'bold text with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_ITALIC: {
                'filter': Filters.entity('italic'),
                'user_msg': 'You cannot send italic text',
                'log_msg': '{user_log_str} has tried to send '
                           'italic text with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_CODE: {
                'filter': Filters.entity('code'),
                'user_msg': 'You cannot send code',
                'log_msg': '{user_log_str} has tried to send '
                           'code with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_UNDERLINE: {
                'filter': Filters.entity('underline'),
                'user_msg': 'You cannot send underlined text',
                'log_msg': '{user_log_str} has tried to send '
                           'underlined text with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_STRIKETHROUGH: {
                'filter': Filters.entity('strikethrough'),
                'user_msg': 'You cannot send strikethrough text',
                'log_msg': '{user_log_str} has tried to send '
                           'strikethrough text with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_CODE_BLOCK: {
                'filter': Filters.entity('pre'),
                'user_msg': 'You cannot send code blocks',
                'log_msg': '{user_log_str} has tried to send a '
                           'code block with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_URL: {
                'filter': Filters.entity('url'),
                'user_msg': 'You cannot send urls',
                'log_msg': '{user_log_str} has tried to send a '
                           'url with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_TEXT_LINK: {
                'filter': Filters.entity('text_link'),
                'user_msg': 'You cannot send text links',
                'log_msg': '{user_log_str} has tried to send a '
                           'text link with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_TEXT_MENTION: {
                'filter': Filters.entity('text_mention'),
                'user_msg': 'You cannot send text mentions',
                'log_msg': '{user_log_str} has tried to send a '
                           'text mention with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_ANIMATION: {
                'filter': Filters.animation,
                'user_msg': 'You cannot send animations',
                'log_msg': '{user_log_str} has tried to send an '
                           'animation with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_PHOTO: {
                'filter': Filters.photo,
                'user_msg': 'You cannot send photos',
                'log_msg': '{user_log_str} has tried to send a '
                           'photo with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_CONTACT: {
                'filter': Filters.contact,
                'user_msg': 'You cannot send contacts',
                'log_msg': '{user_log_str} has tried to send a '
                           'contact with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_DICE: {
                'filter': Filters.dice,
                'user_msg': 'You cannot send dices/targets',
                'log_msg': '{user_log_str} has tried to send a '
                           'dice/target with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_DOCUMENT: {
                # Mimetype filtering is possible, but unneeded right now
                'filter': Filters.document,
                'user_msg': 'You cannot send documents',
                'log_msg': '{user_log_str} has tried to send a '
                           'document with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_LOCATION: {
                'filter': Filters.location,
                'user_msg': 'You cannot send locations',
                'log_msg': '{user_log_str} has tried to send a '
                           'location with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_VIDEO: {
                'filter': Filters.video,
                'user_msg': 'You cannot send videos',
                'log_msg': '{user_log_str} has tried to send a '
                           'video with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_VIDEO_NOTE: {
                'filter': Filters.video_note,
                'user_msg': 'You cannot send video notes',
                'log_msg': '{user_log_str} has tried to send a '
                           'video note with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_AUDIO: {
                'filter': Filters.audio,
                'user_msg': 'You cannot send audios',
                'log_msg': '{user_log_str} has tried to send an '
                           'audio with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_STICKER: {
                'filter': Filters.sticker,
                'user_msg': 'You cannot send stickers',
                'log_msg': '{user_log_str} has tried to send a '
                           'sticker with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.SEND_ANON_POLL: {
                'filter': AnonPollFilter(),
                'user_msg': 'You cannot send hashtags',
                'log_msg': '{user_log_str} has tried to send an '
                           'hashtag with invalid permissions '
                           '({user_perm}) {message}'
            }
        }

    def filter(self, update):
        tg_user = update.message.from_user
        user = User(self._db_man, tg_user.id)

        for perm in Permissions:
            try:
                perm_data = self._filter_map[perm]
                if perm in user.permissions:
                    data_filter = ~Filters.command | perm_data['filter']
                else:
                    data_filter = ~Filters.command & ~perm_data['filter']
                if not data_filter.filter(update):
                    raise InvalidPermissionsError()
            except KeyError:
                pass
            except InvalidPermissionsError:
                update.message.reply_text(perm_data['user_msg'])
                logger.debug(perm_data['log_msg'].format(
                    user_log_str=user_log_str(update.message),
                    user_perm=user.permissions,
                    message=update.message
                ))
                return False

        return True


class PassedCaptchaFilter(BaseFilter):
    '''
    This class filters the messages/commands of users that didn't pass the
    captcha verification
    '''

    def __init__(self, database_manager, captcha_manager,
                 on_success_callback=None):
        self._db_man = database_manager
        self.update_filter = True
        self._captcha_manager = captcha_manager
        self._on_success_callback = on_success_callback

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
                        if self._on_success_callback:
                            self._on_success_callback(update)
                        return True
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
                        e.reason
                    )
                    if e.is_ban:
                        logger.info(f'{user_log_str(update)} has been banned '
                                    f'until {e.end_date} for failing captcha '
                                    'auth too may times')
                    elif e.is_kick:
                        logger.info(f'{user_log_str(update)} has been kicked '
                                    'for failing captcha '
                                    'auth too may times')
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
            logger.info(f'{user_log_str(update)} generated captcha '
                        f'{user.captcha_status.current_value}')
            update.message.reply_photo(
                captcha_img,
                caption='Please complete the captcha challenge '
                '(no spaces)'
            )
            return False
