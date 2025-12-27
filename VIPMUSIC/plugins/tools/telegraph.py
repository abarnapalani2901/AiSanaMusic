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

IMGUR_CLIENT_ID = "5d42a2e5b19fe1d" 

# ---------------- HELPER ---------------- #
def resize_image(image_path):
    try:
        im = Image.open(image_path)
        im.save(image_path, "PNG")
    except Exception as e:
        print(f"Resize Error: {e}")

# ---------------- PM HANDLER ---------------- #
async def send_to_pm(client, message, link, platform):
    """Sends the upload link directly to the user's PM."""
    user_id = message.from_user.id
    try:
        await client.send_message(
            user_id,
            f"✅ **Your {platform} Upload**\n\n"
            f"🔗 **Link:** {link}\n"
            f"📂 **Source:** {message.chat.title or 'Private Chat'}",
            disable_web_page_preview=True
        )
    except:
        # Fails if user hasn't started the bot in PM or blocked it
        pass

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
                f"⏱ **Time:** `{ms}s`\n"
                f"📨 **Check PM for a copy!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open Link", url=url)]])
            )
            
            # Send to PM
            await send_to_pm(client, message, url, "Telegraph Media")

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
            return await msg.edit_text("❌ **Please reply to text.**")

        title = f"{message.from_user.first_name}'s Paste"
        if len(message.command) > 1:
            title = message.text.split(None, 1)[1]

        try:
            page_content = page_content.replace("\n", "<br>")
            response = telegraph.create_page(title=title, html_content=page_content)
            url = f"https://graph.org/{response['path']}"

            await msg.edit_text(
                f"✅ **Page Created!**\n\n"
                f"📄 **Title:** `{title}`\n"
                f"🔗 **Link:** [Click Here]({url})\n"
                f"📨 **Check PM for a copy!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open Page", url=url)]])
            )
            
            # Send to PM
            await send_to_pm(client, message, url, "Telegraph Text")
            
        except Exception as e:
            await msg.edit_text(f"❌ **Error:** `{e}`")


# ---------------- IMGUR COMMAND ---------------- #
@app.on_message(filters.command(["imgur", "ig"], prefixes=["/", "!", ".", ",",]) & ~BANNED_USERS)
async def imgur_upload(client, message):
    if not message.reply_to_message or not message.reply_to_message.media:
        return await message.reply_text("⚠️ **Reply to media to upload to Imgur!**")

    msg = await message.reply_text("<code>📥 Downloading...</code>")
    start = datetime.now()
    local_path = None

    try:
        local_path = await message.reply_to_message.download()
        if local_path.endswith((".webp", ".tgs")):
            resize_image(local_path)

        await msg.edit_text("<code>📤 Uploading to Imgur...</code>")

        headers = {'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'}
        data = {'type': 'file', 'title': 'Uploaded by VIPMUSIC', 'description': 'Uploaded via Pyrogram Bot'}
        
        def upload_request():
            with open(local_path, 'rb') as img_file:
                return requests.post("https://api.imgur.com/3/image", headers=headers, files={'image': img_file}, data=data)
        
        response = await asyncio.to_thread(upload_request)
        result = response.json()

        if response.status_code == 200 and result['success']:
            link = result['data']['link']
            ms = (datetime.now() - start).seconds
            
            await msg.edit_text(
                f"✅ **Uploaded to Imgur!**\n\n"
                f"🔗 **Link:** [Click Here]({link})\n"
                f"⏱ **Time:** `{ms}s`\n"
                f"📨 **Check PM for a copy!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open Link", url=link)]])
            )
            
            # Send to PM
            await send_to_pm(client, message, link, "Imgur")
        else:
            await msg.edit_text(f"❌ **Failed:** `{result.get('data', {}).get('error', 'Unknown')}`")

    except Exception as e:
        await msg.edit_text(f"❌ **Error:** `{e}`")
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
