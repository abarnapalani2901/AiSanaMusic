#start.py
import time
from time import time
import asyncio
import random
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from youtubesearchpython.__future__ import VideosSearch
from pyrogram.errors import UserAlreadyParticipant, UserNotParticipant

import config
from config import BANNED_USERS, GREET, MENTION_USERNAMES, START_REACTIONS, YUMI_PICS
from VIPMUSIC import app
from VIPMUSIC.misc import _boot_
from VIPMUSIC.utils import bot_up_time
from VIPMUSIC.plugins.sudo.sudoers import sudoers_list
from VIPMUSIC.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from VIPMUSIC.utils.decorators.language import LanguageStart
from VIPMUSIC.utils.formatters import get_readable_time
from VIPMUSIC.utils.inline import first_page, private_panel, start_panel
from VIPMUSIC.utils.database import get_assistant
from VIPMUSIC.utils.extraction import extract_user
from strings import get_string

# ==========================================
#  PREMIUM MESSAGE EFFECTS (FULL SCREEN)
# ==========================================
FULL_SCREEN_EFFECTS = [
    "5046509860389126442",  # 🎉 Confetti
    "5044134455711629726",  # ❤️ Hearts
    "5104841245755180586",  # 🔥 Fire
    "5107584321108051014",  # 👍 Like
    "5104858069142078461",  # 🎊 Party
    "5104841245755180587",  # 💥 Explosion
    "5104841245755180588",  # ✨ Sparkles
    "5104841245755180589",  # 🌟 Stars
    "5104841245755180590",  # 😍 Love Eyes
    "5104841245755180591",  # 🥳 Party Face
    "5104841245755180592",  # 😎 Cool
    "5104841245755180593",  # 🤩 Star Struck
    "5107584321108051015",  # 👏 Clap
    "5107584321108051016",  # 🙌 Hands Up
    "5107584321108051018",  # 💙 Hearts
    "5107584321108051022",  # 💫 Dizzy
    "5107584321108051023",  # ⚡ Lightning
    "5107584321108051026",  # 🎈 Balloons
]

# Fallback effects that are guaranteed to work
SAFE_EFFECTS = [
    "5046509860389126442",
    "5044134455711629726",
    "5104841245755180586",
    "5107584321108051014",
]

# ==========================================
#  ANTI-SPAM
# ==========================================
user_last_message_time = {}
user_command_count = {}

SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5


# ==========================================
#  SEND FULL SCREEN EFFECT (BOT MESSAGE)
# ==========================================
async def send_fullscreen_effect(chat_id: int):
    try:
        # Try a random effect from the main list
        await app.send_message(
            chat_id=chat_id,
            text="✨",
            effect_id=random.choice(FULL_SCREEN_EFFECTS),
        )
    except Exception:
        # If the main list fails (invalid ID), use the Safe Fallback list
        try:
            await app.send_message(
                chat_id=chat_id,
                text="✨",
                effect_id=random.choice(SAFE_EFFECTS),
            )
        except Exception:
            pass


# ===================== /start PRIVATE =====================
@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):

    # ---------- FULL SCREEN ANIMATION ----------
    await send_fullscreen_effect(message.chat.id)

    try:
        caption = _["start_2"].format(str(message.from_user.mention))
    except Exception:
        caption = str(_["start_2"])

    user_id = message.from_user.id
    current_time = time()

    last_message_time = user_last_message_time.get(user_id, 0)
    if current_time - last_message_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            hu = await message.reply_text(
                f"**{message.from_user.mention} ᴘʟᴇᴀsᴇ ᴅᴏɴᴛ sᴘᴀᴍ, ᴛʀʏ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 5 sᴇᴄ**"
            )
            await asyncio.sleep(3)
            await hu.delete()
            return
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time

    await add_served_user(user_id)

    # --------- /start help ----------
    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]

        if name.startswith("help"):
            await send_fullscreen_effect(message.chat.id)
            keyboard = first_page(_)
            return await message.reply_photo(
                photo=config.START_IMG_URL,
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )

        if name.startswith("sud"):
            await sudoers_list(client=client, message=message, _=_)
            return

        if name.startswith("inf"):
            m = await message.reply_text("🔎")
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            results = VideosSearch(query, limit=1)

            for result in (await results.next())["result"]:
                title = result["title"]
                duration = result["duration"]
                views = result["viewCount"]["short"]
                thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                channellink = result["channel"]["link"]
                channel = result["channel"]["name"]
                link = result["link"]
                published = result["publishedTime"]

            searched_text = _["start_6"].format(
                title, duration, views, published, channellink, channel, app.mention
            )

            key = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="💕 𝐕𖽹𖽴𖽞𖽙 🦋",
                            callback_data=f"downloadvideo {query}",
                        ),
                        InlineKeyboardButton(
                            text="💕 𝐀𖽪𖽴𖽹𖽙 🦋",
                            callback_data=f"downloadaudio {query}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🎧 sᴇᴇ ᴏɴ ʏᴏᴜᴛᴜʙᴇ 🎧", url=link
                        ),
                    ],
                ]
            )

            await m.delete()
            await app.send_photo(
                chat_id=message.chat.id,
                photo=thumbnail,
                caption=searched_text,
                reply_markup=key,
            )
            return

    # ---------- NORMAL START FLOW ----------
    out = private_panel(_)

    loading_1 = await message.reply_text(random.choice(GREET))
    await asyncio.sleep(1.2)
    await loading_1.delete()

    vip = await message.reply_text("**ᴅιиg ᴅσиg ꨄ︎❣️.....**")
    for dots in [".❣️....", "..❣️...", "...❣️..", "....❣️.", ".....❣️"]:
        await asyncio.sleep(0.3)
        await vip.edit_text(f"**ᴅιиg ᴅσиg ꨄ︎{dots}**")
    await asyncio.sleep(0.5)
    await vip.delete()

    vips = await message.reply_text("**⚡ѕ**")
    steps = ["⚡ѕт", "⚡ѕтα", "⚡ѕтαя", "⚡ѕтαят", "⚡ѕтαятι", "⚡ѕтαятιи", "⚡ѕтαятιиg"]
    for step in steps:
        await vips.edit_text(f"**{step}**")
        await asyncio.sleep(0.12)

    await vips.delete()

    await message.reply_photo(
        photo=config.START_IMG_URL,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(out),
    )


# ===================== /start GROUP =====================
@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    BOT_UP = await bot_up_time()

    await message.reply_photo(
        photo=config.START_IMG_URL,
        caption=_["start_2"].format(app.mention, BOT_UP),
        reply_markup=InlineKeyboardMarkup(out),
    )

    await add_served_chat(message.chat.id)
