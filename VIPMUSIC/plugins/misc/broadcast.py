import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait

# Changed from ShrutiMusic to VIPMUSIC
from VIPMUSIC import app
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from VIPMUSIC.utils.decorators.language import language
from VIPMUSIC.utils.formatters import alpha_to_int
from config import adminlist

# ==========================================
# BROADCAST ALLOWED IDS (NORMAL)
# ==========================================

BROADCAST_ID = [
    1281282633,
    8399160924,
    6773435708,
]

IS_BROADCASTING = False


# ==========================================
# BROADCAST HANDLER
# ==========================================

@app.on_message(filters.command("broadcast","gcast") & (filters.user(BROADCAST_ID) | SUDOERS))
@language
async def braodcast_message(client, message, _):
    global IS_BROADCASTING

    if IS_BROADCASTING:
        return await message.reply_text("⚠️ A broadcast is already running.")

    # ---------- PREPARE CONTENT ----------
    if message.reply_to_message:
        reply = message.reply_to_message
        x = reply.id
        y = message.chat.id
        reply_markup = reply.reply_markup if reply.reply_markup else None

        if reply.photo:
            content_type = "photo"
            file_id = reply.photo.file_id
            caption = reply.caption
        else:
            content_type = "text"
            text_content = reply.text

    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1].strip()
        if not query:
            return await message.reply_text(_["broad_8"])

    IS_BROADCASTING = True
    progress = await message.reply_text("🚀 **Broadcast started...**")

    # =====================================
    # CHAT BROADCAST
    # =====================================

    if "-wfchat" in message.text:
        chats = [int(chat["chat_id"]) for chat in await get_served_chats()]
        total = len(chats)
        sent = 0

        for i in chats:
            try:
                if message.reply_to_message:
                    if "-forward" in message.text:
                        await app.forward_messages(i, y, x)
                    else:
                        await app.copy_message(i, y, x, reply_markup=reply_markup)
                else:
                    await app.send_message(i, text=query)

                sent += 1

                if sent % 25 == 0:
                    await progress.edit_text(
                        f"📢 **Chat Broadcast Progress**\n\n"
                        f"✅ Sent: `{sent}` / `{total}`"
                    )

                await asyncio.sleep(0.2)

            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except:
                continue

        await progress.edit_text(
            f"✅ **Chat Broadcast Completed**\n\n"
            f"📊 Total: `{total}`\n"
            f"📨 Sent: `{sent}`"
        )

    # =====================================
    # USER BROADCAST
    # =====================================

    if "-wfuser" in message.text:
        users = [int(user["user_id"]) for user in await get_served_users()]
        total = len(users)
        sent = 0

        for i in users:
            try:
                if message.reply_to_message:
                    if "-forward" in message.text:
                        await app.forward_messages(i, y, x)
                    else:
                        await app.copy_message(i, y, x, reply_markup=reply_markup)
                else:
                    await app.send_message(i, text=query)

                sent += 1

                if sent % 25 == 0:
                    await progress.edit_text(
                        f"👤 **User Broadcast Progress**\n\n"
                        f"✅ Sent: `{sent}` / `{total}`"
                    )

                await asyncio.sleep(0.2)

            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except:
                continue

        await progress.edit_text(
            f"✅ **User Broadcast Completed**\n\n"
            f"📊 Total: `{total}`\n"
            f"📨 Sent: `{sent}`"
        )

    # =====================================
    # ASSISTANT BROADCAST
    # =====================================

    if "-assistant" in message.text:
        # Changed import here as well
        from VIPMUSIC.core.userbot import assistants

        text = "🤖 **Assistant Broadcast Report**\n\n"

        for num in assistants:
            client = await get_client(num)
            sent = 0

            async for dialog in client.get_dialogs():
                try:
                    if message.reply_to_message:
                        await client.forward_messages(dialog.chat.id, y, x)
                    else:
                        await client.send_message(dialog.chat.id, text=query)

                    sent += 1
                    await asyncio.sleep(3)

                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except:
                    continue

            text += f"• Assistant `{num}` → `{sent}` chats\n"

        await progress.edit_text(text)

    IS_BROADCASTING = False


# ==========================================
# AUTO CLEAN (UNCHANGED)
# ==========================================

async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if user.privileges.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue


asyncio.create_task(auto_clean())
