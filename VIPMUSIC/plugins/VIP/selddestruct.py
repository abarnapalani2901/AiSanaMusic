import os
import asyncio
from pyrogram import filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    InlineQueryResultArticle, InputTextMessageContent
)
from VIPMUSIC import app
from VIPMUSIC.core.userbot import assistants

# --- CONFIGURATION ---
# This matches the text sent when you click the inline button.
COMMAND_TRIGGER = "savedestruct" 

# --- 1. INLINE QUERY HANDLER (The Trigger) ---
# We use group=-1 to make sure this runs even if Whisper catches other queries.
@app.on_inline_query(filters.regex(r"^save"), group=-1)
async def inline_save_trigger(_, inline_query):
    
    # The button that appears when you type "@Bot save"
    results = [
        InlineQueryResultArticle(
            title="📥 Sᴀᴠᴇ Tʜɪs Mᴇᴅɪᴀ",
            description="Cʟɪᴄᴋ ᴛᴏ sᴀᴠᴇ ᴛʜᴇ sᴇʟғ-ᴅᴇsᴛʀᴜᴄᴛ/ᴛɪᴍᴇʀ ᴍᴇᴅɪᴀ ʏᴏᴜ ʀᴇᴘʟɪᴇᴅ ᴛᴏ.",
            thumb_url="https://graph.org/file/0b5a3406361a41552a92c.png",
            
            # This is the magic: It types the command for the Assistant to see
            input_message_content=InputTextMessageContent(f".{COMMAND_TRIGGER}"),
        )
    ]
    
    await inline_query.answer(results, cache_time=0)


# --- 2. ASSISTANT LOGIC (The Worker) ---
# This runs on your Userbot (Assistant) to actually download the restricted media.

if assistants:
    ub = assistants[0] # Use the first assistant

    @ub.on_message(filters.command(COMMAND_TRIGGER, prefixes=".") & filters.me & filters.reply)
    async def save_destruct_media(client, message: Message):
        replied = message.reply_to_message
        
        # Check if there is any media to save
        if not (replied.photo or replied.video or replied.video_note or replied.voice or replied.document or replied.audio):
            return await message.edit_text("❌ <b>Please reply to a media file.</b>")
        
        # Indicate processing
        status_msg = await message.edit_text("<b>⚡ Processing Self-Destruct Media...</b>")
        
        file_path = None
        try:
            # Download the media (Assistant can see timer media)
            file_path = await client.download_media(replied)
            
            # Upload to Saved Messages ("me")
            caption_text = f"<b>🔥 Saved Self-Destruct Media</b>\n<b>From:</b> {message.chat.title or 'Private Chat'}"
            
            if replied.photo:
                await client.send_photo("me", photo=file_path, caption=caption_text)
            elif replied.video:
                await client.send_video("me", video=file_path, caption=caption_text)
            elif replied.video_note:
                await client.send_video_note("me", video_note=file_path)
            elif replied.voice:
                await client.send_voice("me", voice=file_path)
            else:
                await client.send_document("me", document=file_path, caption=caption_text)
            
            # Cleanup: Delete the command message and the local file
            await status_msg.delete()
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            await status_msg.edit_text(f"❌ <b>Error:</b> `{e}`")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
