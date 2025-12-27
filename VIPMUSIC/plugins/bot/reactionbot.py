import asyncio
import random
import re
from typing import Set, Dict, Tuple, Optional

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.enums import ChatMemberStatus, ChatType

from VIPMUSIC import app
from config import MENTION_USERNAMES, START_REACTIONS, OWNER_ID
from VIPMUSIC.utils.database import mongodb

try:
    from VIPMUSIC.misc import SUDOERS
except Exception:
    SUDOERS = set()

# ---------------- DATABASE ----------------
COLLECTION = mongodb["reaction_mentions"]
SETTINGS = mongodb["reaction_settings"]

# ---------------- STATE ----------------
REACTION_ENABLED = True  # global default flag
CHAT_REACTION_OVERRIDES: Dict[int, bool] = {}
custom_mentions: Set[str] = set(x.lower().lstrip("@") for x in (MENTION_USERNAMES or []))

# ---------------- VALID REACTIONS ----------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "✨", "🔥", "💫",
    "💥", "🌸", "😍", "🥰", "💎", "🌙", "🌹", "😂",
    "😎", "🤩", "😘", "😉", "🤭", "💐", "😻", "🥳",
    "👍", "👎", "👏", "😁", "🤔", "😢", "🤯", "🤩", "🙏", "🎉"
}
SAFE_REACTIONS = [e for e in (START_REACTIONS or []) if e in VALID_REACTIONS]
if not SAFE_REACTIONS:
    SAFE_REACTIONS = list(VALID_REACTIONS)

chat_used_reactions: Dict[int, Set[str]] = {}

def next_emoji(chat_id: int) -> str:
    if chat_id not in chat_used_reactions:
        chat_used_reactions[chat_id] = set()

    used = chat_used_reactions[chat_id]
    if len(used) >= len(SAFE_REACTIONS):
        used.clear()

    remaining = [e for e in SAFE_REACTIONS if e not in used]
    if not remaining:
        return random.choice(SAFE_REACTIONS)
        
    emoji = random.choice(remaining)
    used.add(emoji)
    chat_used_reactions[chat_id] = used
    return emoji


# ---------------- HELPERS ----------------
async def load_custom_mentions():
    try:
        docs = await COLLECTION.find({}).to_list(length=None)
        for doc in docs:
            name = doc.get("name")
            if name:
                custom_mentions.add(str(name).lower().lstrip("@"))
        print(f"[ReactionBot] Loaded {len(custom_mentions)} triggers.")
    except Exception as e:
        print(f"[ReactionBot] DB load error: {e}")

async def load_reaction_state():
    global REACTION_ENABLED, CHAT_REACTION_OVERRIDES
    try:
        doc = await SETTINGS.find_one({"_id": "switch"})
        if doc is not None:
            REACTION_ENABLED = doc.get("enabled", True)
        
        cursor = SETTINGS.find({"_id": {"$regex": r"^chat:"}})
        docs = await cursor.to_list(length=None)
        for d in docs:
            try:
                chat_id = int(d["_id"].split(":", 1)[1])
                CHAT_REACTION_OVERRIDES[chat_id] = bool(d.get("enabled", True))
            except:
                continue
    except Exception as e:
        print(f"[ReactionBot] State load error: {e}")

# Start Loaders
loop = asyncio.get_event_loop()
loop.create_task(load_custom_mentions())
loop.create_task(load_reaction_state())


def is_reaction_enabled_for_chat(chat_id: int) -> bool:
    return CHAT_REACTION_OVERRIDES.get(chat_id, REACTION_ENABLED)


async def set_chat_reaction_enabled(chat_id: int, enabled: bool):
    key = f"chat:{chat_id}"
    await SETTINGS.update_one({"_id": key}, {"$set": {"enabled": enabled}}, upsert=True)
    CHAT_REACTION_OVERRIDES[chat_id] = enabled


async def clear_chat_reaction_override(chat_id: int):
    key = f"chat:{chat_id}"
    await SETTINGS.delete_one({"_id": key})
    if chat_id in CHAT_REACTION_OVERRIDES:
        del CHAT_REACTION_OVERRIDES[chat_id]


async def is_admin_or_sudo(client, message_obj) -> Tuple[bool, Optional[str]]:
    user = getattr(message_obj, "from_user", None)
    if not user: return False, "No user"
    
    if user.id == OWNER_ID or user.id in SUDOERS:
        return True, None
    
    chat = getattr(message_obj, "chat", None) or getattr(message_obj.message, "chat", None)
    if not chat: return False, "No chat"
    
    if chat.type == ChatType.PRIVATE:
        return False, "Private chat"

    try:
        member = await client.get_chat_member(chat.id, user.id)
        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
            return True, None
    except:
        pass
        
    return False, "Not Admin"


# ==============================================================================
#                               COMMAND HANDLERS
# ==============================================================================

@app.on_message(filters.command(["reaction", "react"], prefixes=["/", "!", "%", ",", ".", "@", "#"]))
async def react_command(client, message: Message):
    ok, _ = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text("⚠️ Only admins can use this.")
    
    chat_id = message.chat.id
    enabled = is_reaction_enabled_for_chat(chat_id)
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🍏 Enable Auto-React", callback_data=f"react_chat_on:{chat_id}"),
            InlineKeyboardButton("🍎 Disable Auto-React", callback_data=f"react_chat_off:{chat_id}")
        ]
    ])
    
    status_text = "🍏 𝐄ɴᴀʙʟᴇᴅ" if enabled else "🍎 𝐃ɪsᴀʙʟᴇᴅ"
    await message.reply_text(
        f"**🧩 Reaction Settings**\n\n"
        f"**Auto-Reaction:** {status_text}\n"
        f"__Note: Mention triggers ({len(custom_mentions)}) are ALWAYS enabled.__",
        reply_markup=kb
    )


@app.on_callback_query(filters.regex("^react_"))
async def reaction_callback(client, query: CallbackQuery):
    ok, _ = await is_admin_or_sudo(client, query.message)
    if not ok:
        return await query.answer("⚠️ Admins Only!", show_alert=True)
    
    action = query.data
    
    try:
        if action.startswith("react_chat_on:"):
            chat_id = int(action.split(":")[1])
            await set_chat_reaction_enabled(chat_id, True)
            await query.edit_message_text(f"✅ **Auto-Reactions Enabled!**")
            
        elif action.startswith("react_chat_off:"):
            chat_id = int(action.split(":")[1])
            await set_chat_reaction_enabled(chat_id, False)
            await query.edit_message_text(f"❌ **Auto-Reactions Disabled!**\n(Mention triggers will still work)")
            
    except Exception as e:
        print(f"Reaction Callback Error: {e}")


@app.on_message(filters.command("addreact", prefixes=["/"]))
async def add_react(client, message: Message):
    ok, _ = await is_admin_or_sudo(client, message)
    if not ok: return
    
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/addreact <word>`")
    
    word = message.command[1].lower()
    await COLLECTION.update_one({"name": word}, {"$set": {"name": word}}, upsert=True)
    custom_mentions.add(word)
    await message.reply_text(f"✨ Added trigger: `{word}`")


@app.on_message(filters.command("delreact", prefixes=["/"]))
async def del_react(client, message: Message):
    ok, _ = await is_admin_or_sudo(client, message)
    if not ok: return
    
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/delreact <word>`")
    
    word = message.command[1].lower()
    await COLLECTION.delete_one({"name": word})
    if word in custom_mentions:
        custom_mentions.remove(word)
    await message.reply_text(f"🗑 Deleted trigger: `{word}`")


@app.on_message(filters.command("reactlist", prefixes=["/"]))
async def list_react(client, message: Message):
    if not custom_mentions:
        return await message.reply_text("No triggers found.")
    
    txt = "\n".join(f"• `{x}`" for x in sorted(custom_mentions))
    await message.reply_text(f"**📜 Reaction Triggers (Always Active):**\n\n{txt}")


@app.on_message(filters.command("clearreact", prefixes=["/"]))
async def clear_react(client, message: Message):
    ok, _ = await is_admin_or_sudo(client, message)
    if not ok: return
    
    await COLLECTION.delete_many({})
    custom_mentions.clear()
    for n in (MENTION_USERNAMES or []):
        custom_mentions.add(n.lower().lstrip("@"))
        
    await message.reply_text("🧹 All custom triggers cleared.")


# ==============================================================================
#                               WATCHERS (GROUP 6)
# ==============================================================================

WORD_RE = re.compile(r"\b([\w@:\-\.]+)\b", flags=re.UNICODE)

@app.on_message(
    (filters.text | filters.caption),
    group=6
)
async def reaction_watcher(client, message: Message):
    if not message.from_user:
        return

    # 1. Ignore Commands
    text = message.text or message.caption or ""
    if text.startswith(("/", "!", ".", "#", "$")):
        return
    
    triggered = False
    
    # 2. CHECK TRIGGERS (These work even if Auto-Reaction is Disabled)
    try:
        words = set(m.group(1).lower() for m in WORD_RE.finditer(text))
        
        for trig in custom_mentions:
            if trig in words or trig in text.lower():
                await message.react(next_emoji(message.chat.id))
                triggered = True
                break
    except Exception:
        pass

    # 3. AUTO-REACT (Only if triggered is False AND Chat is Enabled)
    if not triggered:
        if is_reaction_enabled_for_chat(message.chat.id) and REACTION_ENABLED:
            try:
                # Random chance (optional)
                # if random.random() > 0.2: return 
                await message.react(next_emoji(message.chat.id))
            except:
                pass
