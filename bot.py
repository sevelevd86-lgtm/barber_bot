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
PREBOOK_SETUP = 2

# ---------- ДАННЫЕ ----------
users = {}
bookings = {}
booked_slots = {}
prebook_settings = {}  # {date: {"10:00": False, "11:00": False, ...}} - глобальные настройки

DATA_FILE = "barber_data.json"

def load_data():
    global users, bookings, booked_slots, prebook_settings
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            users = {int(k): v for k, v in data.get("users", {}).items()}
            bookings = {int(k): v for k, v in data.get("bookings", {}).items()}
            booked_slots = data.get("booked_slots", {})
            prebook_settings = data.get("prebook_settings", {})

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": users,
            "bookings": bookings,
            "booked_slots": booked_slots,
            "prebook_settings": prebook_settings
        }, f, ensure_ascii=False, indent=2)

load_data()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- КЛАВИАТУРЫ ----------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("📅 Предварительная запись", callback_data="prebook")],
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
        [InlineKeyboardButton("⚙️ Настройка предзаписи", callback_data="admin_prebook_setup")],
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
        "Чтобы пользоваться ботом, нажми на кнопку ниже и отправь свой номер телефона.",
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

    await update.message.reply_text(
        f"✅ Отлично, {users[user_id]['name']}! Твой номер сохранён.\n\n"
        "Теперь ты можешь пользоваться ботом:",
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

    if data == "contacts":
        text = (
            "📞 **Связь с нами:**\n\n"
            "📍 Ленинградский просп. 38А, корп. 1\n"
            "✂️ Chop X Chop\n"
            "✂️ Telegram: @DMITROVSTAS\n"
            "🕐 Работаем: ежедневно с 10:00 до 22:00"
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

    elif data == "prebook":
        # Показываем пустую предзапись
        text = "📅 **Предварительная запись**\n\n"
        text += "Здесь ты можешь посмотреть доступные даты и время для записи.\n"
        text += "Но пока ничего нет. Загляни позже!"

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

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

    elif data == "admin_prebook_setup":
        # Показываем список месяцев
        keyboard = []
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        for month in months:
            keyboard.append([InlineKeyboardButton(month, callback_data=f"admin_month_{month}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
        await query.edit_message_text("📅 Выбери месяц для настройки:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_month_"):
        month = data.replace("admin_month_", "")
        context.user_data["admin_month"] = month
        # Показываем дни месяца (30-31)
        days = 31
        if month in ["Апрель", "Июнь", "Сентябрь", "Ноябрь"]:
            days = 30
        elif month == "Февраль":
            days = 28  # упрощённо, без високосных годов

        keyboard = []
        for day in range(1, days + 1):
            keyboard.append([InlineKeyboardButton(f"{day} {month}", callback_data=f"admin_day_{month}_{day}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_prebook_setup")])
        await query.edit_message_text(f"📅 Выбери день в {month}:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_day_"):
        parts = data.split("_")
        month = parts[2]
        day = parts[3]
        date_key = f"{day}_{month}"
        context.user_data["admin_date"] = date_key

        # Показываем часы с 10:00 до 22:00
        keyboard = []
        for hour in range(10, 23):
            time_slot = f"{hour:02d}:00"
            # Проверяем, занят ли этот слот
            is_booked = f"{date_key}_{time_slot}" in booked_slots
            status = "❌" if is_booked else "✅"
            keyboard.append([InlineKeyboardButton(f"{time_slot} {status}", callback_data=f"admin_time_{date_key}_{time_slot}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"admin_month_{month}")])
        await query.edit_message_text(f"📅 {day} {month}\nВыбери время для настройки:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_time_"):
        parts = data.replace("admin_time_", "").split("_")
        # Формат: date_key_time
        date_key = parts[0] + "_" + parts[1]  # день_месяц
        time_slot = parts[2] + ":" + parts[3]  # час:00
        slot_key = f"{date_key}_{time_slot}"

        if slot_key in booked_slots:
            # Если уже занято - разблокируем
            del booked_slots[slot_key]
            # Удаляем запись из bookings
            for uid, user_bookings in bookings.items():
                bookings[uid] = [b for b in user_bookings if f"{b['date']}_{b['time']}" != slot_key]
            save_data()
            await query.edit_message_text(f"✅ Время {time_slot} разблокировано!", reply_markup=admin_menu())
        else:
            # Если свободно - блокируем (имитация записи)
            # Создаём фейковую запись для админа
            admin_id = update.effective_user.id
            if admin_id not in bookings:
                bookings[admin_id] = []
            bookings[admin_id].append({
                "service": "админ-блокировка",
                "time": time_slot,
                "date": date_key
            })
            booked_slots[slot_key] = admin_id
            save_data()
            await query.edit_message_text(f"✅ Время {time_slot} заблокировано!", reply_markup=admin_menu())

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