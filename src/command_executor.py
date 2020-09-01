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
import dateparser
from telegram.ext import CommandHandler
from telegram.constants import MAX_MESSAGE_LENGTH
from utils import log_action, chunk_string, \
    get_permissions_from_config_section, create_and_register_poll,\
    split_cmd_line, escape_markdown_chars
from security import is_hierarchy_respected,\
    is_role_hierarchy_respected
from custom_logging import user_log_str
from custom_filters import ActiveUsersFilter, UnbannedUsersFilter,\
        PassedCaptchaFilter, AntiFloodFilter, CommandPermissionsFilter
from database import DatabaseManager
from user_resolver import UserResolver
from custom_exceptions import UserResolverError
from custom_dataclasses import User, Role
from permissions import Permissions
from poll_types import PollTypes
from misc import user_join

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
        self._usr_resolver = UserResolver(database_manager, config)

        authed_user_filters = ActiveUsersFilter(self._db_man) &\
            UnbannedUsersFilter(self._db_man, self._msg_broker) &\
            AntiFloodFilter(self._db_man, config, self._msg_broker) &\
            PassedCaptchaFilter(self._db_man,
                                self._captcha_manager,
                                config,
                                self._msg_broker)

        self.commands = {
            'join': {
                'description': 'Join the chat',
                'permissions_required': Permissions.NONE,
                'usage': '/join',
                'filters': UnbannedUsersFilter(self._db_man) &
                AntiFloodFilter(self._db_man, config, self._msg_broker) &
                PassedCaptchaFilter(
                    self._db_man,
                    self._captcha_manager,
                    config,
                    self._msg_broker
                ) & ~ActiveUsersFilter(self._db_man),
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
                'if no username or user_id is specified, this command must '
                'be issued as a reply; The original sender will be banned in '
                'this case',
                'permissions_required': Permissions.SEND_CMD | Permissions.BAN,
                'usage': '/ban [username|user_id], [end_date], [reason]',
                'filters': authed_user_filters,
                'callback': self.ban
            },
            'unban': {
                'description': 'Unbans a user from the chat.',
                'permissions_required': Permissions.SEND_CMD | Permissions.BAN,
                'usage': '/unban {username|user_id}, [reason]',
                'filters': authed_user_filters,
                'callback': self.unban
            },
            'kick': {
                'description': 'Kicks the user from the chat. '
                'if no username or user_id is specified, this command must '
                'be issued as a reply; The original sender will be kicked in '
                'this case',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.KICK,
                'usage': '/kick [username|user_id], [reason]',
                'filters': authed_user_filters,
                'callback': self.kick
            },
            'delete': {
                'description': 'Deletes the replied message',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.DELETE_MESSAGE,
                'usage': '/delete',
                'filters': authed_user_filters,
                'callback': self.delete
            },

            # ----------------------- [PERMISSIONS] ---------------------------

            'set_default_permissions': {
                'description': 'Sets the default permissions for new users '
                'Permissions are specified as comma separated keyphrases. '
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_DEFAULT_PERMISSIONS |
                Permissions.SEND_ANON_POLL,
                'usage': '/set_default_permissions {new_permissions}',
                'filters': authed_user_filters,
                'callback': self.set_default_permissions
            },

            'show_default_permissions': {
                'description': 'Shows the default permissions',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SHOW_DEFAULT_PERMISSIONS,
                'usage': '/show_default_permissions',
                'filters': authed_user_filters,
                'callback': self.show_default_permissions
            },
            'show_all_permissions': {
                'description': 'Shows all available permissions',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SHOW_ALL_PERMISSIONS,
                'usage': '/show_all_permissions',
                'filters': authed_user_filters,
                'callback': self.show_all_permissions
            },
            'set_user_permissions': {
                'description': 'Sets the user\'s permissions'
                'if no username or user_id is specified, this command must '
                'be issued as a reply; The original sender will be banned in '
                'this case '
                'Permissions are specified a space separated keywords. '
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_USER_PERMISSIONS |
                Permissions.SEND_ANON_POLL,
                'usage': '/set_user_permissions [username|user_id]',
                'filters': authed_user_filters,
                'callback': self.set_user_permissions
            },

            # -------------------- [CAPTCHA MANAGEMENT] -----------------------

            'waive_captcha': {
                'description': 'Waives the captcha of a user. '
                'if no username or user_id is specified, this command must '
                'be issued as a reply; The original sender will be banned in '
                'this case',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.WAIVE_CAPTCHA,
                'usage': '/waive_captcha {username|user_id}',
                'filters': authed_user_filters,
                'callback': self.waive_captcha
            },
            'reset_captcha': {
                'description': 'Resets the captcha of a user. '
                'if no username or user_id is specified, this command must '
                'be issued as a reply; The original sender\'s captcha will be '
                'reset',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.RESET_CAPTCHA,
                'usage': '/reset_captcha [username|user_id]',
                'filters': authed_user_filters,
                'callback': self.reset_captcha
            },

            # -------------------- [ROLES MANAGEMENT] -------------------------

            'create_role': {
                'description': 'Creates a new role. '
                'Permissions are specified a space separated keywords. '
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.CREATE_ROLE,
                'usage': '/create_role {role_name}, {role_power}',
                'filters': authed_user_filters,
                'callback': self.create_role
            },
            'show_roles': {
                'description': 'Shows available roles',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.EDIT_ROLE,
                'usage': '/show_roles',
                'filters': authed_user_filters,
                'callback': self.show_roles
            },
            'set_default_role': {
                'description': 'Sets the new default role.',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_DEFAULT_ROLE,
                'usage': '/set_default_role {role_name}',
                'filters': authed_user_filters,
                'callback': self.set_default_role
            },
            'show_default_role': {
                'description': 'Shows the default role.',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_DEFAULT_ROLE,
                'usage': '/show_default_role',
                'filters': authed_user_filters,
                'callback': self.show_default_role
            },
            'set_role_permissions': {
                'description': 'Sets the role permissions. '
                'Permissions are specified a space separated keywords. '
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.EDIT_ROLE | Permissions.SET_USER_PERMISSIONS |
                Permissions.SEND_ANON_POLL,
                'usage': '/set_role_permissions {role_name}',
                'filters': authed_user_filters,
                'callback': self.set_role_permissions
            },
            'set_role_power': {
                'description': 'Sets the role power. The power is an '
                'integer number. You cannot change the power of your role, '
                'the power or roles which have more power than you',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.EDIT_ROLE,
                'usage': '/set_role_power {power}',
                'filters': authed_user_filters,
                'callback': self.set_role_power
            },
            'delete_role': {
                'description': 'Deletes a role'
                'integer number. You cannot delete a role whose power is '
                'higher than yours',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.DELETE_ROLE,
                'usage': '/delete_role {role_name}',
                'filters': authed_user_filters,
                'callback': self.delete_role
            },
            'set_user_role': {
                'description': 'Sets the role of a user. '
                'if no username or user_id is specified, this command must '
                'be issued as a reply; The original sender role will be '
                'changed in this case. If no role is specified, the default '
                'one will be set. '
                'You cannot change your own role, promote people to roles '
                'whose power is equal or higher than your role',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_USER_ROLE,
                'usage': '/set_user_role [username|user_id], [new_role]',
                'filters': authed_user_filters,
                'callback': self.set_user_role
            },

            # ------------------ [LOGGING] --------------------------

            'get_logs': {
                'description': 'Gets the latest log '
                'You can specify a start date and an end date if you wish. '
                'If none is specified the last 50 entries are displayed.',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.VIEW_LOGS,
                'usage': '/get_logs [start_date], [end_date]',
                'filters': authed_user_filters,
                'callback': self.get_logs
            },

            'view_user_info': {
                'description': 'Shows the info of a user. '
                'if no username or user_id is specified, this command must '
                'be issued as a reply',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.VIEW_USER_INFO,
                'usage': '/view_user_info [username/user id]',
                'filters': authed_user_filters,
                'callback': self.view_user_info
            },

            # ------------------ [BANNERS] --------------------
            'set_banner': {
                'description': 'Lets you set the join/rejoin/quit message, '
                'If none is specified the default banner will be used ',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_BANNERS,
                'usage': '/set_banner {join|rejoin|quit}, [banner message]',
                'filters': authed_user_filters,
                'callback': self.set_banner
            },
            'show_banners': {
                'description': 'Shows you the current banners',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.SET_BANNERS,
                'usage': '/show_banners',
                'filters': authed_user_filters,
                'callback': self.show_banners
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
        user = User(self._db_man, tg_user)
        user_join(user, self._config, self._msg_broker)

    @log_action(logger)
    def quit(self, update, context):
        tg_user = update.message.from_user
        user = User(self._db_man, tg_user)

        self._msg_broker.send_or_forward_msg(
            user,
            self._config['Banners']['Quit']
        )
        user.quit()
        logger.info(
            f'{user} quit the chat'
        )

    @log_action(logger)
    def ping(self, update, context):
        self._msg_broker.send_or_forward_msg(
            User(self._db_man, update.message.from_user),
            'pong'
        )

    @log_action(logger)
    def help(self, update, context):
        '''
        Sends the help text to the user based on what permissions he has
        '''
        user = User(self._db_man, update.message.from_user)
        user_permissions = user.permissions
        msg_string = '*anon chat bot help page*\nParameters between curly '\
            'braces ({}) are compulsory, parameters between square brackets '\
            '([]) are optional\. When parameters are separated by a pipe (|) '\
            'it means that only one of the proposed options should be '\
            'passed\. Use a comma (,) to separate the arguments\.\nCommands:\n'
        for cmd_name, cmd_dict in self.commands.items():
            if cmd_dict['permissions_required'] in user_permissions:
                msg_string += f'*{cmd_name}*:\nusage: `{cmd_dict["usage"]}`\n'\
                        f'```\n{cmd_dict["description"]}\n```\n'

        update.message.reply_markdown(msg_string)

    # ------------------------- [ADMIN COMMANDS] ------------------------------

    @log_action(logger)
    def ban(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        replied_msg = update.message.reply_to_message
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        try:
            user_to_ban = self._usr_resolver\
                .acquire_target_user_from_cmd(update)

            if user_to_ban.is_banned:
                raise ValueError(f'{user_to_ban} is already banned')

            ban_end_date = None
            reason = ''
            if replied_msg:
                if split_cmd_len == 1:
                    ban_end_date = dateparser.parse(
                        split_cmd[0], settings={'TIMEZONE': 'UTC'}
                    )
                    if not ban_end_date:
                        reason = split_cmd[0]

                elif split_cmd_len == 2:
                    ban_end_date = dateparser.parse(
                        split_cmd[0], settings={'TIMEZONE': 'UTC'}
                    )
                    if not ban_end_date:
                        raise ValueError(f'{split_cmd[0]} is an invalid date')
                    reason = split_cmd[1]
                else:
                    raise ValueError('Wrong number of parameters passed '
                                     'to ban')
            else:
                if split_cmd_len == 1:
                    reason = ''
                elif split_cmd_len == 2:
                    ban_end_date = dateparser.parse(
                        split_cmd[0], settings={'TIMEZONE': 'UTC'}
                    )
                    if not ban_end_date:
                        reason = ''
                elif split_cmd_len == 3:
                    ban_end_date = dateparser.parse(
                        split_cmd[1], settings={'TIMEZONE': 'UTC'}
                    )
                    if not ban_end_date:
                        raise ValueError(f'{split_cmd[0]} is an invalid date')
                    reason = split_cmd[2]
                else:
                    raise ValueError('Wrong number of parameters passed '
                                     'to ban')

            if is_hierarchy_respected(admin_user, user_to_ban):
                if ban_end_date:
                    user_to_ban.ban(f'{reason}\n' if reason else '',
                                    ban_end_date)
                else:
                    user_to_ban.ban(f'{reason}\n' if reason else '')

                if reason:
                    if ban_end_date:
                        user_banned_str = 'You have been banned until '\
                            f'{ban_end_date} for: {reason}'
                        admin_ban_str = f'{user_to_ban} has been banned until'\
                            f' {ban_end_date}'
                        log_str = f'{user_to_ban} has been banned until '\
                            f'{ban_end_date} by {admin_user} for: {reason}'
                    else:
                        user_banned_str = f'You have been banned for: {reason}'
                        admin_ban_str = f'{user_to_ban} has been banned'
                        log_str = f'{user_to_ban} has been banned by '\
                            f'{admin_user} for: {reason}'
                else:
                    if ban_end_date:
                        user_banned_str = f'You have been banned until '\
                            '{ban_end_date}'
                        admin_ban_str = f'{user_to_ban} has been banned until'\
                            f' {ban_end_date}'
                        log_str = f'{user_to_ban} has been banned until '\
                            f'{ban_end_date} by {admin_user}'
                    else:
                        user_banned_str = f'You have been banned'
                        admin_ban_str = f'{user_to_ban} has been banned'
                        log_str = f'{user_to_ban} has been banned by '\
                            f'{admin_user}'

                self._msg_broker.send_or_forward_msg(
                    user_to_ban,
                    escape_markdown_chars(user_banned_str)
                )
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(admin_ban_str)
                )
                logger.info(log_str)
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    'You cannot ban your peers/superiors'
                )
                logger.warning(f'{admin_user} has tried to ban his '
                               f'peer/superior {user_to_ban}')

        except (UserResolverError, ValueError) as e:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(str(e))
            )

    @log_action(logger)
    def unban(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        try:
            user_to_unban = self._usr_resolver\
                .acquire_target_user_from_cmd(update)

            if split_cmd_len == 1:
                reason = ''
            elif split_cmd_len == 2:
                reason = split_cmd[1]
            else:
                raise ValueError(
                    'Wrong number of parameters passed to unban'
                )

            if user_to_unban.is_banned:
                # Forbid unbanning of higher ranks/peers to avoid
                # takeovers from rogues admins/mods
                if is_hierarchy_respected(admin_user, user_to_unban):
                    admin_msg = f'{user_to_unban} has been unbanned'
                    if reason:
                        log_msg = f'{user_to_unban} has been unbanned by '\
                            f'{admin_user} for {reason}'
                        user_to_unban.unban(f'Unbanned by {admin_user} '
                        f'for {reason}')
                    else:
                        log_msg = f'{user_to_unban} has been unbanned by '\
                            f'{admin_user} for {reason}'
                        user_to_unban.unban()

                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        escape_markdown_chars(admin_msg)
                    )
                    logger.info(log_msg)
                else:
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        'You cannot unban your peers/superiors'
                    )
                    logger.warning(f'{admin_user} has tried to unban his '
                                   f'peer/superior {user_to_unban}' )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'{user_to_unban} is not banned'
                    )
                )

        except (UserResolverError, ValueError) as e:
            update.message.reply_text(str(e))

    @log_action(logger)
    def kick(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        replied_msg = update.message.reply_to_message
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        try:
            reason = ''

            if replied_msg:
                reason = split_cmd[0:]
            else:
                if split_cmd_len == 1:
                    pass
                elif split_cmd_len == 2:
                    reason = split_cmd[1:]
                else:
                    raise ValueError('Wrong number of parameters passed to '
                                     'kick')

            user_to_kick = self._usr_resolver\
                .acquire_target_user_from_cmd(update)
            if is_hierarchy_respected(admin_user, user_to_kick):
                user_to_kick.kick()
                self._msg_broker.send_or_forward_msg(
                    user_to_kick,
                    escape_markdown_chars(
                        f'You have been kicked for: {reason}'
                    )
                )
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'{user_to_kick} has been kicked'
                    ),
                )
                logger.info(
                    f'{user_to_kick} has been kicked by {admin_user} for '
                    f'{reason}',
                )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    'You cannot kick your peers/superiors',
                )
                logger.warning(
                    f'{admin_user} has tried to kick his peer/superior '
                    f'{user_to_kick}'
                )
        except (UserResolverError, ValueError) as e:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(str(e))
            )

    @log_action(logger)
    def delete(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        replied_msg = update.message.reply_to_message
        message_sender = self._db_man.get_message_sender(replied_msg)

        if admin_user == message_sender or\
           is_hierarchy_respected(admin_user, message_sender):
            if replied_msg:
                messages_to_delete = self._db_man.get_messages_to_delete(
                    admin_user.id,
                    replied_msg.message_id)
                for msg in messages_to_delete:
                    self._updater.bot.delete_message(
                        msg['chat_id'], msg['message_id'])
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    'You must reply to a message to delete it',
                )
        else:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                'You cannot delete messages from your superiors',
            )
            logger.warning(f'{admin_user} has tried to delete a message '
                           '{replied_msg} sent by his superior '
                           f'{message_sender}')

    @log_action(logger)
    def set_default_permissions(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        create_and_register_poll(
            self._db_man,
            update,
            'Select the new default permissions',
            # Avoid privilege escalation by only allowing to set already owned
            # permissions as default
            [str(perm) for perm in admin_user.permissions],
            PollTypes.SET_DEFAULT_PERMISSIONS
        )

    @log_action(logger)
    def show_default_permissions(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        default_role = Role(self._db_man, self._config['Roles']['DefaultRole'])
        self._msg_broker.send_or_forward_msg(
            admin_user,
            f'*The default permissions are*:\n{str(default_role.permissions)}'
        )

    @log_action(logger)
    def show_all_permissions(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        self._msg_broker.send_or_forward_msg(
            admin_user,
            f'*List of permissions:\n*{str(Permissions.ALL)}'
        )

    @log_action(logger)
    def set_user_permissions(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        try:
            user_to_set_perms = self._usr_resolver\
                .acquire_target_user_from_cmd(update)

            if is_hierarchy_respected(admin_user, user_to_set_perms):
                create_and_register_poll(
                    self._db_man,
                    update,
                    'Select the new user permissions for '
                    f'{user_to_set_perms}',
                    # Avoid privilege escalation by only allowing to set
                    # already owned permissions as default
                    [str(perm) for perm in admin_user.permissions],
                    PollTypes.SET_USER_PERMISSIONS
                )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    'You cannot change the permissions of your peers/superiors'
                )
                logger.warning(
                    f'{admin_user} has tried to change the permissions of his '
                    'peer/superior {user_to_set_perms}'
                )
        except (UserResolverError, ValueError) as e:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(str(e)),
            )

    @log_action(logger)
    def waive_captcha(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)

        try:
            user_to_waive_captcha = self._usr_resolver\
                .acquire_target_user_from_cmd(update)
            if is_hierarchy_respected(admin_user, user_to_waive_captcha):
                user_to_waive_captcha.captcha_status.passed = True

                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'{user_to_waive_captcha}\'s captcha has been waived'
                    )
                )
                logger.info(
                    f'{user_to_waive_captcha}\' captcha has been waived by '
                    f'{admin_user}'
                )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    'You cannot waive the captcha of your peers/superiors'
                )
                logger.warning(
                    f'{admin_user} has tried to waive the captcha '
                    f'of his peer/superior {user_to_waive_captcha}'
                )

        except (UserResolverError, ValueError) as e:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(str(e)),
            )

    @log_action(logger)
    def reset_captcha(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)

        try:
            user_to_reset_captcha = self._usr_resolver\
                .acquire_target_user_from_cmd(update)

            if is_hierarchy_respected(admin_user, user_to_reset_captcha):
                user_to_reset_captcha.captcha_status.passed = False
                user_to_reset_captcha.captcha_status.failed_attempts = 0

                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'{user_to_reset_captcha}\'s captcha has been waived'
                    )
                )
                logger.info(
                    f'{user_to_reset_captcha}\' captcha has been waived by '
                    f'{admin_user}'
                )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    'You cannot waive the captcha of your peers/superiors'
                )
                logger.warning(
                    f'{admin_user} has tried to waive the captcha '
                    f'of his peer/superior {user_to_reset_captcha}'
                )
        except (UserResolverError, ValueError) as e:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(str(e)),
            )

    @log_action(logger)
    def create_role(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        try:
            if split_cmd_len == 2 and split_cmd[1]:
                role_name = split_cmd[0]
                role_power = int(split_cmd[1])
                if self._db_man.does_role_exist(role_name):
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        escape_markdown_chars(
                            f'Role {role_name} already exists'
                        )
                    )
                elif role_power > admin_user.role.power:
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        'You cannot create role whose power is higher than '
                        'yours'
                    )
                    logger.warning(f'{admin_user} has tried to create a role '
                                   'whose power is higher than his')
                else:
                    Role(self._db_man, role_name, role_power)
                    # Sets role's permissions
                    # Max 10 options per poll
                    create_and_register_poll(
                        self._db_man,
                        update,
                        'Select the role\'s permissions',
                        # Avoid privilege escalation by only allowing to set
                        # already owned permissions
                        [str(perm) for perm in admin_user.permissions],
                        PollTypes.SET_ROLE_PERMISSIONS
                    )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    'Wrong number of parameters passed to create role'
                )
        except ValueError as e:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(str(e)),
            )

    @log_action(logger)
    def show_roles(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        msg = '*Current roles:*\n'
        for role in self._db_man.show_roles():
            role_str = str(role)
            role_name, role_permissions = role_str.split(':')
            msg += f'*{escape_markdown_chars(role_name)}*: '\
                f'{escape_markdown_chars(role_permissions)}\n\n'
        self._msg_broker.send_or_forward_msg(
            admin_user,
            msg
        )

    @log_action(logger)
    def set_default_role(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        if split_cmd_len == 1:
            if self._db_man.does_role_exist(split_cmd[0]):
                new_role = Role(self._db_man, split_cmd[0])
                # Only admins with higher power than set a role as default
                if is_role_hierarchy_respected(admin_user, new_role):
                    self._config['Roles']['DefaultRole'] = split_cmd[0]
                    self._config.write()
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        escape_markdown_chars(
                            f'Default role set to {new_role}'
                        )
                    )
                    logger.info(
                        f'{admin_user} has set the default role to {new_role}'
                    )
                else:
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        'You can\'t set a role whose power '
                        'or permissions are greater than yours as default'
                    )
                    logger.warning(
                        f'{user_log_str(update)} has tried to set a role '
                        'whose power or permissions are greater than his as '
                        'default'
                    )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'Role {split_cmd[0]} does not exist. '
                        'create it with /create_role'
                    )
                )
        else:

            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(
                    'Wrong number of parameters passed to /set_default_role'
                )
            )

    @log_action(logger)
    def show_default_role(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)

        default_role = self._config['Roles']['DefaultRole']
        self._msg_broker.send_or_forward_msg(
            admin_user,
            '*Default role is*: '
            f'{escape_markdown_chars(str(Role(self._db_man, default_role)))}'
        )

    @log_action(logger)
    def set_role_permissions(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        if split_cmd_len == 1:
            if self._db_man.does_role_exist(split_cmd[0]):
                new_role = Role(self._db_man, split_cmd[0])
                # Only admins with higher power than set a role as default
                if is_role_hierarchy_respected(admin_user, new_role):
                    # Sets role's permissions
                    create_and_register_poll(
                        self._db_man,
                        update,
                        'Select the role\'s permissions',
                        # Avoid privilege escalation by only allowing to
                        # set already owned permissions
                        [str(perm) for perm in admin_user.permissions],
                        PollTypes.SET_ROLE_PERMISSIONS
                    )
                else:
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        'You can\'t edit a role whose power '
                        'or permissions are greater than yours\.'
                    )
                    logger.warning(
                        f'{user_log_str(update)} has tried to edit a role '
                        'whose power or permissions are greater than his'
                    )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    f'Role {split_cmd[0]} does not exist\. '
                    'create it with /create_role'
                )
        else:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(
                    'Wrong number of parameters passed to '
                    '/set_role_permissions'
                )
            )

    @log_action(logger)
    def set_role_power(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        if split_cmd_len == 2:
            if self._db_man.does_role_exist(split_cmd[0]):
                role = Role(self._db_man, split_cmd[0])
                try:
                    new_power = int(split_cmd[1])
                    # Only admins with higher power than set a role as default
                    if admin_user.role.power > role.power:
                        if 0 <= new_power < admin_user.role.power:
                            role.power = new_power
                            self._msg_broker.send_or_forward_msg(
                                admin_user,
                                escape_markdown_chars(
                                    f'{split_cmd[0]}\'s power set to '
                                    f'{new_power}'
                                )
                            )
                        else:
                            self._msg_broker.send_or_forward_msg(
                                admin_user,
                                f'Invalid power value: {new_power}'
                            )
                    else:
                        self._msg_broker.send_or_forward_msg(
                            admin_user,
                            'You can\'t edit a role whose power is higher '
                            'than yours'
                        )
                        logger.warning(
                            f'{admin_user} has tried to edit a role '
                            'whose power is higher than his'
                        )
                except ValueError as e:
                    update.message.reply(e)
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'Role {split_cmd[0]} does not exist. '
                        'create it with /create_role'
                    )
                )
        else:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(
                    'Wrong number of parameters passed to /set_role_power'
                )
            )

    @log_action(logger)
    def delete_role(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        if split_cmd_len == 1 and split_cmd[0]:
            if self._db_man.does_role_exist(split_cmd[0]):
                role_to_delete = Role(self._db_man, split_cmd[0])
                # Only admins with higher power than set a role as default
                if admin_user.role.power > role_to_delete.power:
                    role_to_delete.delete()
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        escape_markdown_chars(
                            f'Deleted role: {role_to_delete}'
                        )
                    )
                    logger.info(
                        f'{admin_user} has deleted the role: {role_to_delete}'
                    )
                else:
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        'You can\'t delete a role whose power is higher '
                        'or equal to yours'
                    )
                    logger.warning(
                        f'{admin_user} has tried to delete a role '
                        'whose power is higher or equal to his'
                    )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'Role {split_cmd[0]} does not exist. '
                        'create it with /create_role'
                    )
                )
        else:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(
                    'Wrong number of parameters passed to /delete_role'
                )
            )

    @log_action(logger)
    def set_user_role(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        replied_msg = update.message.reply_to_message
        split_cmd = split_cmd_line(update.message.text)
        split_cmd_len = len(split_cmd)

        try:
            target_user = self._usr_resolver\
                .acquire_target_user_from_cmd(update)

            if replied_msg and split_cmd_len == 1:
                new_role_name = split_cmd[0].strip()
            elif split_cmd_len == 2:
                new_role_name = split_cmd[1].strip()
            else:
                raise ValueError(
                    'Wrong number of parameters passed '
                    'to /set_user_role'
                )

            if self._db_man.does_role_exist(new_role_name):
                new_role = Role(self._db_man, new_role_name)
                if is_hierarchy_respected(admin_user, target_user):
                    if is_role_hierarchy_respected(admin_user, new_role):
                        target_user.role = new_role
                        self._msg_broker.send_or_forward_msg(
                            admin_user,
                            escape_markdown_chars(
                                f'{target_user}\'s role has been set to '
                                f'{new_role}'
                            )
                        )
                        logger.info(
                            f'{target_user}\'s role has been set to '
                            f'{new_role} by {admin_user}'
                        )
                    else:
                        self._msg_broker.send_or_forward_msg(
                            admin_user,
                            'You cannot assign roles whose permissions/power '
                            'are greater than yours'
                        )
                        logger.warning(
                            f'{admin_user} has tried to assign a role '
                            f'({new_role}) with '
                            'greater power/permissions than his')
                else:
                    self._msg_broker.send_or_forward_msg(
                        admin_user,
                        'You cannot change the role of your peers/superiors'
                    )
                    logger.warning(
                        f'{admin_user} has tried to set the role of his '
                        f'peer/superior {target_user} to {new_role}')
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'Role {new_role_name} does not exist '
                        'create it with /create_role'
                    )
                )
        except (UserResolverError, ValueError) as e:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(str(e))
            )

    @log_action(logger)
    def get_logs(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        if split_cmd_len < 4:
            raise NotImplementedError

        else:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                'Wrong number of parameters passed to '
                'create role captcha'
            )
            return


        raise NotImplementedError

    @log_action(logger)
    def view_user_info(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        try:
            user = self._usr_resolver.acquire_target_user_from_cmd(update)
            join_log_str = escape_markdown_chars(
                "\n".join(map(lambda x: str(x), user.join_quit_log))
            )
            ban_log_str = escape_markdown_chars(
                "\n".join(map(lambda x: str(x), user.ban_log))
            )
            msg = '*User info*\n'\
                f'*First name*: {escape_markdown_chars(user.first_name)}\n'\
                f'*Last name*: {escape_markdown_chars(user.last_name)}\n'\
                f'*Username*: @{escape_markdown_chars(user.username)}\n'\
                f'*ID*: {user.id}\n'\
                f'*Role*: {escape_markdown_chars(str(user.role))}\n'\
                '*Permissions*: '\
                f'{escape_markdown_chars(str(user.permissions))}\n'\
                f'*Join log*: \n{join_log_str}\n'\
                f'*Ban log*: \n{ban_log_str}\n'

            self._msg_broker.send_or_forward_msg(
                admin_user,
                msg
            )
        except (ValueError, UserResolverError) as e:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                escape_markdown_chars(str(e))
            )

    @log_action(logger)
    def set_banner(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        split_cmd = split_cmd_line(update.message.text)
        split_cmd = [split_cmd[0], ",".join(split_cmd[1:]).strip()]

        if split_cmd[1]:
            if split_cmd[0] in self._config['Banners']:
                self._config['Banners'][split_cmd[0]] = split_cmd[1]
                self._config.write()

                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'{split_cmd[0]} set to: {split_cmd[1]}'
                    )
                )
            else:
                self._msg_broker.send_or_forward_msg(
                    admin_user,
                    escape_markdown_chars(
                        f'{split_cmd[0]} is an invalid banner name. click '
                        '/show_banners to show the current banners'
                    )
                )
        else:
            self._msg_broker.send_or_forward_msg(
                admin_user,
                'Wrong number of parameters passed to '
                'set banner'
            )

    @log_action(logger)
    def show_banners(self, update, context):
        admin_user = User(self._db_man, update.message.from_user)
        msg = '*Current banners:*\n'

        for banner_name, value in self._config['Banners'].items():
            msg += f'*{banner_name}*: {value}\n'

        self._msg_broker.send_or_forward_msg(
            admin_user,
            msg
        )
