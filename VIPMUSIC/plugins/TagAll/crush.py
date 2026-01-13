
from VIPMUSIC.utils.decorators.language import language
from pyrogram import Client, filters
import requests
import random
import os
import re
import asyncio
import time
import config
from VIPMUSIC import app
from time import time
import asyncio
from VIPMUSIC.utils.extraction import extract_user

print("[crush] crush")

# Define a dictionary to track the last message timestamp for each user
user_last_message_time = {}
user_command_count = {}
# Define the threshold for command spamming (e.g., 20 commands within 60 seconds)
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5

from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

SHAYRI = [ "**𝑵𝒆𝒆 𝑷𝒂𝒓𝒌𝒖𝒎 𝑷𝒐𝒅𝒉𝒖 😍💫 𝑵𝒂𝒏 𝑲𝒂𝒍𝒂𝒊 𝑴𝒂𝒓𝒂𝒏𝒕𝒉𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑺𝒊𝒓𝒊𝒄𝒉𝒂 😘💞 𝑵𝒂𝒏 𝑯𝒆𝒂𝒓𝒕 𝑴𝒆𝒍𝒕 𝑷𝒂𝒏𝒏𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑯𝒖𝒈 𝑷𝒂𝒏𝒏𝒂 🤗💞 𝑵𝒂𝒏 𝑯𝒆𝒂𝒗𝒆𝒏 𝑻𝒉𝒐𝒏𝒅𝒖𝒗𝒆𝒏 💫☁️**",
"**𝑵𝒆𝒆 𝑲𝒂𝒏𝒏𝒂 𝑷𝒂𝒂𝒓𝒌𝒖𝒎 😍💞 𝑵𝒂𝒏 𝑼𝒍𝒂𝒈𝒂 𝑴𝒂𝒓𝒂𝒏𝒕𝒉𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑷𝒆𝒔𝒖𝒎 𝑷𝒐𝒅𝒉𝒖 😍💫 𝑵𝒂𝒏 𝑲𝒂𝒍𝒂𝒊 𝑴𝒂𝒓𝒂𝒏𝒕𝒉𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑺𝒂𝒎𝒊𝒑𝒂𝒎 𝑽𝒂𝒓𝒖𝒎 𝑷𝒐𝒅𝒉𝒖 😍💫 𝑵𝒂𝒏 𝑯𝒆𝒂𝒓𝒕 𝑹𝒆𝒔𝒕𝒂𝒓𝒕 𝑨𝒈𝒖𝒎 💞✨**",
"**𝑵𝒆𝒆 𝑵𝒂𝒏 𝑵𝒖𝒑𝒂𝒕𝒉𝒊 𝑷𝒆𝒔𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💫 𝑼𝒍𝒂𝒈𝒂𝒗𝒆 𝑵𝒊𝒓𝒖𝒕𝒉𝒉𝒂𝒎 💞✨**",
"**𝑵𝒆𝒆 𝑲𝒂𝒏𝒏𝒂 𝑲𝒐𝒏𝒅𝒖 𝑷𝒂𝒓𝒌𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑵𝒊𝒓𝒂𝒊𝒗𝒂𝒂𝒈𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑷𝒆𝒓𝒂𝒊 𝑨𝒛𝒂𝒊𝒌𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑶𝒗𝒊𝒊𝒚𝒂𝒗𝒆 𝑴𝒂𝒓𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑷𝒂𝒕𝒉𝒊𝒚𝒂 𝑷𝒆𝒔𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💫 𝑵𝒂𝒏 𝑵𝒊𝒏𝒂𝒊𝒗𝒖𝒈𝒂𝒍𝒊𝒍𝒆 𝑻𝒉𝒐𝒏𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑬𝒏𝒏𝒂𝒊 𝑷𝒂𝒕𝒉𝒊 𝑨𝒏𝒃𝒂𝒈𝒂 𝑷𝒆𝒔𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑼𝒍𝒂𝒈𝒂𝒗𝒆 𝑲𝒂𝒏𝒅𝒖 𝑴𝒖𝒅𝒊𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑺𝒊𝒓𝒊𝒄𝒉𝒂 😘💞 𝑬𝒏 𝑰𝒅𝒂𝒚𝒂𝒎 𝑽𝒊𝒏𝒎𝒆𝒍𝒏𝒂𝒅𝒊 𝑷𝒂𝒚𝒂𝒏𝒂𝒎 💞✨**",
"**𝑵𝒆𝒆 𝑺𝒂𝒎𝒊𝒑𝒂𝒎 𝑵𝒊𝒍𝒂𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑲𝒂𝒍𝒂𝒊𝒗𝒂𝒏𝒂𝒎𝒂𝒈 𝑴𝒂𝒓𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑷𝒆𝒔𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑷𝒂𝒅𝒂𝒍𝒂𝒈 𝑴𝒂𝒓𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑷𝒂𝒓𝒌𝒖𝒎 𝑷𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑵𝒊𝒏𝒂𝒊𝒗𝒂𝒈𝒊 𝑴𝒂𝒓𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑺𝒊𝒓𝒊𝒄𝒉𝒂 😍💞 𝑵𝒂𝒏 𝑲𝒂𝒍𝒂𝒊 𝑨𝒏𝒃𝒂𝒈𝒂 𝑵𝒊𝒓𝒂𝒊𝒗𝒂𝒈𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑷𝒂𝒓𝒌𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑽𝒂𝒏𝒂𝒎𝒆 𝑻𝒉𝒐𝒏𝒅𝒖𝒗𝒆𝒏 💞✨**"
"**𝑵𝒆𝒆 𝑬𝒏 𝑲𝒂𝒏𝒗𝒊𝒍 𝑽𝒂𝒏𝒕𝒉𝒂𝒍 😍💞 𝑵𝒂𝒏 𝑵𝒊𝒅𝒓𝒂𝒊 𝑴𝒂𝒓𝒂𝒏𝒕𝒉𝒊𝒅𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑲𝒂𝒊𝒚𝒂 𝑷𝒊𝒅𝒊𝒌𝒌𝒖𝒎𝒃𝒐𝒅𝒉𝒖 🤝💞 𝑬𝒏 𝑼𝒍𝒂𝒈𝒂𝒎 𝑵𝒊𝒏𝒓𝒖𝒗𝒊𝒅𝒖𝒎 💫✨**",
"**𝑵𝒆𝒆 𝑷𝒆𝒓𝒖𝒎 𝑺𝒊𝒓𝒊𝒄𝒉𝒂 😘💞 𝑵𝒂𝒏 𝑲𝒂𝒍𝒂𝒊 𝑽𝒆𝒍𝒊𝒚𝒆 𝑷𝒂𝒅𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑴𝒐𝒐𝒅𝒊𝒚𝒂𝒎 𝑷𝒆𝒔𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑨𝒏𝒃𝒊𝒍 𝑰𝒏𝒊𝒎𝒂𝒊 𝑲𝒂𝒏𝒅𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑰𝒅𝒂𝒚𝒂𝒕𝒉𝒊𝒍 𝑺𝒆𝒓𝒏𝒅𝒉𝒂𝒍 💖✨ 𝑵𝒂𝒏 𝑬𝒏𝒏𝒂𝒗𝒆 𝑴𝒂𝒓𝒂𝒏𝒕𝒉𝒊𝒅𝒖𝒗𝒆𝒏 💫💞**",
"**𝑵𝒆𝒆 𝑽𝒂𝒍𝒊𝒚𝒊𝒍 𝑰𝒓𝒖𝒏𝒅𝒉𝒂 😢💞 𝑵𝒂𝒏 𝑨𝒏𝒃𝒊𝒍 𝑴𝒂𝒓𝒖𝒎𝒂𝒊 𝑻𝒉𝒂𝒓𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑷𝒆𝒓𝒂𝒊 𝑨𝒛𝒂𝒊𝒌𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑨𝒗𝒂𝒏𝒊 𝑴𝒆𝒍 𝑷𝒂𝒅𝒂𝒎𝒊𝒅𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑷𝒂𝒕𝒉𝒊 𝑷𝒆𝒔𝒖𝒎𝒃𝒐𝒅𝒉𝒖 💞💫 𝑵𝒂𝒏 𝑲𝒂𝒍𝒂𝒊 𝑲𝒂𝒅𝒂𝒊 𝑨𝒈𝒊𝒅𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑵𝒊𝒏𝒂𝒊𝒌𝒌𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑰𝒅𝒂𝒚𝒂𝒕𝒉𝒊𝒍 𝑷𝒐𝒐 𝑴𝒂𝒍𝒂𝒓𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑷𝒂𝒌𝒌𝒂𝒕𝒉𝒊𝒍 𝑵𝒊𝒍𝒂𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑰𝒏𝒃𝒂𝒎𝒂𝒈 𝑴𝒂𝒓𝒊𝒅𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑷𝒂𝒕𝒉𝒊 𝑺𝒊𝒓𝒊𝒄𝒉𝒂 😘💞 𝑵𝒂𝒏 𝑽𝒆𝒍𝒊𝒚𝒆 𝑽𝒂𝒏𝒂𝒎𝒂𝒈 𝑵𝒊𝒏𝒓𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑷𝒆𝒓𝒂𝒊 𝑵𝒆𝒏𝒂𝒊𝒌𝒌𝒖𝒎𝒃𝒐𝒅𝒉𝒖 💞💫 𝑵𝒂𝒏 𝑼𝒏 𝑵𝒆𝒏𝒋𝒊𝒍 𝑽𝒆𝒆𝒅𝒖 𝑲𝒂𝒕𝒕𝒖𝒗𝒆𝒏 💞✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑲𝒂𝒏𝒏𝒂 𝑵𝒐𝒌𝒌𝒖𝒎𝒃𝒐𝒅𝒉𝒖 😍💞 𝑵𝒂𝒏 𝑰𝒏𝒃𝒂 𝑺𝒂𝒈𝒂𝒓𝒂𝒎 𝑨𝒈𝒊𝒅𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑼𝒓𝒂𝒕𝒉𝒊 𝑷𝒆𝒔𝒖𝒎𝒃𝒐𝒅𝒉𝒖 💞💫 𝑵𝒂𝒏 𝑴𝒆𝒈𝒂𝒎𝒂𝒈 𝑻𝒉𝒐𝒏𝒅𝒖𝒗𝒆𝒏 💫✨**",
"**𝑵𝒆𝒆 𝑬𝒏 𝑷𝒆𝒓𝒂𝒊 𝑪𝒉𝒐𝒍𝒍𝒖𝒎𝒃𝒐𝒅𝒉𝒖 💖💫 𝑵𝒂𝒏 𝑷𝒂𝒗𝒂𝒊 𝑻𝒉𝒐𝒏𝒅𝒖𝒗𝒆𝒏 💞✨**"
         ]

# Command
SHAYRI_COMMAND = ["crush"]

@app.on_message(
    filters.command(SHAYRI_COMMAND) & filters.group)
@language
async def shayri_group(client: Client, message: Message, _):
    await message.reply_text(
        f"<blockquote>{random.choice(SHAYRI)}</blockquote>",
        #parse_mode="markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text=_["CHT"], url=config.SUPPORT_CHAT),
                    InlineKeyboardButton(text=_["NET"], url=config.SUPPORT_CHANNEL),
                ]
            ]
        ),
    )


@app.on_message(
    filters.command(SHAYRI_COMMAND) & filters.private)
@language
async def shayri_private(client: Client, message: Message, _):
    await message.reply_text(
        f"<blockquote>{random.choice(SHAYRI)}</blockquote>",
        #parse_mode="markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text=_["CHT"], url=config.SUPPORT_CHAT),
                    InlineKeyboardButton(text=_["NET"], url=config.SUPPORT_CHANNEL),
                ]
            ]
        ),
    )
