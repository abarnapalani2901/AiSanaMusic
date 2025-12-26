import aiohttp
from pyrogram import filters
from VIPMUSIC import app
from config import BANNED_USERS

# API URLs
truth_api_url = "https://api.truthordarebot.xyz/v1/truth"
dare_api_url = "https://api.truthordarebot.xyz/v1/dare"

# Standard prefixes for your bot
PREFIXES = ["/", "!", "%", ",", "", ".", "@", "#"]


@app.on_message(filters.command("truth", prefixes=PREFIXES) & ~BANNED_USERS)
async def get_truth(client, message):
    try:
        # Using aiohttp to prevent bot lag
        async with aiohttp.ClientSession() as session:
            async with session.get(truth_api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    truth_question = data["question"]
                    await message.reply_text(f"ᴛʀᴜᴛʜ ǫᴜᴇsᴛɪᴏɴ:\n\n{truth_question}")
                else:
                    await message.reply_text("ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴀ ᴛʀᴜᴛʜ ǫᴜᴇsᴛɪᴏɴ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.")
    except Exception as e:
        await message.reply_text("ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.")


@app.on_message(filters.command("dare", prefixes=PREFIXES) & ~BANNED_USERS)
async def get_dare(client, message):
    try:
        # Using aiohttp to prevent bot lag
        async with aiohttp.ClientSession() as session:
            async with session.get(dare_api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    dare_question = data["question"]
                    await message.reply_text(f"ᴅᴀʀᴇ ǫᴜᴇsᴛɪᴏɴ:\n\n{dare_question}")
                else:
                    await message.reply_text("ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴀ ᴅᴀʀᴇ ǫᴜᴇsᴛɪᴏɴ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.")
    except Exception as e:
        await message.reply_text("ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.")
