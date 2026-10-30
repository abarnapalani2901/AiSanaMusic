
import asyncio
import importlib

from pyrogram import idle

import config
from config import BANNED_USERS

from VIPMUSIC import LOGGER, app, userbot, telethn
from VIPMUSIC.core.call import VIP
from VIPMUSIC.misc import sudo
from VIPMUSIC.plugins import ALL_MODULES
from VIPMUSIC.utils.database import get_banned_users, get_gbanned

from keep_alive import keep_alive
from autorestart import autorestart


async def init_bot(started):
    # ----------------------------------------------------
    # CHECK SESSION STRINGS
    # ----------------------------------------------------
    if not any([
        config.STRING1,
        config.STRING2,
        config.STRING3,
        config.STRING4,
        config.STRING5
    ]):
        LOGGER(__name__).error(
            "𝐒𝐭𝐫𝐢𝐧𝐠 𝐒𝐞𝐬𝐬𝐢𝐨𝐧 𝐍𝐨𝐭 𝐅𝐢𝐥𝐥𝐞𝐝, "
            "𝐏𝐥𝐞𝐚𝐬𝐞 𝐅𝐢𝐥𝐥 𝐀 𝐏𝐲𝐫𝐨𝐠𝐫𝐚𝐦 V2 𝐒𝐞𝐬𝐬𝐢𝐨𝐧🤬"
        )

    # ----------------------------------------------------
    # LOAD SUDO USERS
    # ----------------------------------------------------
    await sudo()

    # ----------------------------------------------------
    # LOAD BANNED USERS
    # ----------------------------------------------------
    try:
        gb = await get_gbanned()
        for u in gb:
            BANNED_USERS.add(u)

        ban = await get_banned_users()
        for u in ban:
            BANNED_USERS.add(u)

    except Exception as e:
        LOGGER(__name__).warning(
            f"Failed to load banned users: {e}"
        )

    # ----------------------------------------------------
    # START MAIN BOT
    # ----------------------------------------------------
    await app.start()
    started["app"] = True

    # ----------------------------------------------------
    # LOAD ALL PLUGINS
    # ----------------------------------------------------
    for all_module in ALL_MODULES:
        try:
            importlib.import_module(
                "VIPMUSIC.plugins" + all_module
            )
        except Exception as e:
            LOGGER("VIPMUSIC.plugins").error(
                f"Failed to load plugin {all_module}: {e}"
            )

    LOGGER("VIPMUSIC.plugins").info(
        "𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝🥳..."
    )

    # ----------------------------------------------------
    # START USERBOT
    # ----------------------------------------------------
    await userbot.start()
    started["userbot"] = True

    # ----------------------------------------------------
    # START VOICE CALL SYSTEM
    # ----------------------------------------------------
    await VIP.start()
    await VIP.decorators()

    # ----------------------------------------------------
    # BOT STARTED SUCCESSFULLY
    # ----------------------------------------------------
    LOGGER("VIPMUSIC").info(
        r"""
╔═════ஜ۩۞۩ஜ════╗
  ♨️𝗠𝗔𝗗𝗘 𝗕𝗬 𝗩𝗜𝗣 𝗕𝗢𝗬♨️
╚═════ஜ۩۞۩ஜ════╝
        """
    )


async def main():

    started = {
        "telethn": False,
        "app": False,
        "userbot": False
    }

    try:
        # ------------------------------------------------
        # START TELETHON FIRST
        # ------------------------------------------------
        await telethn.start(
            bot_token=config.BOT_TOKEN
        )
        started["telethn"] = True

        # ------------------------------------------------
        # INITIALIZE BOT
        # ------------------------------------------------
        await init_bot(started)

        # ------------------------------------------------
        # KEEP BOT RUNNING
        # ------------------------------------------------
        LOGGER("VIPMUSIC").info(
            "Bot is running successfully..."
        )

        await idle()

    except KeyboardInterrupt:
        LOGGER("VIPMUSIC").info(
            "Bot stopped manually."
        )

    except Exception as e:
        LOGGER("VIPMUSIC").error(
            f"Main bot error: {e}"
        )
        raise

    finally:
        # ------------------------------------------------
        # CLEAN SHUTDOWN
        # ------------------------------------------------

        if started["telethn"]:
            try:
                await telethn.disconnect()
                LOGGER("VIPMUSIC").info(
                    "Telethon disconnected."
                )
            except Exception as e:
                LOGGER("VIPMUSIC").warning(
                    f"Telethon shutdown error: {e}"
                )

        if started["userbot"]:
            try:
                await userbot.stop()
                LOGGER("VIPMUSIC").info(
                    "Userbot stopped."
                )
            except Exception as e:
                LOGGER("VIPMUSIC").warning(
                    f"Userbot shutdown error: {e}"
                )

        if started["app"]:
            try:
                await app.stop()
                LOGGER("VIPMUSIC").info(
                    "Main bot stopped."
                )
            except Exception as e:
                LOGGER("VIPMUSIC").warning(
                    f"Main bot shutdown error: {e}"
                )

        LOGGER("VIPMUSIC").info(
            "VIPMUSIC shutdown completed."
        )


# ========================================================
# KEEP ALIVE + AUTORESTART
# ========================================================

def start_services():

    # ----------------------------------------------------
    # KEEP ALIVE SERVER
    # ----------------------------------------------------
    try:
        keep_alive()
        LOGGER("VIPMUSIC").info(
            "Keep Alive system started."
        )
    except Exception as e:
        LOGGER("VIPMUSIC").error(
            f"Keep Alive error: {e}"
        )

    # ----------------------------------------------------
    # AUTORESTART SYSTEM
    # ----------------------------------------------------
    try:
        autorestart()
        LOGGER("VIPMUSIC").info(
            "AutoRestart system started."
        )
    except Exception as e:
        LOGGER("VIPMUSIC").error(
            f"AutoRestart error: {e}"
        )


# ========================================================
# MAIN ENTRY POINT
# ========================================================

if __name__ == "__main__":

    # Start background services before the bot
    start_services()

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        LOGGER("VIPMUSIC").info(
            "Bot stopped manually."
        )

    except Exception as e:
        LOGGER("VIPMUSIC").error(
            f"Fatal startup error: {e}"
        )
