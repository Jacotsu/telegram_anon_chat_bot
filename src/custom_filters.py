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
from telegram import Update, Message
from permissions import Permissions
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
from captcha_manager import CaptchaManager
from custom_exceptions import MaxCaptchaTriesError, CaptchaFloodError,\
    InvalidPermissionsError
from custom_dataclasses import User
from custom_logging import user_log_str
from misc import user_join


logger = logging.getLogger(__name__)


class MessageBrokeredFilter(BaseFilter):
    def __init__(self, database_manager, message_broker=None, *args, **kwargs):
        self._db_man = database_manager
        self._msg_broker = message_broker
        super().__init__(*args, **kwargs)

    def send_message(self,  update_or_message, msg):
        if isinstance(update_or_message, Update):
            message = update_or_message.message
        elif isinstance(update_or_message, Message):
            message = update_or_message

        user = User(self._db_man, message.from_user)
        if self._msg_broker:
            self._msg_broker.send_or_forward_msg(user, msg)
        else:
            update_or_message.reply_text(msg)


class AnonPollFilter(Filters._Poll):
    def filter(self, message):
        return super().filter(message) and bool(message.poll.is_anonymous)


class AntiFloodFilter(MessageBrokeredFilter):
    def __init__(self, database_manager, config, message_broker=None):
        super().__init__(database_manager, message_broker)
        self._default_time_delta = timedelta(seconds=timeparse(
            config["AntiFlood"]["MinimumDelayBetweenMessages"]
        ))
        self._last_message_dict = {}
        self._cleanup_time_delta = timedelta(hours=1)
        self._inactivity_cleanup_time_delta = timedelta(minutes=10)
        self._last_cleanup_time = datetime.utcnow()

    def filter(self, message):
        user = User(self._db_man, message.from_user)
        now = datetime.utcnow()

        if now - self._last_cleanup_time > self._cleanup_time_delta:
            self._last_message_dict = {
                user_id: data for (user_id, data) in
                self._last_message_dict.items()
                if now - data['last_msg_time'] <
                self._inactivity_cleanup_time_delta
            }

        if Permissions.BYPASS_ANTIFLOOD in user.permissions:
            return True

        try:
            delay = user.chat_delay
        except ValueError:
            delay = self._default_time_delta

        try:
            elapsed_time = now - \
                    self._last_message_dict[user.id]['last_msg_time']
            if elapsed_time > delay:
                # sent_warning is necessary to avoid a DOS by malicious
                # users that try to flood anyway
                self._last_message_dict[user.id] = {
                    'last_msg_time': now,
                    'sent_warning': False
                }
                return True
        except KeyError:
            self._last_message_dict[user.id] = {
                'last_msg_time': now,
                'sent_warning': False
            }
            return True

        if not self._last_message_dict[user.id]['sent_warning']:
            logger.warning(f'{user} is trying to flood the chat')
            self.send_message(message, f'You must wait {delay - elapsed_time} '
                              'before sending another message or command')
        return False


class ActiveUsersFilter(BaseFilter):
    '''
    This class allows the messages/commands of active users
    '''
    def __init__(self, database_manager):
        self._db_man = database_manager

    def filter(self, message):
        user = User(self._db_man, message.from_user)
        if user.is_active:
            return True

        logger.debug(
            f'{user}\'s Message ({message}) was filtered because he\'s '
            'not active'
        )
        return False


class UnbannedUsersFilter(MessageBrokeredFilter):
    '''
    This class filters the messages/commands of banned users
    '''
    def __init__(self, database_manager, message_broker=None):
        super().__init__(database_manager, message_broker)
        self._db_man = database_manager
        # We only send the message once, to avoid spambots that would saturate
        # our message bandwidth
        self._sent_warnings = {}

    def filter(self, message):
        user = User(self._db_man, message.from_user)
        if not user.is_banned:
            return True

        logger.debug(
            f'banned user {user} has tried to use the bot'
        )

        if not self._sent_warnings[user.id]:
            self.send_message(message, 'You have been banned from the bot')
            self._sent_warnings[user.id] = True
        return False


class CommandPermissionsFilter(MessageBrokeredFilter):
    def __init__(self, database_manager, command_dicts, message_broker=None):
        super().__init__(database_manager, message_broker)
        self._command_dicts = command_dicts

    def filter(self, message):
        user = User(self._db_man, message.from_user)
        try:
            # Take the first word an drop the initial slash
            cmd = message.text.split()[0][1:]
            cmd_dict = self._command_dicts[cmd]
            if cmd_dict['permissions_required'] in user.permissions:
                return True
            else:
                self.send_message(
                    message,
                    'You do not have the necessary permissions '
                    'to execute this command'
                )
                logger.warning(f'{user} has tried to execute {cmd} without '
                               'the appropriate permissions')
        except (KeyError, IndexError):

            self.send_message(
                message,
                'Unknown command'
            )
        return False


class MessagePermissionsFilter(MessageBrokeredFilter):
    '''
    This class filters the messages of users that don't have the
    necessary permissions
    '''
    update_filter = True

    def __init__(self, database_manager, message_broker=None):
        super().__init__(database_manager, message_broker)

        self._filter_map = {
            Permissions.SEND_SIMPLE_TEXT: {
                'filter':
                Filters.text & ~Filters.entity('mention') &
                ~Filters.entity('hashtag') & ~Filters.entity('cashtag') &
                ~Filters.entity('phone_number') & ~Filters.entity('email') &
                ~Filters.entity('bold') & ~Filters.entity('italic') &
                ~Filters.entity('code') & ~Filters.entity('underline') &
                ~Filters.entity('strikethrough') & ~Filters.entity('pre') &
                ~Filters.entity('url') & ~Filters.entity('text_link') &
                ~Filters.entity('text_mention'),
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
            Permissions.SEND_VOICE: {
                'filter': Filters.voice,
                'user_msg': 'You cannot send voice notes',
                'log_msg': '{user_log_str} has tried to send a '
                           'voice note with invalid permissions '
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
                'user_msg': 'You cannot send polls',
                'log_msg': '{user_log_str} has tried to send a '
                           'poll with invalid permissions '
                           '({user_perm}) {message}'
            },
            Permissions.FORWARD: {
                'filter': Filters.forwarded,
                'user_msg': 'You cannot forward messages',
                'log_msg': '{user_log_str} has tried to forward a '
                           'message with invalid permissions '
                           '({user_perm}) {message}'
            }
        }

    def filter(self, update):
        user = User(self._db_man, update.message.from_user)
        data_filter = None

        for perm in set(self._filter_map) & set(user.permissions):
            perm_data = self._filter_map[perm]
            if data_filter:
                data_filter |= perm_data['filter']
            else:
                data_filter = perm_data['filter']

        if data_filter and data_filter(update):
            return True

        for perm, data in self._filter_map.items():
            if data['filter'](update):
                self.send_message(update, data['user_msg'])
                logger.debug(data['log_msg'].format(
                    user_log_str=user,
                    user_perm=user.permissions,
                    message=update.message
                ))
                return False

        self.send_message(update, 'Unsupported message type')
        return False


class PassedCaptchaFilter(MessageBrokeredFilter):
    '''
    This class filters the messages/commands of users that didn't pass the
    captcha verification
    '''

    def __init__(self, database_manager, captcha_manager, config,
                 message_broker=None):
        super().__init__(database_manager, message_broker)
        self._last_attempt_dict = {}
        self._captcha_manager = captcha_manager
        self._config = config

    def filter(self, update):
        user = User(self._db_man, update.from_user)
        if user.captcha_status.passed:
            return True

        # Proceed with captcha verification
        if user.captcha_status.current_value:
            try:
                self._captcha_manager.submit_captcha(
                    user,
                    update.text
                )
                if user.captcha_status.passed:
                    logger.info(f'{user} has passed the captcha challenge')
                    user_join(user, self._config, self._msg_broker)
                    return False
                else:
                    self.send_message(update, 'Wrong captcha')
                    max_tries = self._captcha_manager\
                        ._config["Captcha"]["MaxCaptchaTries"]
                    logger.info(
                        f'{user} has failed the captcha challenge'
                        f' ({user.captcha_status.failed_attempts}/'
                        f'{max_tries})')
            except MaxCaptchaTriesError as e:
                self.send_message(update, e.reason)
            except CaptchaFloodError:
                try:
                    if self._last_attempt_dict[user.id]['sent_warning']:
                        logger.info(f'{user} is flooding the captcha')
                    else:
                        self.send_message(
                            update,
                            'You can try once every '
                            f'{self._captcha_manager.delay}'
                        )
                except KeyError:
                    self.send_message(
                        update,
                        'You can try once every '
                        f'{self._captcha_manager.delay}'
                    )
                finally:
                    self._last_attempt_dict[user.id] = {
                        'sent_warning': True
                    }
                    return False
        captcha_img = self._captcha_manager.start_captcha_session(user)
        if captcha_img:
            logger.info(f'{user} generated captcha '
                        f'{user.captcha_status.current_value}')
            update.reply_photo(
                captcha_img,
                caption='Please complete the captcha challenge '
                '(no spaces)'
            )
            self._last_attempt_dict[user.id] = {
                'sent_warning': False
            }
        return False
