import os
import asyncio
import json
from http.server import BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from supabase import create_client

BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID', '@gxhxd')
MINI_APP_URL = 'https://t.me/earntaskpro_bot/TaskEarn'

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
bot_app = Application.builder().token(BOT_TOKEN).build()

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

    result = supabase.table('users').select('*').eq('telegram_id', uid).execute()

    if not result.data:
        supabase.table('users').insert({
            'telegram_id': uid,
            'username': username,
            'coins': 0,
            'ads_watched': 0,
            'tasks_done': 0,
            'refs': 0,
            'referred_by': ref_id,
            'is_member': is_member
        }).execute()

        if ref_id and ref_id != str(uid) and is_member:
            ref_result = supabase.table('users').select('*').eq('telegram_id', int(ref_id)).execute()
            if ref_result.data:
                supabase.table('users').update({
                    'coins': (ref_result.data[0]['coins'] or 0) + 100,
                    'refs': (ref_result.data[0]['refs'] or 0) + 1
                }).eq('telegram_id', int(ref_id)).execute()

    if not is_member:
        keyboard = [
            [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
            [InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data='verify')]
        ]
        await update.message.reply_text(
            "⚠️ لازم تشترك في القناة الأول!\n\n"
            "1️⃣ اشترك في القناة\n"
            "2️⃣ ارجع هنا واضغط تحققت",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await show_menu(update.message, uid)

async def show_menu(message, uid):
    result = supabase.table('users').select('*').eq('telegram_id', uid).execute()
    coins = result.data[0]['coins'] if result.data else 0
    refs = result.data[0]['refs'] if result.data else 0
    keyboard = [
        [InlineKeyboardButton("🚀 فتح التطبيق", url=MINI_APP_URL)],
        [InlineKeyboardButton(f"🪙 رصيدك: {coins} نقطة", callback_data='balance')],
        [InlineKeyboardButton("👥 رابط الإحالة", callback_data='referral')],
        [InlineKeyboardButton("📊 إحصائياتك", callback_data='stats')]
    ]
    await message.reply_text(
        f"👋 أهلاً!\n\n"
        f"🪙 رصيدك: {coins} نقطة\n"
        f"👥 إحالاتك: {refs}\n\n"
        f"افتح التطبيق واكسب! 👇",
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
            result = supabase.table('users').select('*').eq('telegram_id', uid).execute()
            if result.data and not result.data[0].get('is_member'):
                ref_id = result.data[0].get('referred_by')
                supabase.table('users').update({'is_member': True}).eq('telegram_id', uid).execute()
                if ref_id:
                    ref_result = supabase.table('users').select('*').eq('telegram_id', int(ref_id)).execute()
                    if ref_result.data:
                        supabase.table('users').update({
                            'coins': (ref_result.data[0]['coins'] or 0) + 100,
                            'refs': (ref_result.data[0]['refs'] or 0) + 1
                        }).eq('telegram_id', int(ref_id)).execute()

            result = supabase.table('users').select('*').eq('telegram_id', uid).execute()
            coins = result.data[0]['coins'] if result.data else 0
            refs = result.data[0]['refs'] if result.data else 0
            keyboard = [
                [InlineKeyboardButton("🚀 فتح التطبيق", url=MINI_APP_URL)],
                [InlineKeyboardButton(f"🪙 رصيدك: {coins} نقطة", callback_data='balance')],
                [InlineKeyboardButton("👥 رابط الإحالة", callback_data='referral')],
                [InlineKeyboardButton("📊 إحصائياتك", callback_data='stats')]
            ]
            await query.edit_message_text(
                f"✅ تم التحقق! أهلاً بك!\n\n"
                f"🪙 رصيدك: {coins} نقطة\n"
                f"👥 إحالاتك: {refs}\n\n"
                f"افتح التطبيق! 👇",
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
            f"👥 رابط الإحالة بتاعك:\n\n`{ref_link}`\n\n🎁 100 نقطة لكل صديق ينضم!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    elif query.data == 'balance':
        result = supabase.table('users').select('*').eq('telegram_id', uid).execute()
        coins = result.data[0]['coins'] if result.data else 0
        await query.edit_message_text(
            f"🪙 رصيدك: {coins} نقطة\n💵 ≈ {coins*0.0001:.4f} USDT\n\n1000 نقطة = 0.1 USDT",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    elif query.data == 'stats':
        result = supabase.table('users').select('*').eq('telegram_id', uid).execute()
        refs = result.data[0]['refs'] if result.data else 0
        ads = result.data[0]['ads_watched'] if result.data else 0
        await query.edit_message_text(
            f"📊 إحصائياتك:\n\n👥 إحالات: {refs}\n📺 إعلانات: {ads}\n💰 من الإحالات: {refs*100} نقطة",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    elif query.data == 'back':
        result = supabase.table('users').select('*').eq('telegram_id', uid).execute()
        coins = result.data[0]['coins'] if result.data else 0
        refs = result.data[0]['refs'] if result.data else 0
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

bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(button_handler))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        update = Update.de_json(json.loads(body.decode()), bot_app.bot)
        asyncio.run(bot_app.process_update(update))
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'TaskEarn Bot Running!')
