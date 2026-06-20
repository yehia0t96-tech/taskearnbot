import os
import asyncio
import json
from http.server import BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import httpx

BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID', '@gxhxd')
MINI_APP_URL = 'https://t.me/earntaskpro_bot/TaskEarn'

async def db_get(table, field, value):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}?{field}=eq.{value}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        return r.json()

async def db_insert(table, data):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json=data
        )

async def db_update(table, field, value, data):
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/{table}?{field}=eq.{value}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json=data
        )

async def check_member(bot, uid):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ['member','administrator','creator','restricted']
    except:
        return False

async def give_ref_bonus(ref_id, uid):
    if not ref_id or str(ref_id) == str(uid):
        return
    try:
        ref_data = await db_get('users', 'telegram_id', int(ref_id))
        if ref_data:
            await db_update('users', 'telegram_id', int(ref_id), {
                'coins': (ref_data[0]['coins'] or 0) + 100,
                'refs': (ref_data[0]['refs'] or 0) + 1
            })
    except:
        pass

async def get_menu_keyboard(uid):
    result = await db_get('users', 'telegram_id', uid)
    coins = result[0]['coins'] if result else 0
    refs = result[0]['refs'] if result else 0
    ads = result[0]['ads_watched'] if result else 0
    usdt = coins * 0.0001
    text = (
        f"👋 أهلاً بك في TaskEarn!\n\n"
        f"🪙 رصيدك: {coins} نقطة\n"
        f"💵 ≈ {usdt:.4f} USDT\n"
        f"👥 إحالاتك: {refs}\n"
        f"📺 إعلانات: {ads}\n\n"
        f"افتح التطبيق واكسب أكتر! 👇"
    )
    keyboard = [
        [InlineKeyboardButton("🚀 فتح التطبيق", url=MINI_APP_URL)],
        [InlineKeyboardButton(f"🪙 رصيدك: {coins} نقطة", callback_data='balance')],
        [InlineKeyboardButton("👥 رابط الإحالة", callback_data='referral'),
         InlineKeyboardButton("📊 إحصائياتك", callback_data='stats')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

async def process_update(update_data):
    app = Application.builder().token(BOT_TOKEN).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        uid = user.id
        username = user.username or ''
        ref_id = context.args[0] if context.args else None
        is_member = await check_member(context.bot, uid)
        result = await db_get('users', 'telegram_id', uid)

        if not result:
            await db_insert('users', {
                'telegram_id': uid,
                'username': username,
                'coins': 0,
                'ads_watched': 0,
                'tasks_done': 0,
                'refs': 0,
                'referred_by': str(ref_id) if ref_id else None,
                'is_member': is_member,
                'channel_bonus': False
            })
            if is_member and ref_id:
                await give_ref_bonus(ref_id, uid)
                await db_update('users', 'telegram_id', uid, {'channel_bonus': True, 'is_member': True})
        else:
            if is_member and not result[0].get('channel_bonus'):
                stored_ref = result[0].get('referred_by')
                await give_ref_bonus(stored_ref, uid)
                await db_update('users', 'telegram_id', uid, {'is_member': True, 'channel_bonus': True})

        if not is_member:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في قناة TaskEarn", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
                [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data='verify')]
            ]
            await update.message.reply_text(
                "🎯 أهلاً بك في TaskEarn Bot!\n\n"
                "💰 اكسب نقاط وحوّلها لـ USDT\n"
                "👥 100 نقطة لكل صديق تدعوه\n"
                "📺 نقاط على كل إعلان\n\n"
                "⚠️ اشترك في القناة للبدء:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            text, markup = await get_menu_keyboard(uid)
            await update.message.reply_text(text, reply_markup=markup)

    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id

        if query.data == 'verify':
            is_member = await check_member(context.bot, uid)
            if is_member:
                result = await db_get('users', 'telegram_id', uid)
                if result and not result[0].get('channel_bonus'):
                    stored_ref = result[0].get('referred_by')
                    await give_ref_bonus(stored_ref, uid)
                    await db_update('users', 'telegram_id', uid, {'is_member': True, 'channel_bonus': True})
                text, markup = await get_menu_keyboard(uid)
                await query.edit_message_text(text, reply_markup=markup)
            else:
                keyboard = [
                    [InlineKeyboardButton("📢 اشترك في قناة TaskEarn", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
                    [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data='verify')]
                ]
                await query.edit_message_text(
                    "❌ لسه مشتركتش!\n\nاشترك في القناة الأول وبعدين اضغط تحقق",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        elif query.data == 'referral':
            ref_link = f"https://t.me/earntaskpro_bot?start={uid}"
            await query.edit_message_text(
                f"👥 رابط الإحالة بتاعك:\n\n`{ref_link}`\n\n🎁 100 نقطة لكل صديق ينضم!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
            )

        elif query.data == 'balance':
            result = await db_get('users', 'telegram_id', uid)
            coins = result[0]['coins'] if result else 0
            usdt = coins * 0.0001
            await query.edit_message_text(
                f"🪙 رصيدك: {coins} نقطة\n"
                f"💵 ≈ {usdt:.4f} USDT\n\n"
                f"1000 نقطة = 0.1 USDT",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
            )

        elif query.data == 'stats':
            result = await db_get('users', 'telegram_id', uid)
            refs = result[0]['refs'] if result else 0
            ads = result[0]['ads_watched'] if result else 0
            coins = result[0]['coins'] if result else 0
            await query.edit_message_text(
                f"📊 إحصائياتك:\n\n"
                f"👥 إحالات: {refs}\n"
                f"📺 إعلانات: {ads}\n"
                f"🪙 إجمالي النقاط: {coins}\n"
                f"💰 من الإحالات: {refs*100} نقطة",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
            )

        elif query.data == 'back':
            text, markup = await get_menu_keyboard(uid)
            await query.edit_message_text(text, reply_markup=markup)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    async with app:
        update = Update.de_json(update_data, app.bot)
        await app.process_update(update)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        update_data = json.loads(body.decode())
        asyncio.run(process_update(update_data))
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'TaskEarn Bot Running!')
