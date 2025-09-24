from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os

API_ID = ("24595217"))
API_HASH = ("8b37bc475b594f5f30e6b2c01699366e")
BOT_TOKEN = ("8249949820:AAFzjIiJJx5cARdEQV4jz6nmb2KpiSmSrVw")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    client.start(bot_token=BOT_TOKEN)
    print(client.session.save())  # copy this
