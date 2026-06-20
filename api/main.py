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

async def process_update(update_data):
    app = Application.builder().token(BOT_TOKEN).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        uid = user.id
        username = user.username or ''
        ref_id = context.args[0] if context.args else None
        try:
            member = await context.bot.get_chat_member(CHANNEL_ID, uid)
            is_member = member.status in ['member','administrator','creator']
        except:
            is_member = False
        result = await db_get('users', 'telegram_id', uid)
        if not result:
            await db_insert('users', {
                'telegram_id': uid,
                'username': username,
                'coins': 0,
                'ads_watched': 0,
                'tasks_done': 0,
                'refs': 0,
                'referred_by': ref_id,
                'is_member': is_member
            })
            if ref_id and ref_id != str(uid) and is_member:
                ref_data = await db_get('users', 'telegram_id', ref_id)
                if ref_data:
                    await db_update('users', 'telegram_id', ref_id, {
                        'coins': (ref_data[0]['coins'] or 0) + 100,
                        'refs': (ref_data[0]['refs'] or 0) + 1
                    })
        if not is_member:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
                [InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data='verify')]
            ]
            await update.message.reply_text(
                "⚠️ لازم تشترك في القناة الأول!\n\n1️⃣ اشترك\n2️⃣ ارجع واضغط تحققت",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            result = await db_get('users', 'telegram_id', uid)
            coins = result[0]['coins'] if result else 0
            refs = result[0]['refs'] if result else 0
            keyboard = [
                [InlineKeyboardButton("🚀 فتح التطبيق", url=MINI_APP_URL)],
                [InlineKeyboardButton(f"🪙 رصيدك: {coins} نقطة", callback_data='balance')],
                [InlineKeyboardButton("👥 رابط الإحالة", callback_data='referral')],
                [InlineKeyboardButton("📊 إحصائياتك", callback_data='stats')]
            ]
            await update.message.reply_text(
                f"👋 أهلاً!\n\n🪙 رصيدك: {coins} نقطة\n👥 إحالاتك: {refs}\n\nافتح التطبيق! 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id
        if query.data == 'verify':
            try:
                member = await context.bot.get_chat_member(CHANNEL_ID, uid)
                is_member = member.status in ['member','administrator','creator']
            except:
                is_member = False
            if is_member:
                result = await db_get('users', 'telegram_id', uid)
                if result and not result[0].get('is_member'):
                    ref_id = result[0].get('referred_by')
                    await db_update('users', 'telegram_id', uid, {'is_member': True})
                    if ref_id:
                        ref_data = await db_get('users', 'telegram_id', ref_id)
                        if ref_data:
                            await db_update('users', 'telegram_id', ref_id, {
                                'coins': (ref_data[0]['coins'] or 0) + 100,
                                'refs': (ref_data[0]['refs'] or 0) + 1
                            })
                result = await db_get('users', 'telegram_id', uid)
                coins = result[0]['coins'] if result else 0
                refs = result[0]['refs'] if result else 0
                keyboard = [
                    [InlineKeyboardButton("🚀 فتح التطبيق", url=MINI_APP_URL)],
                    [InlineKeyboardButton(f"🪙 رصيدك: {coins} نقطة", callback_data='balance')],
                    [InlineKeyboardButton("👥 رابط الإحالة", callback_data='referral')],
                    [InlineKeyboardButton("📊 إحصائياتك", callback_data='stats')]
                ]
                await query.edit_message_text(
                    f"✅ تم التحقق!\n\n🪙 رصيدك: {coins} نقطة\n👥 إحالاتك: {refs}\n\nافتح التطبيق! 👇",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(
                    "❌ لسه مشتركتش!\n\nاشترك الأول وارجع اضغط تحققت",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
                        [InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data='verify')]
                    ])
                )
        elif query.data == 'referral':
            ref_link = f"https://t.me/earntaskpro_bot?start={uid}"
            await query.edit_message_text(
                f"👥 رابط الإحالة:\n\n`{ref_link}`\n\n🎁 100 نقطة لكل صديق!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
            )
        elif query.data == 'balance':
            result = await db_get('users', 'telegram_id', uid)
            coins = result[0]['coins'] if result else 0
            await query.edit_message_text(
                f"🪙 رصيدك: {coins} نقطة\n💵 ≈ {coins*0.0001:.4f} USDT",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
            )
        elif query.data == 'stats':
            result = await db_get('users', 'telegram_id', uid)
            refs = result[0]['refs'] if result else 0
            ads = result[0]['ads_watched'] if result else 0
            await query.edit_message_text(
                f"📊 إحصائياتك:\n\n👥 إحالات: {refs}\n📺 إعلانات: {ads}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
            )
        elif query.data == 'back':
            result = await db_get('users', 'telegram_id', uid)
            coins = result[0]['coins'] if result else 0
            refs = result[0]['refs'] if result else 0
            keyboard = [
                [InlineKeyboardButton("🚀 فتح التطبيق", url=MINI_APP_URL)],
                [InlineKeyboardButton(f"🪙 رصيدك: {coins} نقطة", callback_data='balance')],
                [InlineKeyboardButton("👥 رابط الإحالة", callback_data='referral')],
                [InlineKeyboardButton("📊 إحصائياتك", callback_data='stats')]
            ]
            await query.edit_message_text(
                f"👋 أهلاً!\n\n🪙 رصيدك: {coins} نقطة\n👥 إحالاتك: {refs}\n\nافتح التطبيق! 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

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
