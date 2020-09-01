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


from typing import Iterable
import logging
from telegram.ext import MessageHandler, Filters, messagequeue
from telegram import Message, Audio, Contact, Document, Animation,\
        Location, PhotoSize, Sticker, Venue, Video, VideoNote, Voice,\
        InputMediaPhoto, ParseMode
from custom_filters import ActiveUsersFilter, UnbannedUsersFilter,\
        PassedCaptchaFilter, MessagePermissionsFilter, AntiFloodFilter
from permissions import Permissions
from poll_types import PollTypes
from custom_dataclasses import User
from custom_logging import user_log_str

logger = logging.getLogger(__name__)


class MessageBroker:
    '''
    This class' main purpose is to send messages to valid users
    '''
    def __init__(self, updater, database_manager, captcha_manager, config):
        self._db_man = database_manager
        self._updater = updater
        self._captcha_manager = captcha_manager
        self._poll_pool = {}
        self._message_forward_map = {
            Audio: lambda x, y:  self._updater.bot.send_audio(
                x.id, y.audio.file_id, y.caption),
            Contact: lambda x, y:  self._updater.bot.send_contact(
                x.id, contact=y.contact),
            Document: lambda x, y:  self._updater.bot.send_document(
                x.id, y.document, caption=y.caption),
            # GIF or H.264/MPEG-4 AVC video without sound
            # Requires document
            Animation: lambda x, y:  self._updater.bot.send_animation(
                x.id, y.animation, caption=y.caption),
            Location: lambda x, y:  self._updater.bot.send_location(
                x.id, location=y.location),
            # Could be one of the following:
            # - Single photo
            # - Photo album
            list: lambda x, y:  self._send_photo(x.id, y),
            Sticker: lambda x, y:  self._updater.bot.send_sticker(
                x.id, y.sticker),
            Venue: lambda x, y:  self._updater.bot.send_venue(
                x.id, venue=y.venue),
            Video: lambda x, y:  self._updater.bot.send_video(
                x.id, y.video.file_id),
            VideoNote: lambda x, y:  self._updater.bot.send_video_note(
                x.id, y.video_note.file_id),
            Voice: lambda x, y:  self._updater.bot.send_voice(
                x.id, y.voice.file_id, y.caption),
            type(None): lambda x, y:  self._process_special_message(
                x.id, y)
        }

        self._is_messages_queued_default = True
        # Important to avoid hitting telegram's anti flood limits
        self._msg_queue = messagequeue.MessageQueue(
            all_burst_limit=29,
            all_time_limit_ms=1017)

        self._updater.dispatcher.add_handler(
            # NB: The captcha filter must come before the permissions filter
            # otherwhise new users won't be able to pass the verification
            MessageHandler(
                UnbannedUsersFilter(self._db_man, self) &
                ~Filters.command &
                PassedCaptchaFilter(
                    self._db_man,
                    self._captcha_manager,
                    config,
                    self
                ) &
                AntiFloodFilter(self._db_man, config, self) &
                MessagePermissionsFilter(self._db_man, self),
                callback=self._message_callback))

    def _send_photo(self, user_id, message):
        message.photo.sort(reverse=True, key=lambda x: x.width)
        self._updater.bot.send_photo(user_id, message.photo[0])

    def _process_special_message(self, user_id, message):
        if message.poll:
            if message.poll.id in self._poll_pool:
                sent_msg = self._updater.bot.forward_message(
                    user_id,
                    self._poll_pool[message.poll.id]['sender_id'],
                    message_id=self._poll_pool[message.poll.id]
                    ['message_id']
                )
            else:
                sent_msg = self._updater.bot.send_poll(
                    user_id,
                    message.poll.question,
                    [option.text for option in message.poll.options],
                    True,
                    allow_multiple_answers=message.poll.
                    allows_multiple_answers,
                    open_period=message.poll.open_period
                )
                self._poll_pool[message.poll.id] = {
                    'sender_id': user_id,
                    'message_id': sent_msg.message_id
                }
                message.delete()
        elif message.text:
            sent_msg = self._updater.bot.send_message(
                user_id,
                message.text
            )
        else:
            message.reply_text('Unsupported message type')
            return None
        return sent_msg

    def _message_callback(self, update, context):
        message = update.message
        if message.poll:
            # Check for admin polls
            try:
                # !IMPORTANT! always check that the answer sender is the poll
                # creator, otherwise non admins/mods could vote by through
                # a forwarded poll
                data = self._db_man.get_admin_poll(message.poll.id)
                if data['creator_user_id'] == message.from_user.id:
                    poll_type = data['poll_type']
                    # Should turn this into a map
                    if poll_type == PollTypes.SET_DEFAULT_PERMISSIONS:
                        message.reply_text('setting default permissions')
                        raise NotImplementedError
                    elif poll_type == PollTypes.SET_USER_PERMISSIONS:
                        message.reply_text('setting user permissions')
                        raise NotImplementedError
                    elif poll_type == PollTypes.SET_ROLE_PERMISSIONS:
                        message.reply_text('setting role permission')
                        raise NotImplementedError
                    elif poll_type == PollTypes.SET_DEFAULT_ROLE:
                        message.reply_text('setting default role')
                        raise NotImplementedError
                else:
                    logger.warning(f'{user_log_str(message)} has tried to'
                                   'vote in an admin poll not created by him.'
                                    'The creator of the poll '
                                   f'({data["creator_user_id"]}) may have'
                                   ' gone rogue.'
                                   )
                #poll_id, poll_type, creator_user_id, extra_data
            except ValueError:
                pass
        self.broadcast_message(update.message)

    def broadcast_message(self,
                          message,
                          permissions: Permissions = Permissions.RECEIVE):
        # Select only users whose permissions match
        # Banned and inactive users are automatically filtered by the database
        effective_users = filter(lambda x: permissions in x.permissions,
                                 self._db_man.get_active_users())

        if isinstance(message, Message) and \
                type(message.effective_attachment) not in \
                self._message_forward_map:
            message.reply_text('Unsupported message type '
                               f'{type(message.effective_attachment)}')
        else:
            for user in effective_users:
                self.send_or_forward_msg(user, message)

            # Trying to free some memory
            self._poll_pool = {}

    @messagequeue.queuedmessage
    def send_or_forward_msg(self, user, message,
                            parse_mode=ParseMode.MARKDOWN_V2):
        '''
        Sends the anonymized message to the specified user. If the user has the
        VIEW_CLEAR_MSGS permission the message is forwarded
        '''
        logger.debug(f'Relaying message to {user}')
        if isinstance(message, Message):
            if Permissions.VIEW_CLEAR_MSGS in user.permissions:
                msg = self._updater.bot.forward_message(
                    chat_id=user.id,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
            else:
                msg = self\
                    ._message_forward_map[type(message.effective_attachment)](
                        user,
                        message
                    )

            # Batch registering is more efficient but harder to implement due
            # to the delayed message queue
            self._db_man.register_messages([
                {
                    'sender_id': message.from_user.id,
                    'receiver_id': msg.chat_id,
                    'sender_message_id': message.message_id,
                    'receiver_message_id': msg.message_id,
                    'unix_sent_date': msg.date
                }
            ])
        else:
            msg = self._updater.bot.send_message(
                user.id,
                message,
                parse_mode=parse_mode
            )
            self._db_man.register_messages([
                {
                    'sender_id': self._updater.bot.id,
                    'receiver_id': msg.chat_id,
                    'sender_message_id': 0,
                    'receiver_message_id': msg.message_id,
                    'unix_sent_date': msg.date
                }
            ])
