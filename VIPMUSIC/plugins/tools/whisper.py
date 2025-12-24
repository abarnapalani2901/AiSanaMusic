from VIPMUSIC import app as bot
from config import BOT_USERNAME
from pyrogram import filters
from pyrogram.types import (
    InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQueryResultPhoto
)
from pyrogram.errors import Unauthorized
from youtubesearchpython.__future__ import VideosSearch

print("[whisper] whisper loaded")

whisper_db = {}

# --- 1. CONFIGURATION ---
THUMB_URL = "https://graph.org/file/ffdb1be822436121cf5fd.png"

switch_btn = InlineKeyboardMarkup([[InlineKeyboardButton("●ᥫᩣ Sᴛᴀʀᴛ Wʜɪsᴘᴇʀ", switch_inline_query_current_chat="")]])

# --- 2. YOUTUBE SEARCH (Fallback) ---
async def get_youtube_results(text):
    try:
        results = []
        a = VideosSearch(text, limit=20)
        result = (await a.next()).get("result")
        for x in range(15):
            title = (result[x]["title"]).title()
            duration = result[x]["duration"]
            views = result[x]["viewCount"]["short"]
            thumbnail = result[x]["thumbnails"][0]["url"].split("?")[0]
            channellink = result[x]["channel"]["link"]
            channel = result[x]["channel"]["name"]
            link = result[x]["link"]
            published = result[x]["publishedTime"]
            description = f"{views} | {duration} ᴍɪɴᴜᴛᴇs | {channel}  | {published}"
            
            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʏᴏᴜᴛᴜʙᴇ 🎄",
                            url=link,
                        )
                    ],
                ]
            )
            
            searched_text = f"""
❄ <b>ᴛɪᴛʟᴇ :</b> <a href={link}>{title}</a>

⏳ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> {duration} ᴍɪɴᴜᴛᴇs
👀 <b>ᴠɪᴇᴡs :</b> <code>{views}</code>
🎥 <b>ᴄʜᴀɴɴᴇʟ :</b> <a href={channellink}>{channel}</a>
⏰ <b>ᴘᴜʙʟɪsʜᴇᴅ ᴏɴ :</b> {published}


<u><b>➻ ɪɴʟɪɴᴇ sᴇᴀʀᴄʜ ᴍᴏᴅᴇ ʙʏ {bot.name}</b></u>"""
            
            results.append(
                InlineQueryResultPhoto(
                    photo_url=thumbnail,
                    title=title,
                    thumb_url=thumbnail,
                    description=description,
                    caption=searched_text,
                    reply_markup=buttons,
                )
            )
        return results
    except Exception as e:
        return []

# --- 3. WHISPER LOGIC ---
async def _whisper(_, inline_query):
    data = inline_query.query
    splitted = data.split()
    results = []
    
    # If the text is too short, it's likely a song search.
    if len(splitted) < 2:
        yt_results = await get_youtube_results(data)
        if yt_results:
            return yt_results
        else:
            mm = [
                InlineQueryResultArticle(
                    title="⦿ Wʜɪsᴘᴇʀ ⦿",
                    description=f"@{BOT_USERNAME} [ USERNAME | ID ] [ TEXT ]",
                    input_message_content=InputTextMessageContent(f"⦿ Usᴀɢᴇ:\n\n@{BOT_USERNAME} [ USERNAME | ID ] [ TEXT ]"),
                    thumb_url=THUMB_URL,
                    reply_markup=switch_btn
                )
            ]
            results.append(mm)
            return results

    # Try to find a user to create a whisper
    try:
        user = None
        msg = ""

        # Check: @User Message
        try:
            user = await _.get_users(splitted[0])
            msg = " ".join(splitted[1:])
        except:
            # Check: Message @User
            try:
                user = await _.get_users(splitted[-1])
                msg = " ".join(splitted[:-1])
            except:
                # No user found, assume it is a song search
                raise Exception("User not found")

        whisper_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❥ Wʜɪsᴘᴇʀ", callback_data=f"fdaywhisper_{inline_query.from_user.id}_{user.id}")]])
        one_time_whisper_btn = InlineKeyboardMarkup([[InlineKeyboardButton("☞ Oɴᴇ-Tɪᴍᴇ Wʜɪsᴘᴇʀ", callback_data=f"fdaywhisper_{inline_query.from_user.id}_{user.id}_one")]])
        
        # THIS IS THE PART THAT SHOWS WHISPER AT THE TOP
        mm = [
            InlineQueryResultArticle(
                title="⦿ Wʜɪsᴘᴇʀ ⦿",
                description=f"Sᴇɴᴅ A Wʜɪsᴘᴇʀ Tᴏ {user.first_name}!",
                input_message_content=InputTextMessageContent(f"⦿ Yᴏᴜ Aʀᴇ Sᴇɴᴅɪɴɢ A Wʜɪsᴘᴇʀ Tᴏ {user.first_name}.\n\nTʏᴘᴇ Uʀ Mᴇssᴀɢᴇ/Sᴇɴᴛᴇɴᴄᴇ."),
                thumb_url=THUMB_URL,
                reply_markup=whisper_btn
            ),
            InlineQueryResultArticle(
                title="➤ Oɴᴇ-Tɪᴍᴇ Wʜɪsᴘᴇʀ",
                description=f"Sᴇɴᴅ A Oɴᴇ-Tɪᴍᴇ Wʜɪsᴘᴇʀ Tᴏ {user.first_name}!",
                input_message_content=InputTextMessageContent(f"☞ Yᴏᴜ Aʀᴇ Sᴇɴᴅɪɴɢ A Oɴᴇ-Tɪᴍᴇ Wʜɪsᴘᴇʀ Tᴏ {user.first_name}.\n\nTʏᴘᴇ Uʀ Mᴇssᴀɢᴇ/Sᴇɴᴇᴛᴇɴᴄᴇ."),
                thumb_url=THUMB_URL,
                reply_markup=one_time_whisper_btn
            )
        ]
        
        whisper_db[f"{inline_query.from_user.id}_{user.id}"] = msg
        results.extend(mm)
        return results

    except Exception as e:
        # If no user found, search YouTube
        yt_results = await get_youtube_results(data)
        if yt_results:
            return yt_results
        else:
            mm = [
                InlineQueryResultArticle(
                    title="⦿ Wʜɪsᴘᴇʀ ⦿",
                    description="Iɴᴠᴀʟɪᴅ Usᴇʀɴᴀᴍᴇ ᴏʀ Iᴅ!",
                    input_message_content=InputTextMessageContent("ɪɴᴠᴀʟɪᴅ Usᴇʀɴᴀᴍᴇ ᴏʀ Iᴅ!"),
                    thumb_url=THUMB_URL,
                    reply_markup=switch_btn
                )
            ]
            results.append(mm)
            return results

# --- 4. CALLBACKS ---
@bot.on_callback_query(filters.regex(pattern=r"fdaywhisper_(.*)"))
async def whispes_cb(_, query):
    data = query.data.split("_")
    from_user = int(data[1])
    to_user = int(data[2])
    user_id = query.from_user.id
    
    if user_id not in [from_user, to_user, 1983816571]:
        try:
            await _.send_message(from_user, f"{query.from_user.mention} Is Tʀʏɪɴɢ Tᴏ Oᴘᴇɴ Uʀ Wʜɪsᴘᴇʀ.")
        except Unauthorized:
            pass
        return await query.answer("Tʜɪs Wʜɪsᴘᴇʀ Is Nᴏᴛ Fᴏʀ Yᴏᴜ 𖣘︎", show_alert=True)
    
    search_msg = f"{from_user}_{to_user}"
    
    try:
        msg = whisper_db[search_msg]
    except:
        msg = "𖣘︎ Eʀʀᴏʀ!\n\nWʜɪsᴘᴇʀ Hᴀs Bᴇᴇɴ Dᴇʟᴇᴛᴇᴅ Fʀᴏᴍ Tʜᴇ Dᴀᴛᴀʙᴀsᴇ!"
    
    SWITCH = InlineKeyboardMarkup([[InlineKeyboardButton("Gᴏ Iɴʟɪɴᴇ ➻", switch_inline_query_current_chat="")]])
    
    await query.answer(msg, show_alert=True)
    
    if len(data) > 3 and data[3] == "one":
        if user_id == to_user:
            await query.edit_message_text("➤ Wʜɪsᴘᴇʀ Hᴀs Bᴇᴇɴ Rᴇᴀᴅ!\n\nPʀᴇss Tʜᴇ Bᴜᴛᴛᴏɴ Bᴇʟᴏᴡ Tᴏ Sᴇɴᴅ A Wʜɪsᴘᴇʀ!", reply_markup=SWITCH)

# --- 5. DEFAULT HELP (Shows First) ---
async def in_help():
    whisper_answers = [
        InlineQueryResultArticle(
            title="⦿ Whisper ⦿",
            description=f"@{BOT_USERNAME} [USERNAME | ID] [TEXT]",
            input_message_content=InputTextMessageContent(f"**❍ Usage:**\n\n@{BOT_USERNAME} (Target Username or ID) (Your Message).\n\n**Example:**\n@{BOT_USERNAME} @user_username/id ʜᴇʏ ᴄᴜᴛɪᴇ, ɪ ᴍɪ𝗌𝗌 ᴜ "),
            thumb_url=THUMB_URL,
            reply_markup=switch_btn
        )
    ]
    return whisper_answers

# --- 6. HANDLER ---
@bot.on_inline_query()
async def bot_inline(_, inline_query):
    string = inline_query.query.lower()
    
    if string.strip() == "":
        answers = await in_help()
        await inline_query.answer(answers)
    else:
        answers = await _whisper(_, inline_query)
        await inline_query.answer(answers, cache_time=0)
