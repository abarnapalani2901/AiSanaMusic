import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired

# ================= CONFIG ================= #
TARGET_GROUP_ID = -1003374582476

GROUP_TITLE = "💭 𝐂ʜʌᴛ 𔘓 𝐇ᴏᴜƨᴇ 𓂃ꠂ💗ˎˊ˗"

UPDATE_INTERVAL = 30  # seconds
# ========================================= #


async def auto_update_group_title(app: Client):
    await app.wait_until_ready()
    print("[AUTO-TITLE] Group title updater started")

    while True:
        try:
            await app.set_chat_title(
                chat_id=TARGET_GROUP_ID,
                title=GROUP_TITLE
            )
            await asyncio.sleep(UPDATE_INTERVAL)

        except FloodWait as e:
            await asyncio.sleep(e.value + 5)

        except ChatAdminRequired:
            print("[AUTO-TITLE] ERROR: Bot is not admin or missing permission")
            await asyncio.sleep(120)

        except Exception as e:
            print(f"[AUTO-TITLE ERROR] {e}")
            await asyncio.sleep(60)


# ================= AUTO START ================= #
from VIPMUSIC import app  # fallback handled by repo

app.loop.create_task(auto_update_group_title(app))
