import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired

# ================= CONFIG ================= #

GROUP_IDS = [
    -1003673296456,
    -1003374582476
]

GROUP_TITLE = "💭 𝐂ʜʌᴛ 𔘓 𝐇ᴏᴜƨᴇ 𓂃ꠂ💗ˎˊ˗"

UPDATE_INTERVAL = 30  # seconds

# ========================================== #


async def auto_update_group_titles(app: Client):
    await app.wait_until_ready()
    print("[AUTO-TITLE] Multi-group title updater started")

    while True:
        for group_id in GROUP_IDS:
            try:
                await app.set_chat_title(
                    chat_id=group_id,
                    title=GROUP_TITLE
                )

            except FloodWait as e:
                await asyncio.sleep(e.value + 5)

            except ChatAdminRequired:
                print(f"[AUTO-TITLE] Missing admin permission in {group_id}")

            except Exception as e:
                print(f"[AUTO-TITLE ERROR] {group_id}: {e}")

        await asyncio.sleep(UPDATE_INTERVAL)


# ================= AUTO START ================= #
try:
    from VIPMUSIC import app
except ImportError:
    from main import app

app.loop.create_task(auto_update_group_titles(app))
