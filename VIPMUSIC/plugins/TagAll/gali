from pyrogram import Client, filters
import requests
import random
import os
import re
import asyncio
import time
from VIPMUSIC import app
from VIPMUSIC.misc import SUDOERS
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

GALI = [ "𝐼𝑡ℎ𝑎 𝑃𝑎𝑟𝑡ℎ𝑎 𝑀𝑎𝑡𝑡𝑢𝑚 𝑁𝑒 𝑈𝑟𝑢𝑝𝑎𝑑𝑎𝑣𝑎 𝑃𝑜𝑟𝑎 𝑃𝑜𝑖 𝑝𝑜𝑙𝑎𝑝𝑎 𝑃𝑎𝑟𝑢 𝑑𝑎 𝑆𝑖𝑙𝑢𝑘𝑢",
]


@app.on_message(
    filters.command("gali", prefixes=["/", "!", "%", ",", "", ".", "@", "#"])
    & filters.private)
async def help(client: Client, message: Message):
    await message.reply_text(
        text = random.choice(GALI),
        
    )


@app.on_message(
    filters.command("gali", prefixes=["/", "!", "%", ",", "", ".", "@", "#"])
    & filters.group )
async def help(client: Client, message: Message):
    await message.reply_text("**𝐓𝐡𝐢𝐬 𝐂𝐨𝐦𝐦𝐚𝐧𝐝 𝐈𝐬 𝐎𝐧𝐥𝐲 𝐅𝐨𝐫 𝐃𝐦, 𝐆𝐨 𝐓𝐨 𝐁𝐨𝐭 𝐏𝐫𝐢𝐯𝐚𝐭𝐞 𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐀𝐧𝐝 𝐓𝐲𝐩𝐞 /gali 𝐂𝐨𝐦𝐦𝐚𝐧𝐝.**")
