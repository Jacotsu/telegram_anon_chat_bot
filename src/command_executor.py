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
import sys
from telegram.ext import CommandHandler
from telegram.constants import MAX_MESSAGE_LENGTH
from utils import log_action, chunk_string
from security import execute_if_hierarchy_is_respected
from custom_logging import user_log_str
from custom_filters import ActiveUsersFilter, UnbannedUsersFilter,\
        PassedCaptchaFilter, AntiFloodFilter, CommandPermissionsFilter
from database import DatabaseManager
from user_resolver import UserResolver
from custom_dataclasses import User
from permissions import Permissions

logger = logging.getLogger(__name__)


class CommandExecutor:
    def __init__(self,
                 config,
                 updater,
                 database_manager,
                 message_broker,
                 captcha_manager):
        self._config = config
        self._db_man = database_manager
        self._updater = updater
        self._msg_broker = message_broker
        self._captcha_manager = captcha_manager
        self._usr_resolver = UserResolver(config)

        self._default_permissions = Permissions.NONE
        for perm in self._config["Users"]["DefaultPermissions"].split():
            try:
                self._default_permissions |= Permissions[perm.strip()]
            except KeyError:
                logger.error('Invalid permission in default users '
                             f'permissions {perm}')
                sys.exit(1)

        authed_user_filters = ActiveUsersFilter(self._db_man) &\
            UnbannedUsersFilter(self._db_man) &\
            AntiFloodFilter(self._db_man, config) &\
            PassedCaptchaFilter(self._db_man, self._captcha_manager)

        self.commands = {
            'join': {
                'description': 'Join the chat',
                'permissions_required': Permissions.NONE,
                'usage': '/join',
                'filters': UnbannedUsersFilter(self._db_man) &
                AntiFloodFilter(self._db_man, config) &
                PassedCaptchaFilter(
                    self._db_man,
                    self._captcha_manager
                ),
                'callback': self.join
            },
            'quit': {
                'description': 'Quits the chat',
                'permissions_required': Permissions.NONE,
                'usage': '/quit',
                'filters': authed_user_filters,
                'callback': self.quit
            },
            'help': {
                'description': 'Shows the help page',
                'permissions_required': Permissions.SEND_CMD,
                'usage': '/help',
                'filters': authed_user_filters,
                'callback': self.help
            },
            'ping': {
                'description': 'Shows if the bot is online',
                'permissions_required': Permissions.SEND_CMD,
                'usage': '/ping',
                'filters': authed_user_filters,
                'callback': self.ping
            },

            # ---------------------- [ADMINISTRATION] -------------------------

            'ban': {
                'description': 'Bans a user from the chat. '
                'if no username or user_id is specified, this command must'
                'be issued as a reply; The original sender will be banned in'
                'this case',
                'permissions_required': Permissions.SEND_CMD | Permissions.BAN,
                'usage': '/ban [username|user_id] [reason]',
                'filters': authed_user_filters,
                'callback': self.ban
            },
            'unban': {
                'description': 'Unbans a user from the chat. ',
                'permissions_required': Permissions.SEND_CMD | Permissions.BAN,
                'usage': '/unban {username|user_id}',
                'filters': authed_user_filters,
                'callback': self.ban
            },
            'kick': {
                'description': 'Kicks the user from the chat. '
                'if no username or user_id is specified, this command must'
                'be issued as a reply; The original sender will be kicked in'
                'this case',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.KICK,
                'usage': '/kick [username|user_id] [reason]',
                'filters': authed_user_filters,
                'callback': self.kick
            },

            # ----------------------- [PERMISSIONS] ---------------------------

            'set_default_permissions': {
                'description': 'Sets the default permissions for new users'
                'Permissions are specified a space separated keywords.'
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_DEFAULT_PERMISSIONS,
                'usage': '/set_default_permissions {new_permissions}',
                'filters': authed_user_filters,
                'callback': self.ping
            },

            'show_default_permissions': {
                'description': 'Shows the default permissions',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SHOW_DEFAULT_PERMISSIONS,
                'usage': '/show_default_permissions',
                'filters': authed_user_filters,
                'callback': self.ping
            },
            'show_all_permissions': {
                'description': 'Shows all available permissions',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SHOW_ALL_PERMISSIONS,
                'usage': '/show_all_permissions',
                'filters': authed_user_filters,
                'callback': self.ping
            },
            'set_user_permissions': {
                'description': 'Sets the user\'s permissions'
                'if no username or user_id is specified, this command must'
                'be issued as a reply; The original sender will be banned in'
                'this case'
                'Permissions are specified a space separated keywords.'
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_USER_PERMISSIONS,
                'usage': '/set_user_permissions [username|user_id] '
                '{permissions}',
                'filters': authed_user_filters,
                'callback': self.ping
            },

            # -------------------- [CAPTCHA MANAGEMENT] -----------------------

            'waive_captcha': {
                'description': 'Waives the captcha of a user.'
                'if no username or user_id is specified, this command must'
                'be issued as a reply; The original sender will be banned in'
                'this case',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.WAIVE_CAPTCHA,
                'usage': '/waive_captcha {username|user_id}',
                'filters': authed_user_filters,
                'callback': self.ping
            },
            'reset_captcha': {
                'description': 'Resets the captcha of a user.'
                'if no username or user_id is specified, this command must'
                'be issued as a reply; The original sender\'s captcha will be '
                'reset',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.RESET_CAPTCHA,
                'usage': '/reset_captcha [username|user_id]',
                'filters': authed_user_filters,
                'callback': self.ping
            },

            # -------------------- [ROLES MANAGEMENT] -------------------------

            'create_role': {
                'description': 'Creates a new role.'
                'Permissions are specified a space separated keywords.'
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.CREATE_ROLE,
                'usage': '/create_role {role_name} {role_power} '
                '{role_permissions}',
                'filters': authed_user_filters,
                'callback': self.ping
            },
            'set_default_role': {
                'description': 'Sets the new default role.',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_DEFAULT_ROLE,
                'usage': '/set_default_role {role_name}',
                'filters': authed_user_filters,
                'callback': self.ping
            },
            'set_role_permissions': {
                'description': 'Sets the role permissions.'
                'Permissions are specified a space separated keywords.'
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.EDIT_ROLE | Permissions.SET_USER_PERMISSIONS,
                'usage': '/set_role_permissions {permissions}',
                'filters': authed_user_filters,
                'callback': self.ping
            },
            'set_role_power': {
                'description': 'Sets the role power. The power is an '
                'integer number. You cannot change the power of your role, '
                'the power or roles which have more power than you',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.EDIT_ROLE,
                'usage': '/set_role_power {power}',
                'filters': authed_user_filters,
                'callback': self.ping
            },
            'delete_role': {
                'description': 'Deletes a role'
                'integer number. You cannot delete a role whose power is '
                'higher than yours',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.DELETE_ROLE,
                'usage': '/delete_role {role_name}',
                'filters': authed_user_filters,
                'callback': self.ping
            },
            'set_user_role': {
                'description': 'Sets the role of a user. '
                'if no username or user_id is specified, this command must'
                'be issued as a reply; The original sender role will be '
                'changed in this case. If no role is specified, the default'
                'one will be set. '
                'You cannot change your own role, promote people to roles '
                'whose power is equal or higher than your role',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_USER_ROLE,
                'usage': '/set_user_role [username|user_id] [new_role]',
                'filters': authed_user_filters,
                'callback': self.ping
            },

            # ------------------ [LOGGING] --------------------------

            'get_logs': {
                'description': 'Gets the latest log'
                'You can specify a start date and an end date if you wish. '
                'If none is specified the last 50 entries are displayed.',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.VIEW_LOGS,
                'usage': '/get_logs [start_date] [end_date]',
                'filters': authed_user_filters,
                'callback': self.ping
            },

            'view_user_info': {
                'description': 'Shows the info of a user. '
                'if no username or user_id is specified, this command must'
                'be issued as a reply',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.VIEW_USER_INFO,
                'usage': '/view_user_info [username/user id]',
                'filters': authed_user_filters,
                'callback': self.ping
            },

            # ------------------ [BANNERS] --------------------
            'set_banner': {
                'description': 'Lets you set the join/quit message, '
                'If none is specified the respective banner will be disabled',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_BANNERS,
                'usage': '/set_banner {join|quit} [banner message]',
                'filters': authed_user_filters,
                'callback': self.ping
            }
        }

        cmd_filter = CommandPermissionsFilter(self._db_man,
                                              self.commands)

        message_dispatcher = updater.dispatcher

        for cmd_name, cmd_dict in self.commands.items():
            message_dispatcher.add_handler(
                CommandHandler(cmd_name,
                               cmd_dict['callback'],
                               filters=cmd_dict['filters'] & cmd_filter)
            )
            logger.debug(f'Registered {cmd_name}: {cmd_dict["callback"]}')

        bot = updater.bot

        # Sets the public commands
        public_commands = map(lambda x: (x[0],
                                         x[1]['description']),
                              filter(lambda x:
                                     x[1]['permissions_required'] ==
                                     Permissions.NONE,
                                     self.commands.items()))
        bot.set_my_commands([*public_commands])

    # General commands
    @log_action(logger)
    def join(self, update, context):
        tg_user = update.message.from_user
        # Creates a new user if it doesn't exist
        usual = self._db_man.user_exists(tg_user.id)
        user = User(self._db_man, tg_user.id, self._default_permissions)

        join_banner = self._config['Banners']['JoinBanner'] or \
            'Congratulations you have joined the chat'
        rejoin_banner = self._config['Banners']['RejoinBanner'] or \
            'Welcome back'

        if usual:
            if not user.is_active:
                logger.info(
                    f'{user_log_str(update)} rejoined the chat'
                )
                update.message.reply_text(rejoin_banner)
                user.join()
        else:
            logger.info(
                f'{user_log_str(update)} joined the chat'
            )
            update.message.reply_text(join_banner)
            user.join()

    @log_action(logger)
    def quit(self, update, context):
        tg_user = update.message.from_user
        User(self._db_man, tg_user.id).quit()

        quit_banner = self._config['Banners']['QuitBanner'] or \
            'K, Bye'
        update.message.reply_text(quit_banner)
        logger.info(
            f'{user_log_str(update)} quit the chat'
        )

    @log_action(logger)
    def ping(self, update, context):
        update.message.reply_text("pong")

    @log_action(logger)
    def help(self, update, context):
        '''
        Sends the help text to the user based on what permissions he has
        '''
        user = User(self._db_man,
                    update.message.from_user.id,
                    update.message.chat.id)
        user_permissions = user.permissions
        msg_string = '*anon chat bot help page*\nParameters between curly '\
            'braces ({}) are compulsory, parameters between square brackets '\
            '([]) are optional. When parameters are separated by a pipe (|) '\
            'it means that only one of the proposed options should be '\
            'passed.\nCommands:\n'
        for cmd_name, cmd_dict in self.commands.items():
            if cmd_dict['permissions_required'] in user_permissions:
                msg_string += f'*{cmd_name}*:\nusage: `{cmd_dict["usage"]}`\n'\
                        f'```\n{cmd_dict["description"]}\n```\n'

        for chunk in chunk_string(msg_string, MAX_MESSAGE_LENGTH):
            update.message.reply_markdown(msg_string)

    # Admin commands

    @log_action(logger)
    def ban(self, update, context):
        user_id = update.message.id

        replied_msg = update.message.reply_to_message

        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        if replied_msg:
            reason = split_cmd[1:]
            user_id = self._usr_resolver.resolve(replied_msg)

            admin_user = User(self._db_man, update.message.from_user.id)
            user_to_ban = User(self._db_man, user_id)

            execute_if_hierarchy_is_respected(
                admin_user, user_to_ban, lambda : user_to_ban.ban(reason),
                update,
                f'{user_log_str(replied_msg)} has been banned',
                'You cannot ban your peers/superiors',
                f'{user_log_str(replied_msg)} has been banned by '
                f'{user_log_str(update)}',
                f'{user_log_str(update)} has tried to ban his '
                f'peer/superior {split_cmd[1]}'
            )
        else:
            if split_cmd_len >= 2:
                reason = split_cmd[2:]
                user_id = self._usr_resolver.resolve(split_cmd[1])
                if user_id:
                    user_to_ban = User(self._db_man, user_id)
                    admin_user = User(self._db_man,
                                      update.message.from_user.id)

                    execute_if_hierarchy_is_respected(
                        admin_user, user_to_ban,
                        lambda : user_to_ban.ban(reason), update,
                        f'{user_log_str(replied_msg)} has been banned',
                        'You cannot ban your peers/superiors',
                        f'{user_log_str(replied_msg)} has been banned by '
                        f'{user_log_str(update)}',
                        f'{user_log_str(update)} has tried to ban his '
                        f'peer/superior {split_cmd[1]}'
                    )
                else:
                    update.message.reply_text(
                        f'{split_cmd[1]} is an invalid username/userid'
                    )
            else:
                update.message.reply('Wrong number of parameters passed to '
                                     'ban')

    @log_action(logger)
    def kick(self, update, context):
        pass

    @log_action(logger)
    def set_permissions(self, update, context):
        pass
