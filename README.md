#NASBOT

This bot is built to download with aria2 links sent to bot's Telegram chat. It tells apart TV-Sows, movies and other downloads.
It accepts links or .torrent files as input. Also you can choose the download directory by sending "/special" with download link and derictory of choice.

###Following modules are bot's dependencies:
thread
bencode
requests
websocket

###Run
To start using this bot you have to create *token.cfg* file. Content of file as follows *'["MASTER"], "TOKEN"'*. List of MARTERs is the list of users allowed to use the bot, TOKEN is the Telegram bot token.
Run Nasbot and Aria2 in the same working dir or add dir path to save metadata explicitly by editing the code.

###Bot will create following files:
id_file -- persistent dict
nasbot_ws.log -- json rpc messages log limited to 300 lines; requests are limited to 200 chars.
nasbot_nonusers.log -- logs messages from non-MASTERs

For testing purpose tmux or screen is ok, for 24/7 use suggest using supervisord or other tools.
