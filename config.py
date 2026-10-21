import re
import os
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

# Get this value from my.telegram.org/apps
API_ID = int(getenv("API_ID","35217688"))
API_HASH = getenv("API_HASH", "725c7b4b34de7401b31c8b7f1ceb18e0")
# ------------------------------------------------------
BOT_TOKEN = getenv("BOT_TOKEN", "8777174568:AAHAeEw6rENtARj6OBFXD7DHapSN32m62QY")
# -------------------------------------------------------
OWNER_USERNAME = getenv("OWNER_USERNAME","Ak_Power_47")
# --------------------------------------------------------
BOT_USERNAME = getenv("BOT_USERNAME" , "AiSanaXbot")
# --------------------------------------------------------
BOT_NAME = getenv("BOT_NAME" , "𝐀𝐢 𝐒𝐡𝐚𝐧𝐚 𝐌𝐮𝐬𝐢𝐜")
# ---------------------------------------------------------
ASSUSERNAME = getenv("ASSUSERNAME" , "Kuttima_1")

EVALOP = list(map(int, getenv("EVALOP", "1281282633 8399160924 6773435708").split()))
MONGO_DB_URI = getenv("MONGO_DB_URI","mongodb+srv://zewdatabase:ijoXgdmQ0NCyg9DO@zewgame.urb3i.mongodb.net/ontap?retryWrites=true&w=majority")
GPT_API = getenv("GPT_API", "sk-proj-h6pk40oVRIxpXwrf3i50T3BlbkFJGVET8wX1yJtdi0zCWjDQ")
PLAYHT_API = getenv("PLAYHT_API", "22e323f342024c0fb4ee430eeb9d0011")
DATABASE_NAME = getenv("DATABASE_NAME","aisanaFed")
#ChatBot
MONGO_URL = getenv("MONGO_URL","mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority")
#Reaction Bot - TRUE on / FALSE off
REACTION_ENABLED = getenv("REACTION_ENABLED","True")

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 17000))

# Chat id of a group for logging bot's activities
LOGGER_ID = int(getenv("LOGGER_ID", "-1002275616383"))
LOG_GROUP_ID = int(getenv("LOG_GROUP_ID", "-1002275616383"))
LOG_CHANNEL = int(getenv("LOG_CHANNEL", "-1002275616383")) #fed_logs

# Get this value from  on Telegram by /id
OWNER_ID = int(getenv("OWNER_ID", 8997214968))
SUDOERS = getenv("SUDOERS", "8997214968 5574295371 8671058334 1281282633 6773435708").split()


SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/TamilFRlE")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/TamilFRlE")
MUST_JOIN = getenv("MUST_JOIN", "HeartBeat_Offi")

#Ranking
AUTOPOST_TIME_HOUR = 21
AUTOPOST_TIME_MINUTE = 0

# Maximum Limit Allowed for users to save playlists on bot's server
SERVER_PLAYLIST_LIMIT = int(getenv("SERVER_PLAYLIST_LIMIT", "3000"))

# MaximuM limit for fetching playlist's track from youtube, spotify, apple links.
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", "2500"))
# Set this to True if you want the assistant to automatically leave chats after an interval
AUTO_LEAVING_ASSISTANT = False

#Auto Gcast/Broadcast Handler (True = broadcast on , False = broadcast off During Hosting, Dont Do anything here.)
AUTO_GCAST = os.getenv("AUTO_GCAST","False")

#Auto Broadcast Message That You Want Use In Auto Broadcast In All Groups.
AUTO_GCAST_MSG = getenv("AUTO_GCAST_MSG", "<blockquote>⋆｡°✩ **𝐋ᴇᴛƨ𝐕ɪʙᴇ𝐎ᴜᴛ** ✩°｡⋆\n[💋⟵꯭᪵〬𓂋⃝᜴͓ ⃪𝐒ㅤ͓ᷘɪㅤ⃪ᷢ𝐋ㅤ͓ᷴᴜㅤ⃪͓ᷚ𝐊 ₋ ͓ᷤᴋㅤ͢ ̌̍𝐔 🍷𓂃](https://t.me/SilukkuMusicBot)</blockquote>\n<blockquote>➽───𝐅ᴇᴧᴛᴜꝛᴇ𝗌-ɪɴ𝗌ɪᴅᴇ───❥\n🔻 ꝛᴏ𝗌ᴇ ғᴜηᴄᴛɪᴏɴ𝗌|ғᴇᴅ ❅ ꝛᴧηᴋɪɴɢ\n🔻 ᴡʜɪ𝗌ᴘᴇꝛ ϻ𝗌ɢ ❅ 𝗌ᴧηɢ-ϻᴧᴛᴧ\n🔻 ϻᴇɴᴛɪᴏη ❅ ᴄʜᴧᴛ|ꝛᴇᴧᴄᴛ\n─⋆｡°✩ **𝐋ᴏᴠᴇ-𝐌ᴧɢɪᴄ** ✩°｡⋆─\n🔻 ᴄᴏᴜᴘʟᴇ𝗌   ❅ ʟᴏᴠᴇ\n🔻 ғʟᴧϻᴇs     ❅ ᴜꝛᴜᴛᴛᴜ\n─⋆｡°✩ **𝐓ʜᴇ-𝐁ꝛᴇᴧᴋᴅᴏᴡɴ** ✩°｡⋆─\n🔻 ʟᴧɢ-ғʀᴇᴇ ϻᴜ𝗌ɪᴄ\n🔻 ᴠɪᴅᴇᴏ/ᴧᴜᴅɪᴏ ᴅᴏᴡηʟᴏᴧᴅ\n🔻 𝗌ᴜᴘᴘᴏꝛᴛ ʟɪηᴋs/ᴜꝛʟ'𝗌\n🔻 𝗌ᴜᴘᴘᴏꝛᴛ ʟɪᴠᴇ-𝗌ᴛʀᴇᴧϻ\n🔻 𝗌ᴜᴘᴘᴏꝛᴛ ɪɴ𝗌ᴛᴧ ᴅᴏᴡηʟᴏᴧᴅ𝗌</blockquote>\n<blockquote>𝆺𝅥 𝐃σит тσʋᴄн мʏ || [𝐂𝖗𝖚𝖘𝖍 🦇](https://t.me/rajeshrakis) ||</blockquote>")

# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "")


# Maximum limit for fetching playlist's track from youtube, spotify, apple links.
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 2500))


# Telegram audio and video file size limit (in bytes)
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 904857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 973741824))
# Checkout https://www.gbmb.org/mb-to-bytes for converting mb to bytes

# Time after which bot will suggest random chats about bot commands.
AUTO_SUGGESTION_TIME = int(
    getenv("AUTO_SUGGESTION_TIME", "3")
)  # Remember to give value in Seconds

# Set it True if you want to bot to suggest about bot commands to random chats of your bots.
AUTO_SUGGESTION_MODE = getenv("AUTO_SUGGESTION_MODE", "True")
# Cleanmode time after which bot will delete its old messages from chats
CLEANMODE_DELETE_MINS = int(
    getenv("CLEANMODE_MINS", "5")
)  # Remember to give value in Seconds

## Fill these variables if you're deploying on heroku.
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
# Get it from http://dashboard.heroku.com/account
HEROKU_API_KEY = getenv("HEROKU_API_KEY", "HRKU-fc1b7aea-b37a-4015-9877-8c3967ee97bc")

UPSTREAM_REPO = getenv(
    "UPSTREAM_REPO",
    "https://github.com/abarnapalani2901/AiSanaMusic",
)
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "master")
GIT_TOKEN = getenv(
    "GIT_TOKEN", None
)  # Fill this variable if your upstream repository is private


# Get your pyrogram v2 session from @VIP_STRING_ROBOT on Telegram
STRING1 = getenv("STRING_SESSION2", "BQH2LbkAJN5Qqln8V0uZIhbXPAAf1nwYxg7v9mK-sDXScVsaJwFPOEXBEZZbG7HxMIekPBoHPdH8RZF45vcXnrHnSKT1QRbxoLaRlaIGp1Rw_NpMmQZjJWAWpehC2FSH3q3NfXm__4p1lU-uyZj3PBuJYwayV4emtUmw4HWbnlbtEFbcvGXow9u8eW3Rugwz9qZCMFgaf5MOKDgR5Sf6hnrkrvW90slsiKmCZMV48G9UMyLz1-mn8jDcTLWvO0ZtMIcEDLjVoVRnp2CvIbKwvpOrpevprexPYcOk4HIQa1-LDYHVvI3owH41ramdTovXBn1rWMQGkutxAq6wIt-ucRv0827IlQAAAAIYRpr4AA")
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)


YUMI_PICS = [
    "https://files.catbox.moe/mus8qn.jpg",
    "https://files.catbox.moe/n7t6ma.jpg",
    "https://files.catbox.moe/tb66lq.jpg",
    "https://files.catbox.moe/imwrq4.jpg",
    "https://files.catbox.moe/3u3dcp.jpg",
    "https://files.catbox.moe/70fnlf.jpg",
    "https://files.catbox.moe/i8r1dm.jpg",
    "https://files.catbox.moe/5u11yx.jpg"
]

START_IMG_URL = getenv(
    "START_IMG_URL", "https://i.ibb.co/8LtBzCNK/jjj.jpg"
)
PING_IMG_URL = getenv(
    "PING_IMG_URL", "https://graph.org/file/ffdb1be822436121cf5fd.png"
)
RANKING_PIC = "https://files.catbox.moe/pfjca4.jpg"
PLAYLIST_IMG_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
STATS_IMG_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
TELEGRAM_AUDIO_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
TELEGRAM_VIDEO_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
STREAM_IMG_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
SOUNCLOUD_IMG_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
YOUTUBE_IMG_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
SPOTIFY_ARTIST_IMG_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
SPOTIFY_ALBUM_IMG_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"
SPOTIFY_PLAYLIST_IMG_URL = "https://graph.org/file/f21bcb4b8b9c421409b64.png"

GREET = [
    "💞", "🥂", "🔍", "🧪", "🥂", "⚡️", "🔥", "🦋", "🎩", "🌈", "🍷", "🥂", "🦋", "🥃", "🥤", "🕊️",
    "🦋", "🦋", "🕊️", "⚡️", "🕊️", "⚡️", "⚡️", "🥂", "💌", "🥂", "🥂", "🧨"
]
MENTION_USERNAMES = [
    "/start",
    "/help",
    "Ghost Bat",
    "Shasha",
    "bat here",
    "@"
]
START_REACTIONS = [
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", 
    "🤯", "😱", "🤬", "😢", "🎉", "🤩", "🤮", "💩",
    "🙏", "👌", "🕊", "🤡", "🥱", "🥴", "😍", "🐳",
    "❤", "🔥", "💔", "💯", "🤣", "⚡", "💘", "🏆",
    "🍓", "🍾", "💋", "💘", "😈", "😴", "😭", "🤓",
    "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨", "🤝",
    "✍", "🤗", "🫡", "🎅", "🎄", "☃", "💅", "🤪",
    "🗿", "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊",
    "😎", "👾", "🤷‍♂", "🤷", "🤷‍♀", "😡"
]


#       ___ ______________   _____ __________________________________________   ________________
#      /   |   \_   _____/  /  _  \\______   \__    ___/\______   \_   _____/  /  _  \__    ___/
#     /    ~    \    __)_  /  /_\  \|       _/ |    |    |    |  _/|    __)_  /  /_\  \|    |   
#     \    Y    /        \/    |    \    |   \ |    |    |    |   \|        \/    |    \    |   
#      \___|_  /_______  /\____|__  /____|_  / |____|    |______  /_______  /\____|__  /____|   
#            \/        \/         \/       \/                   \/        \/         \/         

BANNED_USERS = filters.user()
#BANNED_USERS = filters.user([])
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}
chatstats = {}
userstats = {}
clean = {}

autoclean = []


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))


if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_CHAT:
    if not re.match("(?:http|https)://", SUPPORT_CHAT):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHAT url is wrong. Please ensure that it starts with https://"
        )
