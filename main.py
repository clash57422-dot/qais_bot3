import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
import time
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- 1. سيرفر وهمي لإرضاء Render وتفعيل Web Service مجاناً ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"QAIS STORE Bot is Live and Running!")


def run_dummy_server():
  port = int(os.environ.get("PORT", 8080))
  server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
  server.serve_forever()


threading.Thread(target=run_dummy_server, daemon=True).start()

# --- 2. البيانات الأساسية والإعدادات ---
BOT_TOKEN = "8712058483:AAEajZ57ooCtTTCibNuuN2zOSfdy3u969rE"
ADMIN_CHAT_ID = 8556501768  # ايديك الخاص كآدمن

BINANCE_PAY_ID = "1006208970"
USDT_WALLET = "0x409239a2a633f0627366f701c4ee3c2d5a9dac2a"

BINANCE_API_KEY = (
    "Al7fywuuad77sluatuiq60kwv6k9p2rf4nuh7vgxiuboilntmwnlzt2nbfmlgprh"
)
BINANCE_SECRET_KEY = (
    "wahitoge75wxgfss40o7p2hapkgwupelca65n3snr4qdou4rnep4xlaprlhzb8ab"
)

# قائمة المنتجات القابلة للتعديل ديناميكياً من الآدمن
products_db = {
    "APKMOD": {"name": "تطبيقات APKMOD", "price": 5.0},
    "IOS": {"name": "تطبيقات IOS", "price": 10.0},
    "ROOT": {"name": "خدمات ROOT", "price": 15.0},
}

# رسائل الترحيب القابلة للتعديل
welcome_messages = {
    "ar": "👋 **أهلاً بك في QAIS STORE!**\n⭐ متجر الخدمات والتطبيقات المعدلة الممتازة\n⚡ تحقق وإيداع آلي 24/7",
    "en": "👋 **Welcome to QAIS STORE!**\n⭐ Premium Game Keys & Mod Tools\n⚡ Instant Verification 24/7",
}

user_balances = {}
user_data = {}
used_txids = set()


# --- 3. الدعم الفني والربط مع بايننس ---
def check_binance_deposit(tx_id):
  url = "https://api.binance.com/sapi/v1/capital/deposit/hisrec"
  timestamp = int(time.time() * 1000)
  query_string = f"timestamp={timestamp}"

  signature = hmac.new(
      BINANCE_SECRET_KEY.encode("utf-8"),
      query_string.encode("utf-8"),
      hashlib.sha256,
  ).hexdigest()

  headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
  full_url = f"{url}?{query_string}&signature={signature}"

  try:
    response = requests.get(full_url, headers=headers, timeout=10)
    if response.status_code == 200:
      deposits = response.json()
      for deposit in deposits:
        if deposit.get("txId") == tx_id and deposit.get("status") == 1:
          return float(deposit.get("amount", 0))
    return None
  except Exception as e:
    print(f"Binance API Error: {e}")
    return None


def is_valid_amount(amount):
  return amount == 1.0 or (amount >= 5.0 and amount % 5.0 == 0)


def build_main_menu(lang, balance, user_id):
  welcome_txt = welcome_messages.get(lang, welcome_messages["ar"])

  if lang == "en":
    text = (
        f"🤖 **─── QAIS Gaming Store ───**\n\n"
        f"{welcome_txt}\n\n"
        f"🆔 Your ID: `{user_id}`\n"
        f"💰 Balance: **${balance:.2f}**"
    )
    keyboard = [
        [InlineKeyboardButton("💎 Shop Now", callback_data="store")],
        [
            InlineKeyboardButton("📜 My Orders", callback_data="my_orders"),
            InlineKeyboardButton("👑 Profile", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("💳 Add Balance", callback_data="deposit"),
            InlineKeyboardButton("🤝 Referral", callback_data="referral"),
        ],
        [InlineKeyboardButton("📁 Downloads", callback_data="downloads")],
        [InlineKeyboardButton("📖 How to Use", callback_data="how_to")],
        [InlineKeyboardButton("💬 Support", callback_data="support")],
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        ],
    ]
  else:
    text = (
        f"🤖 **─── متجر قيس للخدمات ───**\n\n"
        f"{welcome_txt}\n\n"
        f"🆔 معرّفك الخاص: `{user_id}`\n"
        f"💰 رصيدك الحالي: **${balance:.2f}**"
    )
    keyboard = [
        [InlineKeyboardButton("💎 الشراء الآن", callback_data="store")],
        [
            InlineKeyboardButton("📜 طلباتي", callback_data="my_orders"),
            InlineKeyboardButton("👑 الحساب الشخصي", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("💳 إيداع رصيد", callback_data="deposit"),
            InlineKeyboardButton("🤝 الإحالة", callback_data="referral"),
        ],
        [InlineKeyboardButton("📁 تحميل الملفات", callback_data="downloads")],
        [InlineKeyboardButton("📖 طريقة الاستخدام", callback_data="how_to")],
        [InlineKeyboardButton("💬 الدعم الفني", callback_data="support")],
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        ],
    ]

  return text, InlineKeyboardMarkup(keyboard)


# --- 4. معالجة الأوامر الرئيسية والتفاعل ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  user_id = user.id

  if user_id not in user_balances:
    user_balances[user_id] = 0.0

  # سؤال المستخدم عن اللغة أولاً إذا كانت هذه زيارته الأولى
  if user_id not in user_data or "lang" not in user_data[user_id]:
    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data="init_lang_ar"),
            InlineKeyboardButton("🇬🇧 English", callback_data="init_lang_en"),
        ]
    ]
    await update.message.reply_text(
        "👋 **مرحباً بك! اختر اللّغة للبدء / Welcome! Select your language to"
        " start:**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return

  lang = user_data[user_id].get("lang", "ar")
  balance = user_balances[user_id]

  text, reply_markup = build_main_menu(lang, balance, user_id)
  await update.message.reply_text(
      text, parse_mode="Markdown", reply_markup=reply_markup
  )


# --- 5. أوامر لوحة تحكم الآدمن ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_user.id != ADMIN_CHAT_ID:
    return

  msg = (
      "👑 **لوحة تحكم الآدمن (قيس):**\n\n"
      "🔹 **تعديل سعر منتج:**\n`/setprice [رمز_المنتج] [السعر_الجديد]`\nمثال:"
      " `/setprice APKMOD 7.5`\n\n"
      "🔹 **إضافة منتج جديد:**\n`/addproduct [الرمز] [الاسم] [السعر]`\nمثال:"
      " `/addproduct VIP جواهر_فراير 10`\n\n"
      "🔹 **تعديل الترحيب العربي:**\n`/setwelcome [النص]`\n\n"
      "📦 **المنتجات الحالية:**\n"
  )
  for code, item in products_db.items():
    msg += f"• `{code}`: {item['name']} - **${item['price']}**\n"

  await update.message.reply_text(msg, parse_mode="Markdown")


async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_user.id != ADMIN_CHAT_ID:
    return
  try:
    code = context.args[0].upper()
    new_price = float(context.args[1])
    if code in products_db:
      products_db[code]["price"] = new_price
      await update.message.reply_text(
          f"✅ تم تحديث سعر `{code}` إلى **${new_price:.2f}** بنجاح!"
      )
    else:
      await update.message.reply_text("❌ هذا المنتج غير موجود!")
  except Exception:
    await update.message.reply_text(
        "⚠️ الاستخدام الخاطئ! الصيغة الصحيحة:\n`/setprice APKMOD 8.0`",
        parse_mode="Markdown",
    )


async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_user.id != ADMIN_CHAT_ID:
    return
  try:
    code = context.args[0].upper()
    name = context.args[1].replace("_", " ")
    price = float(context.args[2])
    products_db[code] = {"name": name, "price": price}
    await update.message.reply_text(
        f"🎉 تم إضافة المنتج الجديد `{code}` ({name}) بسعر **${price:.2f}**!"
    )
  except Exception:
    await update.message.reply_text(
        "⚠️ الاستخدام الخاطئ! الصيغة الصحيحة:\n`/addproduct VIP جواهر_فري_فاير"
        " 10.0`",
        parse_mode="Markdown",
    )


async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_user.id != ADMIN_CHAT_ID:
    return
  new_text = " ".join(context.args)
  if new_text:
    welcome_messages["ar"] = new_text
    await update.message.reply_text("✅ تم تحديث رسالة الترحيب بنجاح!")
  else:
    await update.message.reply_text("⚠️ اكتب نص الترحيب الجديد بعد الأمر!")


# --- 6. معالج الأزرار والقوائم ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  user = query.from_user
  user_id = user.id

  if user_id not in user_balances:
    user_balances[user_id] = 0.0

  user_data.setdefault(user_id, {})

  # اختيار اللغة البدائي
  if query.data.startswith("init_lang_"):
    lang = query.data.split("_")[2]
    user_data[user_id]["lang"] = lang
    text, reply_markup = build_main_menu(lang, user_balances[user_id], user_id)
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=reply_markup
    )
    return

  lang = user_data[user_id].get("lang", "ar")

  if query.data.startswith("lang_"):
    lang = query.data.split("_")[1]
    user_data[user_id]["lang"] = lang
    text, reply_markup = build_main_menu(lang, user_balances[user_id], user_id)
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=reply_markup
    )

  elif query.data == "store":
    keyboard = []
    for code, item in products_db.items():
      btn_text = f"📱 {item['name']} - ${item['price']:.2f}"
      keyboard.append(
          [InlineKeyboardButton(btn_text, callback_data=f"prod_{code}")]
      )
    keyboard.append([
        InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")
    ])

    await query.edit_message_text(
        "🛍️ **اختر الخدمة أو المنتج المطلوبة:**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  elif query.data.startswith("prod_"):
    code = query.data.split("_")[1]
    item = products_db.get(code)
    if not item:
      await query.edit_message_text("❌ هاد المنتج غير متوفر حالياً.")
      return

    price = item["price"]
    current_balance = user_balances[user_id]

    if current_balance < price:
      await query.edit_message_text(
          f"❌ رصيدك غير كافٍ!\nرصيدك الحالي: **${current_balance:.2f}**\nسعر"
          f" الخدمة: **${price:.2f}**",
          parse_mode="Markdown",
          reply_markup=InlineKeyboardMarkup([[
              InlineKeyboardButton(
                  "💳 إيداع رصيد الآن", callback_data="deposit"
              )
          ]]),
      )
    else:
      user_data[user_id]["buying_product"] = code
      user_data[user_id]["state"] = "WAITING_EMAIL"
      await query.edit_message_text(
          f"🛒 اخترت: **{item['name']}** بسعر **${price:.2f}**\n\n📧 أرسل بريدك"
          " الإلكتروني الآن لتسليم طلبك:"
      )

  elif query.data == "deposit":
    user_data[user_id]["state"] = "WAITING_TXID"
    msg = (
        "💳 **── قسم إيداع الرصيد ──**\n\n"
        f"• **Binance Pay ID:** `{BINANCE_PAY_ID}`\n"
        f"• **USDT (BEP20):** `{USDT_WALLET}`\n\n"
        "أرسل **رمز الحوالة (TxID)** هنا للتحقق التلقائي:"
    )
    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 العودة للقائمة", callback_data="main_menu"
            )
        ]
    ]
    await query.edit_message_text(
        msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

  elif query.data == "profile":
    msg = (
        "👑 **── الحساب الشخصي ──**\n\n"
        f"👤 المستخدم: @{user.username or 'غير معرف'}\n"
        f"🆔 ID الخاص بك: `{user_id}`\n"
        f"💰 الرصيد الحالي: **${user_balances[user_id]:.2f}**"
    )
    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 العودة للقائمة", callback_data="main_menu"
            )
        ]
    ]
    await query.edit_message_text(
        msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

  elif query.data in [
      "my_orders",
      "referral",
      "downloads",
      "how_to",
      "support",
  ]:
    messages = {
        "my_orders": "📜 لا يوجد لديك طلبات سابقة حالياً.",
        "referral": "🤝 نظام الإحالة قيد التطوير!",
        "downloads": "📁 لا توجد ملفات جاهزة للتحميل حالياً.",
        "how_to": (
            "📖 **طريقة الاستخدام:**\n1. اشحن محفظتك بـ USDT.\n2. اختر الخدمة"
            " من المتجر.\n3. أرسل إيميلك واستلم الخدمة."
        ),
        "support": "💬 للتواصل مع الدعم الفني: @qies111",
    }
    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 العودة للقائمة", callback_data="main_menu"
            )
        ]
    ]
    await query.edit_message_text(
        messages[query.data],
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  elif query.data == "main_menu":
    user_data[user_id]["state"] = None
    text, reply_markup = build_main_menu(lang, user_balances[user_id], user_id)
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=reply_markup
    )


# --- 7. معالجة الرسائل العادية والطلبات ---
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  user_id = user.id
  text = update.message.text.strip()
  state = user_data.get(user_id, {}).get("state")

  if state == "WAITING_TXID":
    txid = text
    if txid in used_txids:
      await update.message.reply_text("⚠️ رمز الحوالة (TxID) مستخدم سابقاً!")
      return

    await update.message.reply_text(
        "⏳ جاري الفحص والتحقق التلقائي مع بايننس..."
    )
    amount = check_binance_deposit(txid)

    if amount is not None:
      if is_valid_amount(amount):
        used_txids.add(txid)
        user_balances[user_id] = user_balances.get(user_id, 0.0) + amount
        user_data[user_id]["state"] = None

        await update.message.reply_text(
            f"🎉 **تم شحن الرصيد بنجاح!**\nتم إضافة: **${amount:.2f}**\nرصيدك"
            f" الجديد: **${user_balances[user_id]:.2f}**",
            parse_mode="Markdown",
        )

        admin_msg = (
            f"✅ **إيداع آلي جديد!**\n👤 العميل: @{user.username or user_id}\n🆔"
            f" العميل: `{user_id}`\n💳 المبلغ: ${amount}\n🔗 TxID: `{txid}`"
        )
        await context.bot.send_message(
            ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown"
        )
      else:
        await update.message.reply_text(
            "❌ المبلغ المحول غير مسموح به! يجب أن يكون إما 1$ أو من مضاعفات"
            " الـ 5."
        )
    else:
      await update.message.reply_text(
          "❌ لم نتمكن من التأكد من العملية في بايننس. يرجى التأكد وإعادة"
          " المحاولة."
      )

  elif state == "WAITING_EMAIL":
    if "@" in text and "." in text:
      email = text
      code = user_data[user_id].get("buying_product")
      item = products_db.get(code, {})
      price = item.get("price", 0)

      user_balances[user_id] -= price
      user_data[user_id]["state"] = None

      await update.message.reply_text(
          f"✅ تم خصم **${price:.2f}** من رصيدك بنجاح.\nالخدمة:"
          f" {item.get('name')}\nالإيميل: `{email}`\nسيتم التسليم قريباً!"
      )

      admin_msg = (
          f"📦 **طلب جديد!**\n👤 العميل: @{user.username or user_id}\n🆔 العميل:"
          f" `{user_id}`\n🛒 الخدمة: {item.get('name')}\n📧 الإيميل للنسخ:"
          f" `{email}`"
      )
      await context.bot.send_message(
          ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown"
      )
    else:
      await update.message.reply_text("⚠️ البريد الإلكتروني غير صحيح!")


# --- 8. تشغيل التطبيق واضافة الهاندلرز ---
if __name__ == "__main__":
  app = ApplicationBuilder().token(BOT_TOKEN).build()

  # أوامر المستخدم والآدمن
  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("admin", admin_panel))
  app.add_handler(CommandHandler("setprice", set_price))
  app.add_handler(CommandHandler("addproduct", add_product))
  app.add_handler(CommandHandler("setwelcome", set_welcome))

  # التفاعلات والرسائل
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(
      MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
  )

  print("Bot is running...")
  app.run_polling()
