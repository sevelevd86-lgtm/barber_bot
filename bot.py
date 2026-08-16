import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime, timedelta
import json
import os

# ---------- НАСТРОЙКИ ----------
TOKEN = "8944409425:AAGC659vkO9fJPzBAoHOTBVP-ClS4t0UclY"
ADMIN_PASSWORD = "Стасбар"

# ---------- СОСТОЯНИЯ ----------
CONTACT = 1

# ---------- ДАННЫЕ ----------
SERVICES = {
    "стрижка": 1500,
    "борода": 1000,
    "комплекс": 2200,
}

ALL_SLOTS = {}
for day_offset in range(7):
    date = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")
    ALL_SLOTS[date] = {
        "10:00": False, "11:00": False, "12:00": False,
        "14:00": False, "15:00": False, "16:00": False, "17:00": False
    }

users = {}
bookings = {}
booked_slots = {}

DATA_FILE = "barber_data.json"

def load_data():
    global users, bookings, booked_slots
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            users = {int(k): v for k, v in data.get("users", {}).items()}
            bookings = {int(k): v for k, v in data.get("bookings", {}).items()}
            booked_slots = data.get("booked_slots", {})

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": users, "bookings": bookings, "booked_slots": booked_slots}, f, ensure_ascii=False, indent=2)

load_data()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- КЛАВИАТУРЫ ----------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("💇 Услуги", callback_data="services")],
        [InlineKeyboardButton("📅 Записаться", callback_data="book")],
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],  # Новая кнопка
        [InlineKeyboardButton("✏️ Изменить контакты", callback_data="edit_contacts")],
    ]
    return InlineKeyboardMarkup(keyboard)

def contact_keyboard():
    button = KeyboardButton("📱 Отправить номер телефона", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)

def admin_menu():
    keyboard = [
        [InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("📅 Управление записями", callback_data="admin_bookings")],
        [InlineKeyboardButton("🔙 Выход из админки", callback_data="admin_exit")],
    ]
    return InlineKeyboardMarkup(keyboard)

def has_contacts(user_id):
    return user_id in users and users[user_id].get("phone") and users[user_id].get("contacts_given", False)

# ---------- ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    if user_id not in users:
        users[user_id] = {
            "name": first_name,
            "phone": None,
            "contacts_given": False,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_data()

    if has_contacts(user_id):
        await update.message.reply_text(
            f"✂️ С возвращением, {users[user_id]['name']}!",
            reply_markup=main_menu()
        )
        return

    await update.message.reply_text(
        f"👋 Привет, {first_name}!\n\n"
        "Чтобы я мог записывать тебя на стрижку, нажми на кнопку ниже и отправь свой номер телефона.",
        reply_markup=contact_keyboard()
    )
    return CONTACT

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact

    if not contact:
        await update.message.reply_text(
            "Пожалуйста, используй кнопку 'Отправить номер телефона'.",
            reply_markup=contact_keyboard()
        )
        return CONTACT

    users[user_id]["phone"] = contact.phone_number
    users[user_id]["contacts_given"] = True
    if not users[user_id].get("name"):
        users[user_id]["name"] = contact.first_name or "Гость"
    save_data()

    # ✅ ТЕПЕРЬ ТОЛЬКО ОДНО СООБЩЕНИЕ
    await update.message.reply_text(
        f"✅ Отлично, {users[user_id]['name']}! Твой номер сохранён.\n\n"
        "Теперь ты можешь пользоваться всеми функциями бота:",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

# ---------- ОБРАБОТЧИК ТЕКСТА ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == ADMIN_PASSWORD:
        await update.message.reply_text("🔐 Админ-панель:", reply_markup=admin_menu())

# ---------- ОБРАБОТЧИК КНОПОК ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("admin_"):
        await admin_handler(update, context)
        return

    if data != "edit_contacts" and not has_contacts(user_id):
        await query.edit_message_text(
            "Сначала укажи свои контакты, нажав кнопку ниже.",
            reply_markup=contact_keyboard()
        )
        return

    if data == "services":
        text = "💇 **Наши услуги и цены:**\n\n"
        for service, price in SERVICES.items():
            text += f"• {service.capitalize()} — {price} ₽\n"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "contacts":
        text = (
            "📞 **Связь с нами:**\n\n"
            "✂️ Telegram: @DMITROVSTAS\n"
            "📍 Адрес: ул. Примерная, д. 10\n"
            "🕐 Работаем: ежедневно с 10:00 до 21:00"
        )
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "profile":
        user_info = users.get(user_id, {})
        phone = user_info.get("phone", "Не указан")
        name = user_info.get("name", "Гость")

        user_bookings = bookings.get(user_id, [])
        if user_bookings:
            bookings_text = "\n".join([f"• {b['date']} в {b['time']} — {b['service']}" for b in user_bookings])
        else:
            bookings_text = "Нет активных записей"

        text = (
            f"👤 **Твой профиль**\n\n"
            f"Имя: {name}\n"
            f"📱 Телефон: {phone}\n\n"
            f"📋 **Твои записи:**\n{bookings_text}"
        )
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "book":
        today = datetime.now()
        keyboard = []
        for i in range(7):
            day = today + timedelta(days=i)
            date_str = day.strftime("%Y-%m-%d")
            day_label = day.strftime("%d.%m (%a)")
            keyboard.append([InlineKeyboardButton(day_label, callback_data=f"day_{date_str}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        await query.edit_message_text("📅 Выбери день для записи:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("day_"):
        date_str = data.replace("day_", "")
        context.user_data["selected_date"] = date_str
        keyboard = []
        for time_slot in ALL_SLOTS.get(date_str, {}):
            is_booked = f"{date_str}_{time_slot}" in booked_slots
            status = "❌" if is_booked else "✅"
            keyboard.append([InlineKeyboardButton(f"{time_slot} {status}", callback_data=f"slot_{date_str}_{time_slot}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="book")])
        await query.edit_message_text(
            f"📅 {datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}\nВыбери свободное время:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("slot_"):
        parts = data.split("_")
        date_str = parts[1]
        time_slot = parts[2]
        slot_key = f"{date_str}_{time_slot}"

        if slot_key in booked_slots:
            await query.edit_message_text("❌ Это время уже занято. Выбери другое.", reply_markup=main_menu())
            return

        service = context.user_data.get("selected_service", "стрижка")
        if user_id not in bookings:
            bookings[user_id] = []
        bookings[user_id].append({"service": service, "time": time_slot, "date": date_str})
        booked_slots[slot_key] = user_id
        save_data()

        await query.edit_message_text(
            f"✅ Запись подтверждена!\n\n"
            f"Услуга: {service.capitalize()}\n"
            f"Дата: {datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
            f"Время: {time_slot}\n\nМы ждём тебя! ✂️",
            reply_markup=main_menu()
        )

    elif data == "my":
        user_bookings = bookings.get(user_id, [])
        if not user_bookings:
            text = "📋 У тебя пока нет записей."
        else:
            text = "📋 **Твои записи:**\n\n"
            for i, b in enumerate(user_bookings, 1):
                date_display = datetime.strptime(b['date'], '%Y-%m-%d').strftime('%d.%m.%Y')
                text += f"{i}. {b['service']} — {date_display} в {b['time']}\n"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "edit_contacts":
        if user_id in users:
            users[user_id]["contacts_given"] = False
            users[user_id]["phone"] = None
            save_data()
        await query.edit_message_text(
            "✏️ Обновим твои контакты. Нажми кнопку ниже:",
            reply_markup=contact_keyboard()
        )
        return CONTACT

    elif data == "back":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu())

    elif data.startswith("service_"):
        service = data.replace("service_", "")
        context.user_data["selected_service"] = service
        today = datetime.now()
        keyboard = []
        for i in range(7):
            day = today + timedelta(days=i)
            date_str = day.strftime("%Y-%m-%d")
            day_label = day.strftime("%d.%m (%a)")
            keyboard.append([InlineKeyboardButton(day_label, callback_data=f"day_{date_str}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="book")])
        await query.edit_message_text(
            f"Выбрано: {service.capitalize()}\n\n📅 Выбери день:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ---------- АДМИН-ХЕНДЛЕР ----------
async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

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

    elif data == "admin_bookings":
        if not booked_slots:
            await query.edit_message_text("📅 Записей пока нет.", reply_markup=admin_menu())
            return

        text = "📅 **Все записи:**\n\n"
        for slot, uid in booked_slots.items():
            date, time = slot.split("_")
            user_info = users.get(uid, {})
            name = user_info.get("name", "Неизвестный")
            service = "стрижка"
            for b in bookings.get(uid, []):
                if b["date"] == date and b["time"] == time:
                    service = b["service"]
                    break
            date_display = datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')
            text += f"• {date_display} в {time} — {name} ({service})\n"

        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить все записи", callback_data="admin_clear_all")],
            [InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "admin_clear_all":
        booked_slots.clear()
        bookings.clear()
        save_data()
        await query.edit_message_text("✅ Все записи очищены!", reply_markup=admin_menu())

    elif data == "admin_back":
        await query.edit_message_text("Админ-панель:", reply_markup=admin_menu())

    elif data == "admin_exit":
        await query.edit_message_text("Вы вышли из админ-панели.", reply_markup=main_menu())

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