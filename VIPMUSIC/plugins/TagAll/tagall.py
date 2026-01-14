from VIPMUSIC import app 
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.types import ChatPermissions

print("[tagall] tagall, vctag")

spam_chats = []

EMOJI = [ "🦋🦋🦋🦋🦋",
          "🧚🌸🧋🍬🫖",
          "🥀🌷🌹🌺💐",
          "🌸🌿💮🌱🌵",
          "❤️💚💙💜🖤",
          "💓💕💞💗💖",
          "🌸💐🌺🌹🦋",
          "🍔🦪🍛🍲🥗",
          "🍎🍓🍒🍑🌶️",
          "🧋🥤🧋🥛💕",
          "🍬🍭🧁🎂🍡",
          "🍨🧉🍺☕🍻",
          "🥪🥧🍦🍥🍚",
          "🫖☕🍹💕🥛",
          "☕🧃🍩🍦🍙",
          "🍁🌾💮🍂🌿",
          "🌨️🌥️⛈️🌩️🌧️",
          "🌷🏵️🌸🌺💐",
          "💮🌼🌻🍀🍁",
          "🧟🦸🦹🧙👸",
          "🧅🍠🥕🌽🥦",
          "🐷🐹🐭🐨🐻‍❄️",
          "🦋🐇🐀🐈🐈‍⬛",
          "🌼🌳🌲🌴🌵",
          "🥩🍋🍐🍈🍇",
          "🍴🍽️🔪🍶🥃",
          "🕌🏰🏩⛩️🏩",
          "🎉🎊🎈🎂🎀",
          "🪴🌵🌴🌳🌲",
          "🎄🎋🎍🎑🎎",
          "🦅🦜🕊️🦤🦢",
          "🦤🦩🦚🦃🦆",
          "🐬🦭🦈🐋🐳",
          "🐔🐟🐠🐡🦐",
          "🦩🦀🦑🐙🦪",
          "🐦🦂🕷️🕸️🐚",
          "🥪🍰🥧🍨🍨",
          " 🥬🍉🧁🧇",
        ]

TAGMES = [
    "**Hey have u eat a food**",
    "**What is your native place**",
    "**Hope your day is going great**",
    "**Did you drink enough water today**",
    "**Work hard but don’t forget to smile**",
    "**How is everything going**",
    "**Small progress is still progress**",
    "**Are you enjoying your day**",
    "**Success starts with discipline**",
    "**What’s one good thing today**",

    "**Hello there, how are you feeling**",
    "**Take a deep breath and relax**",
    "**Consistency beats motivation**",
    "**Hope you are doing well**",
    "**Any plans for today**",
    "**Believe in your skills**",
    "**A positive mind changes everything**",
    "**How’s work going**",
    "**Learning never stops**",
    "**Stay focused and calm**",

    "**Good vibes only today**",
    "**Don’t forget to take breaks**",
    "**Hard work always pays off**",
    "**What made you smile today**",
    "**Keep going, you’re doing great**",
    "**Balance work and life**",
    "**How’s your mood today**",
    "**Progress over perfection**",
    "**Stay confident and kind**",
    "**Hope today treats you well**",

    "**Are you a tea or coffee person**",
    "**Dream big, start small**",
    "**Every day is a fresh start**",
    "**Did you rest well**",
    "**Focus on what you can control**",
    "**Your effort matters**",
    "**Let’s make today productive**",
    "**How’s the weather there**",
    "**Success loves preparation**",
    "**Stay humble, stay hungry**",

    "**Don’t stress, do your best**",
    "**One step at a time**",
    "**Your mindset is your power**",
    "**Hope you’re feeling positive**",
    "**Time management is self-respect**",
    "**Are you enjoying your work**",
    "**Stay patient and persistent**",
    "**Even small wins count**",
    "**What motivates you today**",
    "**Keep improving yourself**",

    "**Smile, it suits you**",
    "**Today is full of opportunities**",
    "**Do something that makes you happy**",
    "**How’s your energy level**",
    "**Discipline creates freedom**",
    "**Take care of yourself**",
    "**Growth happens outside comfort zones**",
    "**Hope you’re having a calm day**",
    "**Stay sharp and focused**",
    "**Your future depends on today**",

    "**Let’s keep things positive**",
    "**Did you finish your tasks**",
    "**Believe, act, achieve**",
    "**Good communication builds trust**",
    "**Are you feeling productive**",
    "**Success is a daily habit**",
    "**Kindness never goes out of style**",
    "**Hope everything is fine**",
    "**Learn something new today**",
    "**Your attitude matters most**",

    "**Work smart, not just hard**",
    "**Take responsibility, gain respect**",
    "**How’s life treating you**",
    "**Stay calm under pressure**",
    "**Focus brings results**",
    "**You are capable of more**",
    "**Let’s keep moving forward**",
    "**Did you smile today**",
    "**Professionalism builds reputation**",
    "**Stay consistent, stay winning**"
]

VC_TAG = [
    "🎧 **Voice chat is live, join now**",
    "🔊 **VC started, come and chill**",
    "🎙 **Let’s talk live on voice chat**",
    "📢 **Join the voice chat everyone**",
    "🎶 **VC is open, don’t be shy**",
    "🗣 **Hop into VC and say hi**",
    "🎧 **Live voice chat happening now**",
    "🔔 **VC alert, join the conversation**",
    "🎙 **Your mic is missing, join VC**",
    "💬 **Talk it out on voice chat**",

    "😄 **Friendly VC open, join us**",
    "🎧 **Good vibes VC is live**",
    "🗨 **Let’s discuss on voice chat**",
    "🔥 **VC live now, don’t miss it**",
    "🎙 **Come share your thoughts on VC**",
    "📣 **Voice chat invite for everyone**",
    "😊 **Casual talk VC is open**",
    "🎧 **Join VC for fun talks**",
    "🗣 **Speak freely on voice chat**",
    "🎙 **Mic check, VC is live**",

    "😎 **Cool people in VC, join now**",
    "🎧 **Relax and talk in VC**",
    "🗨 **Open voice chat, join anytime**",
    "🔥 **Live discussion on VC**",
    "🎙 **Your voice matters, join VC**",
    "📢 **VC started, come interact**",
    "😁 **Fun VC session going on**",
    "🎧 **Let’s connect on voice chat**",
    "🗣 **Talk live, join the VC**",
    "🎙 **VC room is open now**",

    "🤝 **Professional talk VC is live**",
    "🎧 **Discussion VC started**",
    "🗨 **Join VC for a quick chat**",
    "🔥 **Active VC, hop in**",
    "🎙 **Speak your mind on VC**",
    "📣 **Voice chat now live**",
    "🙂 **Friendly VC open for all**",
    "🎧 **Join VC and feel relaxed**",
    "🗣 **Live voices, real talks**",
    "🎙 **VC is waiting for you**",

    "😌 **Peaceful VC session open**",
    "🎧 **Join VC, no typing needed**",
    "🗨 **Talk more, type less – VC**",
    "🔥 **VC live, join the flow**",
    "🎙 **Come on mic, join VC**",
    "📢 **Voice chat started now**",
    "😁 **Light talks in VC, join**",
    "🎧 **VC is open, feel free**",
    "🗣 **Live conversation on VC**",
    "🎙 **Join VC and be heard**",

    "😇 **Calm VC session going on**",
    "🎧 **Let’s have a voice chat**",
    "🗨 **VC open for discussion**",
    "🔥 **Hot topics on VC**",
    "🎙 **Join VC, mic on**",
    "📣 **Voice chat invitation**",
    "😊 **Chill VC open now**",
    "🎧 **Join VC for friendly talks**",
    "🗣 **Speak live, join VC**",
    "🎙 **VC is live, join fast**",

    "😄 **Fun + talk VC open**",
    "🎧 **Join VC and enjoy**",
    "🗨 **Open mic VC session**",
    "🔥 **VC live, everyone welcome**",
    "🎙 **Time to talk on VC**",
    "📢 **Voice chat is active now**",
    "🙂 **Friendly voices in VC**",
    "🎧 **Join VC and connect**",
    "🗣 **Live voice, real connection**",
    "🎙 **VC open, come join us**"
]



@app.on_message(filters.command(["tagall"], prefixes=["/", "@", ".", "#"]))
async def mentionall(client, message):
    chat_id = message.chat.id
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply("𝐓𝐡𝐢𝐬 𝐂𝐨𝐦𝐦𝐚𝐧𝐝 𝐎𝐧𝐥𝐲 𝐅𝐨𝐫 𝐆𝐫𝐨𝐮𝐩𝐬.")

    is_admin = False
    try:
        participant = await client.get_chat_member(chat_id, message.from_user.id)
    except UserNotParticipant:
        is_admin = False
    else:
        if participant.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ):
            is_admin = True
    if not is_admin:
        return await message.reply("𝐘𝐨𝐮 𝐀𝐫𝐞 𝐍𝐨𝐭 𝐀𝐝𝐦𝐢𝐧 𝐁𝐚𝐛𝐲, 𝐎𝐧𝐥𝐲 𝐀𝐝𝐦𝐢𝐧𝐬 𝐂𝐚𝐧 𝐓𝐚𝐠 𝐌𝐞𝐦𝐛𝐞𝐫𝐬. ")

    if message.reply_to_message and message.text:
        return await message.reply("/tagall 𝐆𝐨𝐨𝐝 𝐌𝐨𝐫𝐧𝐢𝐧𝐠 👈 𝐓𝐲𝐩𝐞 𝐋𝐢𝐤𝐞 𝐓𝐡𝐢𝐬 / 𝐑𝐞𝐩𝐥𝐲 𝐀𝐧𝐲 𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐍𝐞𝐱𝐭 𝐓𝐢𝐦𝐞 𝐅𝐨𝐭 𝐓𝐚𝐠𝐠𝐢𝐧𝐠...")
    elif message.text:
        mode = "text_on_cmd"
        msg = message.text
    elif message.reply_to_message:
        mode = "text_on_reply"
        msg = message.reply_to_message
        if not msg:
            return await message.reply("/tagall 𝐆𝐨𝐨𝐝 𝐌𝐨𝐫𝐧𝐢𝐧𝐠 👈 𝐓𝐲𝐩𝐞 𝐋𝐢𝐤𝐞 𝐓𝐡𝐢𝐬 / 𝐑𝐞𝐩𝐥𝐲 𝐀𝐧𝐲 𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐍𝐞𝐱𝐭 𝐓𝐢𝐦𝐞 𝐅𝐨𝐭 𝐓𝐚𝐠𝐠𝐢𝐧𝐠...")
    else:
        return await message.reply("/tagall 𝐆𝐨𝐨𝐝 𝐌𝐨𝐫𝐧𝐢𝐧𝐠 👈 𝐓𝐲𝐩𝐞 𝐋𝐢𝐤𝐞 𝐓𝐡𝐢𝐬 / 𝐑𝐞𝐩𝐥𝐲 𝐀𝐧𝐲 𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐍𝐞𝐱𝐭 𝐓𝐢𝐦𝐞 𝐅𝐨𝐭 𝐓𝐚𝐠𝐠𝐢𝐧𝐠...")
    if chat_id in spam_chats:
        return await message.reply("𝐏𝐥𝐞𝐚𝐬𝐞 𝐀𝐭 𝐅𝐢𝐫𝐬𝐭 𝐒𝐭𝐨𝐩 𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐌𝐞𝐧𝐭𝐢𝐨𝐧 𝐏𝐫𝐨𝐜𝐞𝐬𝐬 𝐁𝐲 /tagalloff , /stopvctag ...")
    spam_chats.append(chat_id)
    usrnum = 0
    usrtxt = ""
    async for usr in client.get_chat_members(chat_id):
        if not chat_id in spam_chats:
            break
        if usr.user.is_bot:
            continue
        usrnum += 1
        usrtxt += f"[{usr.user.first_name}](tg://user?id={usr.user.id}) "

        if usrnum == 1:
            if mode == "text_on_cmd":
                txt = f"<blockquote>{random.choice(TAGMES)}</blockquote>\n<blockquote>✰ | {usrtxt}</blockquote>"
                await client.send_message(chat_id, txt)
            elif mode == "text_on_reply":
                await msg.reply(f"[{random.choice(EMOJI)}](tg://user?id={usr.user.id})")
            await asyncio.sleep(4)
            usrnum = 0
            usrtxt = ""
    try:
        spam_chats.remove(chat_id)
    except:
        pass


@app.on_message(filters.command(["vctag"], prefixes=["/", ".", "@", "#"]))
async def mention_allvc(client, message):
    chat_id = message.chat.id
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply("𝐓𝐡𝐢𝐬 𝐂𝐨𝐦𝐦𝐚𝐧𝐝 𝐎𝐧𝐥𝐲 𝐅𝐨𝐫 𝐆𝐫𝐨𝐮𝐩𝐬.")

    is_admin = False
    try:
        participant = await client.get_chat_member(chat_id, message.from_user.id)
    except UserNotParticipant:
        is_admin = False
    else:
        if participant.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ):
            is_admin = True
    if not is_admin:
        return await message.reply("𝐘𝐨𝐮 𝐀𝐫𝐞 𝐍𝐨𝐭 𝐀𝐝𝐦𝐢𝐧 𝐁𝐚𝐛𝐲, 𝐎𝐧𝐥𝐲 𝐀𝐝𝐦𝐢𝐧𝐬 𝐂𝐚𝐧 𝐓𝐚𝐠 𝐌𝐞𝐦𝐛𝐞𝐫𝐬. ")
    if chat_id in spam_chats:
        return await message.reply("𝐏𝐥𝐞𝐚𝐬𝐞 𝐀𝐭 𝐅𝐢𝐫𝐬𝐭 𝐒𝐭𝐨𝐩 𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐌𝐞𝐧𝐭𝐢𝐨𝐧 𝐏𝐫𝐨𝐜𝐞𝐬𝐬 𝐁𝐲 /tagalloff , /stopvctag ...")
    spam_chats.append(chat_id)
    usrnum = 0
    usrtxt = ""
    async for usr in client.get_chat_members(chat_id):
        if not chat_id in spam_chats:
            break
        if usr.user.is_bot:
            continue
        usrnum += 1
        usrtxt += f"[{usr.user.first_name}](tg://user?id={usr.user.id}) "

        if usrnum == 1:
            txt = f"<blockquote>{random.choice(VC_TAG)}</blockquote>\n<blockquote>✰ | {usrtxt}</blockquote>"
            await client.send_message(chat_id, txt)
            await asyncio.sleep(2)
            usrnum = 0
            usrtxt = ""
    try:
        spam_chats.remove(chat_id)
    except:
        pass



@app.on_message(filters.command(["stoptag", "stoptagall", "canceltagall", "offtagall", "tagallstop", "stopvctag", "tagalloff", "stopvc", "stopvctag", "cancelvctag", "vctagstop", "vcstop"]))
async def cancel_spam(client, message):
    if not message.chat.id in spam_chats:
        return await message.reply("𝐂𝐮𝐫𝐫𝐞𝐧𝐭𝐥𝐲 𝐈'𝐦 𝐍𝐨𝐭 𝐓𝐚𝐠𝐠𝐢𝐧𝐠 𝐁𝐚𝐛𝐲.")
    is_admin = False
    try:
        participant = await client.get_chat_member(message.chat.id, message.from_user.id)
    except UserNotParticipant:
        is_admin = False
    else:
        if participant.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ):
            is_admin = True
    if not is_admin:
        return await message.reply("𝐘𝐨𝐮 𝐀𝐫𝐞 𝐍𝐨𝐭 𝐀𝐝𝐦𝐢𝐧 𝐁𝐚𝐛𝐲, 𝐎𝐧𝐥𝐲 𝐀𝐝𝐦𝐢𝐧𝐬 𝐂𝐚𝐧 𝐓𝐚𝐠 𝐌𝐞𝐦𝐛𝐞𝐫𝐬.")
    else:
        try:
            spam_chats.remove(message.chat.id)
        except:
            pass
        return await message.reply("♦ 𝐒𝐭𝐨𝐩𝐩𝐞𝐝..♦")
