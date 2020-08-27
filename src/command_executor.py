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
from utils import log_action, chunk_string, \
    get_permissions_from_config_section, create_and_register_poll
from security import execute_if_hierarchy_is_respected
from custom_logging import user_log_str
from custom_filters import ActiveUsersFilter, UnbannedUsersFilter,\
        PassedCaptchaFilter, AntiFloodFilter, CommandPermissionsFilter
from database import DatabaseManager
from user_resolver import UserResolver, UserResolverError
from custom_dataclasses import User, Role
from permissions import Permissions
from poll_types import PollTypes

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
                'if no username or user_id is specified, this command must '
                'be issued as a reply; The original sender will be banned in '
                'this case',
                'permissions_required': Permissions.SEND_CMD | Permissions.BAN,
                'usage': '/ban [username|user_id] [reason]',
                'filters': authed_user_filters,
                'callback': self.ban
            },
            'unban': {
                'description': 'Unbans a user from the chat.',
                'permissions_required': Permissions.SEND_CMD | Permissions.BAN,
                'usage': '/unban {username|user_id} [reason]',
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
                'usage': '/kick [username|user_id] [reason]',
                'filters': authed_user_filters,
                'callback': self.kick
            },

            # ----------------------- [PERMISSIONS] ---------------------------

            'set_default_permissions': {
                'description': 'Sets the default permissions for new users '
                'Permissions are specified a space separated keywords. '
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
                'usage': '/set_user_permissions [username|user_id] '
                '{permissions}',
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
                'usage': '/create_role {role_name} {role_power} '
                '{role_permissions}',
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
            'set_role_permissions': {
                'description': 'Sets the role permissions. '
                'Permissions are specified a space separated keywords. '
                'Issue /show_all_permissions for a complete list',
                'permissions_required': Permissions.SEND_CMD |
                Permissions.EDIT_ROLE | Permissions.SET_USER_PERMISSIONS |
                Permissions.SEND_ANON_POLL,
                'usage': '/set_role_permissions {role_name} {permissions}',
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
                'usage': '/set_user_role [username|user_id] [new_role]',
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
                'usage': '/get_logs [start_date] [end_date]',
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
                'usage': '/set_banner {join|rejoin|quit} [banner message]',
                'filters': authed_user_filters,
                'callback': self.set_banner
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
        user = User(self._db_man, tg_user.id)
        default_role_name = self._config['Roles']['DefaultRole']
        user.role = Role(self._db_man, default_role_name)

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
        def ban_and_send_reason(user: User, reason: str):
            user.ban(reason)
            self._updater.bot.send_message(
                user.user_id,
                f'You have been banned for: {reason}'
            )

        admin_user = User(self._db_man, update.message.from_user.id)
        replied_msg = update.message.reply_to_message
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        try:
            user_to_ban_id = self._usr_resolver\
                .acquire_target_user_from_cmd(update)
            if replied_msg:
                reason = split_cmd[1:]
            else:
                if split_cmd_len >= 2:
                    reason = split_cmd[2:]
                else:
                    update.message.reply('Wrong number of parameters passed '
                                         'to ban')
                    return

            user_to_ban = User(self._db_man, user_to_ban_id)
            execute_if_hierarchy_is_respected(
                admin_user, user_to_ban,
                lambda: ban_and_send_reason(user_to_ban, reason),
                update,
                f'{user_log_str(replied_msg)} has been banned',
                'You cannot ban your peers/superiors',
                f'{user_log_str(replied_msg)} has been banned by '
                f'{user_log_str(update)} for {reason}',
                f'{user_log_str(update)} has tried to ban his '
                f'peer/superior {split_cmd[1]}'
            )
        except (UserResolverError, ValueError) as e:
            update.message.reply_text(e)

    @log_action(logger)
    def unban(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        try:
            user_to_unban_id = self._usr_resolver\
                .acquire_target_user_from_cmd(update)

            if split_cmd_len >= 2:
                reason = split_cmd[2:]
            else:
                update.message.reply('Wrong number of parameters passed to'
                                     ' unban')
                return

            user_to_unban = User(self._db_man, user_to_unban_id)
            if user_to_unban.is_banned:
                # Forbid unbanning of higher ranks/peers to avoid
                # takeovers from rogues admins/mods
                execute_if_hierarchy_is_respected(
                    admin_user, user_to_unban,
                    lambda: user_to_unban.unban(reason),
                    update,
                    f'{split_cmd[1]} has been unbanned',
                    'You cannot unban your peers/superiors',
                    f'{split_cmd[1]} has been unbanned by '
                    f'{user_log_str(update)} for {reason}',
                    f'{user_log_str(update)} has tried to unban his '
                    f'peer/superior {split_cmd[1]}'
                )
            else:
                update.message.reply_text(
                    f'{split_cmd[1]} is not banned'
                )

        except (UserResolverError, ValueError) as e:
            update.message.reply_text(e)

    @log_action(logger)
    def kick(self, update, context):
        def kick_and_send_reason(user: User, reason: str):
            user.kick()
            self._updater.bot.send_message(
                user.user_id,
                f'You have been kicked for: {reason}'
            )

        admin_user = User(self._db_man, update.message.from_user.id)
        replied_msg = update.message.reply_to_message
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        try:
            user_to_kick_id = self._usr_resolver\
                .acquire_target_user_from_cmd(update)

            if replied_msg:
                reason = split_cmd[1:]
            else:
                if split_cmd_len >= 2:
                    reason = split_cmd[2:]
                else:
                    update.message.reply('Wrong number of parameters passed to'
                                         ' kick')
                    return
            user_to_kick = User(self._db_man, user_to_kick_id)
            execute_if_hierarchy_is_respected(
                admin_user, user_to_kick,
                lambda: kick_and_send_reason(user_to_kick, reason),
                update,
                f'{user_log_str(replied_msg)} has been kicked',
                'You cannot kick your peers/superiors',
                f'{user_log_str(replied_msg)} has been kicked by '
                f'{user_log_str(update)} for {reason}',
                f'{user_log_str(update)} has tried to kick his '
                f'peer/superior {split_cmd[1]}'
            )

        except (UserResolverError, ValueError) as e:
            update.message.reply_text(e)

    @log_action(logger)
    def set_default_permissions(self, update, context):
        sent_msg = update.message.reply_poll(
            question='Select the new default permissions',
            options=[x.replace('_', ' ') for x in self._config['Users']
                     ['DefaultPermissions'].split()],
            allows_multiple_answers=True,
            open_period=20
        )

        self._db_man.register_admin_poll(
            sent_msg.poll.poll_id,
            PollTypes.SET_DEFAULT_PERMISSIONS,
            update.message.from_user.id
        )

    @log_action(logger)
    def show_default_permissions(self, update, context):
        default_role = self._config['Roles']['DefaultRole']

        update.message.reply_markdown(
            '*The default permissions are*:\n{}'.format(
                str(get_permissions_from_config_section(
                    self._config['Roles'][default_role]['Permissions']
                ))
            )
        )

    @log_action(logger)
    def show_all_permissions(self, update, context):
        update.message.reply_markdown(
            '*List of permissions:\n*{}'.format(
                str(Permissions.ALL)
            )
        )

    @log_action(logger)
    def set_user_permissions(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        try:
            user_to_set_perms_id = self._usr_resolver\
                .acquire_target_user_from_cmd(update)
            user_to_set_perms = User(self._db_man,
                                         user_to_set_perms_id)
            user_info = self._usr_resolver\
                .get_user_info(user_to_waive_captcha_id)
            execute_if_hierarchy_is_respected(
                admin_user, user_to_set_perms,
                lambda: create_and_register_poll(
                    self._db_man,
                    update,
                    f'Select the new user permissions for '
                    'user_log_str(update)',
                    [x.replace('_', ' ').replace('Permissions', '').lower()
                     for x in Permissions]
                ),
                update,
                f'{user_log_str(user_info)}\'s permissions has been changed '
                'to {}',
                'You cannot change the permissions of your peers/superiors',
                f'{user_log_str(user_info)}\' permissions has been changed by '
                f'{user_log_str(update)} to',
                f'{user_log_str(update)} has tried to waive the captcha '
                'of his'
                f' peer/superior {user_log_str(user_info)}'
            )

        except (UserResolverError, ValueError) as e:
            update.message.reply_text(e)

    @log_action(logger)
    def waive_captcha(self, update, context):
        def update_passed_status(user: User, new_status: bool):
            user.captcha_status.passed = new_status

        admin_user = User(self._db_man, update.message.from_user.id)

        try:
            user_to_waive_captcha_id = self._usr_resolver\
                .acquire_target_user_from_cmd(update)
            user_to_waive_captcha = User(self._db_man,
                                         user_to_waive_captcha_id)
            user_info = self._usr_resolver\
                .get_user_info(user_to_waive_captcha_id)
            execute_if_hierarchy_is_respected(
                admin_user, user_to_waive_captcha,
                lambda: update_passed_status(user_to_waive_captcha, True),
                update,
                f'{user_log_str(user_info)}\'s captcha has been waived',
                'You cannot waive the captcha of your peers/superiors',
                f'{user_log_str(user_info)}\' captcha has been waived by '
                f'{user_log_str(update)}',
                f'{user_log_str(update)} has tried to waive the captcha '
                'of his'
                f' peer/superior {user_log_str(user_info)}'
            )

        except (UserResolverError, ValueError) as e:
            update.message.reply_text(e)

    @log_action(logger)
    def reset_captcha(self, update, context):
        def update_passed_status(user: User, new_status: bool):
            user.captcha_status.passed = new_status

        admin_user = User(self._db_man, update.message.from_user.id)
        replied_msg = update.message.reply_to_message
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        try:
            user_to_reset_captcha_id = self._usr_resolver\
                .acquire_target_user_from_cmd(update)

            user_to_reset_captcha = User(self._db_man,
                                         user_to_reset_captcha_id)

            user_info = self._usr_resolver\
                .get_user_info(user_to_reset_captcha_id)
            execute_if_hierarchy_is_respected(
                admin_user, user_to_reset_captcha,
                lambda: update_passed_status(user_to_reset_captcha, False),
                update,
                f'{user_log_str(user_info)}\'s captcha has been reset',
                'You cannot reset the captcha of your peers/superiors',
                f'{user_log_str(user_info)}\' captcha has been reset by '
                f'{user_log_str(update)}',
                f'{user_log_str(update)} has tried to reset the captcha of his'
                f' peer/superior {split_cmd[1]}'
            )

        except (UserResolverError, ValueError) as e:
            update.message.reply_text(e)

    @log_action(logger)
    def create_role(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)
        user_to_reset_captcha_id = None

        if split_cmd_len == 3:
            pass
        else:
            update.message.reply('Wrong number of parameters passed to '
                                 'create role captcha')
            return

        raise NotImplementedError

    @log_action(logger)
    def show_roles(self, update, context):
        update.message.reply_text(
            "\n\n".join(
                map(lambda x: str(x), self._db_man.show_roles())
            )
        )

    @log_action(logger)
    def set_default_role(self, update, context):
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        if split_cmd_len == 2:
            if self._db_man.does_role_exist(split_cmd[1]):
                admin_user = User(self._db_man, update.message.from_user.id)
                new_role = Role(self._db_man, split_cmd[1])
                if admin_user.role.power > new_role.power:
                    if new_role.permissions in admin_user.permissions:
                        self._config['Roles']['DefaultRole'] = split_cmd[1]
                    else:
                        update.message.reply_text(
                            'You can\'t set a role whose permissions are '
                            'more than yours'
                        )
                        logger.warning(
                            f'{user_log_str(update)} has tried to set a role '
                            'whose permissions are higher than his'
                        )
                else:
                    update.message.reply_text(
                        'You can\'t set a role whose power is higher '
                        'than yours as default'
                    )
                    logger.warning(
                        f'{user_log_str(update)} has tried to set a role '
                        'whose power is higher than his as default role'
                    )
            else:
                update.message.reply(f'Role {split_cmd[1]} does not exist. '
                                     'create it with /create_role')
        else:
            update.message.reply('Wrong number of parameters passed to '
                                 'create role captcha')

    @log_action(logger)
    def set_role_permissions(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)

        if split_cmd_len == 2:
            raise NotImplementedError

        else:
            update.message.reply('Wrong number of parameters passed to '
                                 'create role captcha')
            return


        raise NotImplementedError

    @log_action(logger)
    def set_role_power(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)
        user_to_reset_captcha_id = None

        if split_cmd_len == 2:
            raise NotImplementedError
            pass
        else:
            update.message.reply('Wrong number of parameters passed to '
                                 'create role captcha')
            return


        raise NotImplementedError

    @log_action(logger)
    def delete_role(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)
        user_to_reset_captcha_id = None

        if split_cmd_len == 3:
            raise NotImplementedError

        else:
            update.message.reply('Wrong number of parameters passed to '
                                 'create role captcha')
            return


        raise NotImplementedError

    @log_action(logger)
    def set_user_role(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)
        user_to_reset_captcha_id = None

        if split_cmd_len == 3:
            raise NotImplementedError
            pass
        else:
            update.message.reply('Wrong number of parameters passed to '
                                 'create role captcha')
            return


        raise NotImplementedError

    @log_action(logger)
    def get_logs(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)
        user_to_reset_captcha_id = None

        if split_cmd_len < 4:
            raise NotImplementedError

        else:
            update.message.reply('Wrong number of parameters passed to '
                                 'create role captcha')
            return


        raise NotImplementedError

    @log_action(logger)
    def view_user_info(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)
        user_to_reset_captcha_id = None

        if split_cmd_len < 3:
            raise NotImplementedError
            pass
        else:
            update.message.reply('Wrong number of parameters passed to '
                                 'create role captcha')
            return

        raise NotImplementedError

    @log_action(logger)
    def set_banner(self, update, context):
        admin_user = User(self._db_man, update.message.from_user.id)
        split_cmd = update.message.text.split()
        split_cmd_len = len(split_cmd)



        raise NotImplementedError
