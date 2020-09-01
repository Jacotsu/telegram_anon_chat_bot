# Quickstart

```
git clone https://github.com/Jacotsu/telegram_anon_chat_bot.git
cd telegram_anon_chat_bot
pip install -e --user .
sudo mkdir -p /var/lib/anon_chat_bot/ /var/log/anon_chat_bot/
sudo chown $USER:$USER /var/lib/anon_chat_bot/ /var/log/anon_chat_bot/
./scripts/init_username_resolver.py
```
do `cp templates/config.ini config.ini` and configure the bot by editing the file.
run the bot with `./src/main.py`

# Features

- polls
- audios
- videos
- contact
- chats
