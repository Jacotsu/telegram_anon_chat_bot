- Ban
  - [ ] Implement unban query
  - [ ] Implement ban override protection
  - [ ] Implement unban with reason
  - [X] Implement timed ban

- Logging
  - [ ] Implement message log to allow content moderation

- Performance
  - [ ] Implement Database indexes
  - [ ] Implement garbage collection in antiflood filter and captcha filter

- Security
  - [ ] Implement Database and log encryption
  - [ ] Set default role and permissions on join

- Maintainability
  - [ ] Cleanup code
    - [ ] Implement `usr_log_str` as Users's `__str__`
    - [ ] Allow passing a telegram user object to User class as constructor

~~ - [ ] Store hashes of user_ids to make database anonymous by default~~ Not compatible with bot's features
