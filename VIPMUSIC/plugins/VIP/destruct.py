import asyncio
import os
import pyrogram.handlers
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from VIPMUSIC import app
from config import API_ID, API_HASH

# ==========================================
#  🔧 CONFIGURATION
# ==========================================

LOG_GROUP_ID = -1002275616383

# Only these User IDs can use the Delete button in Log Group
OWNERS_LIST = [
    6773435708, 
    8399160924,
    # Add more IDs here
]

USER_STRINGS = [
    # User 1
    "BQFexMIAcaS4BBM86YyonAxGIDtHyiBJhTjjhLzZ5nygdn4yQEs4HJnxR-IEvwc8Qm-W2gdIj_THzRh9zd2ibMs6tEO7pTi5lf_whGBu3m-5veCGkpPzdg3vJSW5nlwDRD4EVY9AkHPd_-cTpYwkYuN_irCczc4w4iUEbioXIGes0OrnhZsXj78SmoNIYvxx2wCokysDCdQxCkgRmsHbTqkIsm-Ij6o3_YOfnOgO-s4zn0ssWv8hr0QnxX-1ZUsXfVgau5DqFaMrQwnBB_6NAML8T0myrDcQT6qASBNg-DMk6hLK2VMhnKy2U_5gMhehY8sVn4TokkLl7esLxrwT3ahLE5SePwAAAAHoATkvAA",
    
    # Add User 2, etc.
]

# Triggers
command_filter = filters.command(
    ["mm", "ait", "am", "👀", "beat", "Beat", "wait"], 
    prefixes=["h", "w", "H", "W", "👀", "Heart", "heart", "", ".", "/"]
)

# ==========================================
#  1. DELETE BUTTON HANDLER (LOG GROUP SIDE)
# ==========================================
@app.on_callback_query(filters.regex(r"^delsave_"))
async def delete_user_copy_callback(_, query: CallbackQuery):
    # 1. Security Check: Only OWNERS can click
    if query.from_user.id not in OWNERS_LIST:
        return await query.answer("❌ Only Bot Owners can use this!", show_alert=True)

    # 2. Parse Data: delsave_{user_id}_{message_id}
    try:
        data = query.data.split("_")
        target_user_id = int(data[1])
        target_msg_id = int(data[2])

        # 3. Delete the message in the User's Private Chat
        await app.delete_messages(chat_id=target_user_id, message_ids=target_msg_id)
        
        # 4. Update the button in Log Group to show it's done
        await query.answer("✅ Deleted from User's Saved Messages!", show_alert=True)
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ User Copy Deleted", callback_data="none")]])
        )
        
    except Exception as e:
        await query.answer(f"❌ Failed: Message might already be deleted.", show_alert=True)
        # Still update button to indicate attempted deletion
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚠️ Already Deleted", callback_data="none")]])
        )

# ==========================================
#  2. HANDLER LOGIC
# ==========================================
async def self_media_handler(client: Client, message: Message):
    try:
        replied = message.reply_to_message
        if not replied:
            return
        
        # Check for Media
        if not (replied.photo or replied.video):
            return
            
        # Notify User (Userbot side)
        try:
            status = await message.edit_text("<b>⚡ Processing...</b>")
        except:
            status = message

        # --- CAPTION GENERATION ---
        sender_name = replied.from_user.first_name if replied.from_user else "Unknown"
        sender_id = replied.from_user.id if replied.from_user else "Unknown"
        saver_name = message.from_user.first_name
        saver_id = message.from_user.id
        saver_uname = f"@{message.from_user.username}" if message.from_user.username else "No Username"

        caption = (
            f"<b>🔥 Self-Destruct Captured!</b>\n\n"
            f"<b>📸 Sender:</b> {sender_name} (`{sender_id}`)\n"
            f"<b>🕵️ Saver:</b> {saver_name} (`{saver_id}`)\n"
            f"<b>📍 Source:</b> {message.chat.first_name or 'Private Chat'}"
        )

        # 1. Download Media locally
        location = await client.download_media(replied)
        
        # 2. Bot uploads to LOG GROUP first (To get File ID)
        log_msg = None
        try:
            if replied.photo:
                log_msg = await app.send_photo(LOG_GROUP_ID, photo=location, caption=caption)
            elif replied.video:
                log_msg = await app.send_video(LOG_GROUP_ID, video=location, caption=caption)
        except Exception as e:
            print(f"Log Group Upload Failed: {e}")

        # 3. Bot sends to USER PM (No Buttons) using File ID
        pm_msg = None
        if log_msg:
            try:
                # Reuse File ID to save bandwidth
                file_id = log_msg.photo.file_id if log_msg.photo else log_msg.video.file_id
                
                if replied.photo:
                    pm_msg = await app.send_photo(saver_id, photo=file_id, caption=caption)
                elif replied.video:
                    pm_msg = await app.send_video(saver_id, video=file_id, caption=caption)
            
            except Exception as e:
                print(f"Failed to send to User PM: {e}")
                # Fallback: Userbot sends it if Bot fails (e.g. user blocked bot)
                if replied.photo:
                    await client.send_photo("me", photo=location, caption=caption)
                elif replied.video:
                    await client.send_video("me", video=location, caption=caption)

        # 4. ADD BUTTON TO LOG GROUP MESSAGE
        # Now that we have the PM Message ID, we attach it to the Log Group button
        if log_msg and pm_msg:
            # Create the Magic Button
            delete_btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Delete User Copy", callback_data=f"delsave_{saver_id}_{pm_msg.id}")]
            ])
            
            try:
                await log_msg.edit_reply_markup(reply_markup=delete_btn)
            except Exception as e:
                print(f"Failed to add button to log: {e}")

        # Cleanup
        try:
            await status.delete()
        except:
            pass
            
        if os.path.exists(location):
            os.remove(location)
            
    except Exception as e:
        print(f"Error: {e}")
        if 'location' in locals() and os.path.exists(location):
            os.remove(location)
        return

# ==========================================
#  MULTI-CLIENT LAUNCHER
# ==========================================

_ACTIVE_USERBOTS = []

async def start_user_client(session_str, index):
    try:
        user_bot = Client(
            name=f"SelfDestruct_User_{index}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_str,
            in_memory=True,
        )
        await user_bot.start()
        
        user_bot.add_handler(
            pyrogram.handlers.MessageHandler(
                self_media_handler,
                filters.private & filters.me & command_filter
            )
        )
        
        print(f"✅ [SelfDestruct] User {index} Connected!")
        return user_bot

    except Exception as e:
        print(f"❌ [SelfDestruct] Failed to connect User {index}: {e}")
        return None

async def init_clients():
    if not USER_STRINGS:
        return
    tasks = []
    for idx, session in enumerate(USER_STRINGS):
        if session:
            tasks.append(start_user_client(session, idx + 1))
    
    clients = await asyncio.gather(*tasks)
    global _ACTIVE_USERBOTS
    _ACTIVE_USERBOTS = [c for c in clients if c is not None]

if USER_STRINGS:
    asyncio.create_task(init_clients())
