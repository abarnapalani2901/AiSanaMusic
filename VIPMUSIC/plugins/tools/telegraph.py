# VIPMUSIC/plugins/tools/telegraph.py

import os
import asyncio
import requests
from datetime import datetime
from PIL import Image
from telegraph import Telegraph, upload_file, exceptions

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from VIPMUSIC import app
from config import BANNED_USERS

# ---------------- CONFIGURATION ---------------- #
VIP = "VIPMUSIC"
telegraph = Telegraph(domain="graph.org")
r = telegraph.create_account(short_name=VIP)
auth_url = r["auth_url"]

# Imgur Client ID (Generic Public ID)
IMGUR_CLIENT_ID = "5d42a2e5b19fe1d" 

# ---------------- HELPER ---------------- #
def resize_image(image_path):
    """Converts WebP/Stickers to PNG for Telegraph/Imgur support."""
    try:
        im = Image.open(image_path)
        im.save(image_path, "PNG")
    except Exception as e:
        print(f"Resize Error: {e}")

# ---------------- TELEGRAPH COMMANDS ---------------- #
@app.on_message(filters.command(["tgm", "tgt", "telegraph", "tl"], prefixes=["/", "!", ".", ",",]) & ~BANNED_USERS)
async def telegraph_upload(client, message):
    if not message.reply_to_message:
        return await message.reply_text("⚠️ **Reply to a message or media!**")

    cmd = message.command[0].lower()
    
    # --- MEDIA UPLOAD (/tgm) ---
    if cmd in ["tgm", "telegraph", "tl"]:
        if not message.reply_to_message.media:
            return await message.reply_text("❌ **Please reply to an image or video/gif.**")

        msg = await message.reply_text("<code>📥 Downloading...</code>")
        start = datetime.now()
        local_path = None

        try:
            local_path = await message.reply_to_message.download()
            
            if local_path.endswith((".webp", ".tgs")):
                resize_image(local_path)

            await msg.edit_text("<code>📤 Uploading to Telegraph...</code>")
            
            upload_path = upload_file(local_path)
            url = f"https://graph.org{upload_path[0]}"
            
            end = datetime.now()
            ms = (end - start).seconds

            await msg.edit_text(
                f"✅ **Uploaded to Telegraph!**\n\n"
                f"🔗 **Link:** [Click Here]({url})\n"
                f"⏱ **Time:** `{ms}s`",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔗 Open Link", url=url)]]
                )
            )

        except exceptions.TelegraphException as exc:
            await msg.edit_text(f"❌ **Telegraph Error:** `{exc}`")
        except Exception as e:
            await msg.edit_text(f"❌ **Error:** `{e}`")
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)

    # --- TEXT UPLOAD (/tgt) ---
    elif cmd == "tgt":
        msg = await message.reply_text("<code>📝 Creating page...</code>")
        
        page_content = message.reply_to_message.text or message.reply_to_message.caption
        if not page_content:
            return await msg.edit_text("❌ **Please reply to a text message.**")

        title = "VIPMUSIC Paste"
        if len(message.command) > 1:
            title = message.text.split(None, 1)[1]
        elif message.from_user:
            title = f"{message.from_user.first_name}'s Paste"

        try:
            page_content = page_content.replace("\n", "<br>")
            response = telegraph.create_page(title=title, html_content=page_content)
            url = f"https://graph.org/{response['path']}"

            await msg.edit_text(
                f"✅ **Page Created!**\n\n"
                f"📄 **Title:** `{title}`\n"
                f"🔗 **Link:** [Click Here]({url})",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔗 Open Page", url=url)]]
                )
            )
            
        except Exception as e:
            await msg.edit_text(f"❌ **Error:** `{e}`")


# ---------------- IMGUR COMMAND ---------------- #
@app.on_message(filters.command(["imgur", "ig"], prefixes=["/", "!", ".", ",",]) & ~BANNED_USERS)
async def imgur_upload(client, message):
    if not message.reply_to_message:
        return await message.reply_text("⚠️ **Reply to an image/video to upload to Imgur!**")
    
    if not message.reply_to_message.media:
        return await message.reply_text("❌ **Please reply to media.**")

    msg = await message.reply_text("<code>📥 Downloading...</code>")
    start = datetime.now()
    local_path = None

    try:
        local_path = await message.reply_to_message.download()
        
        if local_path.endswith((".webp", ".tgs")):
            resize_image(local_path)

        await msg.edit_text("<code>📤 Uploading to Imgur...</code>")

        # Imgur API Call
        headers = {'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'}
        data = {'type': 'file', 'title': 'Uploaded by VIPMUSIC', 'description': 'Uploaded via Pyrogram Bot'}
        
        # We run the blocking request in a separate thread to avoid lag
        def upload_request():
            with open(local_path, 'rb') as img_file:
                return requests.post(
                    "https://api.imgur.com/3/image",
                    headers=headers,
                    files={'image': img_file},
                    data=data
                )
        
        response = await asyncio.to_thread(upload_request)
        result = response.json()

        if response.status_code == 200 and result['success']:
            link = result['data']['link']
            end = datetime.now()
            ms = (end - start).seconds
            
            await msg.edit_text(
                f"✅ **Uploaded to Imgur!**\n\n"
                f"🔗 **Link:** [Click Here]({link})\n"
                f"⏱ **Time:** `{ms}s`",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔗 Open Link", url=link)]]
                )
            )
        else:
            error_msg = result.get('data', {}).get('error', 'Unknown Error')
            await msg.edit_text(f"❌ **Imgur Failed:** `{error_msg}`")

    except Exception as e:
        await msg.edit_text(f"❌ **Error:** `{e}`")
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
