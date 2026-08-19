import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime
import json
import os

# ---------- НАСТРОЙКИ ----------
TOKEN = "8944409425:AAGC659vkO9fJPzBAoHOTBVP-ClS4t0UclY"
INSTAGRAM_URL = "https://www.instagram.com/dmitrovstashair?igsh=MWdsOW9vemtzNmx1eg=="

# ---------- СОСТОЯНИЯ ----------
CONTACT = 1

# ---------- ДАННЫЕ ----------
users = {}
admins = {}

DATA_FILE = "barber_data.json"

def load_data():
    global users, admins
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            users = {int(k): v for k, v in data.get("users", {}).items()}
            admins = {int(k): v for k, v in data.get("admins", {}).items()}
    else:
        users = {}
        admins = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": users,
            "admins": admins
        }, f, ensure_ascii=False, indent=2)

load_data()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- КЛАВИАТУРЫ ----------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Предварительная запись", callback_data="contacts")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🔄 Обновить бота", callback_data="restart")],
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_menu():
    keyboard = [
        [InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("🔙 Выход из админки", callback_data="admin_exit")],
    ]
    return InlineKeyboardMarkup(keyboard)

def has_contacts(user_id):
    return user_id in users and users[user_id].get("contacts_given", False)

# ---------- ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    # Проверяем, есть ли пользователь в базе
    if user_id not in users:
        users[user_id] = {
            "name": first_name,
            "phone": None,
            "contacts_given": False,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "username": update.effective_user.username or "Не указан"
        }
        save_data()

    # Если контактов нет — запрашиваем ТОЛЬКО при первом старте
    if not has_contacts(user_id):
        # Создаём клавиатуру с кнопкой "Отправить номер"
        contact_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(
            f"👋 Привет, {first_name}!\n\n"
            "Чтобы пользоваться ботом, нажми на кнопку ниже и отправь свой номер телефона.",
            reply_markup=contact_keyboard
        )
        return CONTACT

    # Если контакты уже есть — показываем главное меню
    await update.message.reply_text(
        f"✂️ С возвращением, {users[user_id]['name']}!",
        reply_markup=main_menu()
    )
    return

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact

    if not contact:
        await update.message.reply_text(
            "Пожалуйста, используй кнопку 'Отправить номер телефона'.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        return CONTACT

    users[user_id]["phone"] = contact.phone_number
    users[user_id]["contacts_given"] = True
    if not users[user_id].get("name"):
        users[user_id]["name"] = contact.first_name or "Гость"
    save_data()

    await update.message.reply_text(
        f"✅ Отлично, {users[user_id]['name']}! Твой номер сохранён.\n\n"
        "Теперь ты можешь пользоваться ботом:",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

# ---------- ОБРАБОТЧИК ТЕКСТА ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    if text == "Стасбар":
        if user_id not in admins:
            admins[user_id] = {"sound_on": True}
            save_data()
        await update.message.reply_text(
            "🔐 Админ-панель",
            reply_markup=admin_menu()
        )

# ---------- ОБРАБОТЧИК КНОПОК ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("admin_"):
        await admin_handler(update, context)
        return

    if data == "restart":
        # Отправляем команду /start заново
        await query.edit_message_text("🔄 Перезапускаю бота...")
        # Запускаем команду /start
        await start(update, context)
        return

    if data != "contacts" and not has_contacts(user_id):
        contact_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await query.edit_message_text(
            "Сначала укажи свои контакты, нажав кнопку ниже.",
            reply_markup=contact_keyboard
        )
        return CONTACT

    if data == "contacts":
        text = (
            "📞 **Связь с нами:**\n\n"
            "✂️ Telegram: @DMITROVSTAS\n"
            f"📸 [Инстаграм]({INSTAGRAM_URL})\n"
            "🕐 Работаем: ежедневно с 10:00 до 22:00"
        )
        await query.edit_message_text(
            text,
            reply_markup=main_menu(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    elif data == "profile":
        user_info = users.get(user_id, {})
        phone = user_info.get("phone", "Не указан")
        name = user_info.get("name", "Гость")

        text = (
            f"👤 **Твой профиль**\n\n"
            f"Имя: {name}\n"
            f"📱 Телефон: {phone}"
        )
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

# ---------- АДМИН-ХЕНДЛЕР ----------
async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if data == "admin_users":
        text = "👥 **Список пользователей:**\n\n"
        with_contacts = []
        without_contacts = []

        for uid, info in users.items():
            name = info.get("name", "Без имени")
            phone = info.get("phone", "Не указан")
            if info.get("contacts_given", False):
                with_contacts.append(f"• {name} — {phone}")
            else:
                without_contacts.append(f"• {name} (ID: {uid})")

        text += "**✅ С контактами:**\n" + ("\n".join(with_contacts) if with_contacts else "Нет") + "\n\n"
        text += "**❌ Без контактов:**\n" + ("\n".join(without_contacts) if without_contacts else "Нет")

        await query.edit_message_text(text, reply_markup=admin_menu(), parse_mode="Markdown")
        return

    if data == "admin_exit":
        await query.edit_message_text("Вы вышли из админ-панели.", reply_markup=main_menu())
        context.user_data.clear()
        return

# ---------- ЗАПУСК ----------
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONTACT: [MessageHandler(filters.CONTACT, handle_contact)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()