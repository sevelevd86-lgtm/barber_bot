import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime

# ---------- НАСТРОЙКИ ----------
TOKEN = "8944409425:AAGC659vkO9fJPzBAoHOTBVP-ClS4t0UclY"  # Замени на свой токен

# ---------- СОСТОЯНИЯ ----------
CONTACT = 1

# ---------- ДАННЫЕ ----------
SERVICES = {
    "стрижка": 1500,
    "борода": 1000,
    "комплекс": 2200,
}
FREE_SLOTS = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"]

user_data_storage = {}  # {user_id: {"name": "...", "phone": "..."}}
bookings = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- КЛАВИАТУРЫ ----------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("💇 Услуги", callback_data="services")],
        [InlineKeyboardButton("📅 Записаться", callback_data="book")],
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my")],
        [InlineKeyboardButton("✏️ Изменить контакты", callback_data="edit_contacts")],
    ]
    return InlineKeyboardMarkup(keyboard)

def contact_keyboard():
    """Кнопка для отправки контакта"""
    button = KeyboardButton("📱 Отправить номер телефона", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)

def has_contacts(user_id):
    return user_id in user_data_storage and user_data_storage[user_id].get("phone")

# ---------- ОБРАБОТЧИКИ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    if has_contacts(user_id):
        await update.message.reply_text(
            f"✂️ С возвращением, {user_data_storage[user_id]['name']}!",
            reply_markup=main_menu()
        )
        return

    # Сохраняем имя из Telegram
    if user_id not in user_data_storage:
        user_data_storage[user_id] = {}
    user_data_storage[user_id]["name"] = first_name

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

    # Сохраняем телефон
    user_data_storage[user_id]["phone"] = contact.phone_number
    # Если имя не было сохранено ранее — берём из контакта
    if not user_data_storage[user_id].get("name"):
        user_data_storage[user_id]["name"] = contact.first_name or "Гость"

    await update.message.reply_text(
        f"✅ Отлично, {user_data_storage[user_id]['name']}! Твой номер сохранён.\n\n"
        "Теперь ты можешь пользоваться всеми функциями бота:",
        reply_markup=main_menu()
    )
    # Убираем клавиатуру с кнопкой контакта
    await update.message.reply_text(
        "Выбери действие:",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data != "edit_contacts" and not has_contacts(user_id):
        await query.edit_message_text(
            "Сначала укажи свои контакты, нажав кнопку ниже.",
            reply_markup=contact_keyboard()
        )
        return

    # --- Остальные обработчики кнопок (без изменений) ---
    if data == "services":
        text = "💇 **Наши услуги и цены:**\n\n"
        for service, price in SERVICES.items():
            text += f"• {service.capitalize()} — {price} ₽\n"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "contacts":
        info = user_data_storage.get(user_id, {})
        text = (
            "📞 **Твои контакты:**\n\n"
            f"👤 Имя: {info.get('name', 'Не указано')}\n"
            f"📱 Телефон: {info.get('phone', 'Не указан')}\n\n"
            "📍 Адрес барбершопа: ул. Примерная, д. 10\n"
            "📱 Телефон: +7 (999) 123-45-67\n"
            "📷 Instagram: @barbershop_example"
        )
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "book":
        keyboard = [[InlineKeyboardButton(service.capitalize(), callback_data=f"service_{service}")] for service in SERVICES]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        await query.edit_message_text("Выбери услугу:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "my":
        user_bookings = bookings.get(user_id, [])
        if not user_bookings:
            text = "📋 У тебя пока нет записей."
        else:
            text = "📋 **Твои записи:**\n\n"
            for i, b in enumerate(user_bookings, 1):
                text += f"{i}. {b['service']} — {b['date']} в {b['time']}\n"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "edit_contacts":
        if user_id in user_data_storage:
            del user_data_storage[user_id]
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
        today = datetime.now().strftime("%d.%m.%Y")
        keyboard = [[InlineKeyboardButton(slot, callback_data=f"time_{slot}")] for slot in FREE_SLOTS]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="book")])
        await query.edit_message_text(
            f"Выбрано: {service.capitalize()}\n\n"
            f"📅 Сегодня ({today})\n"
            "Выбери свободное время:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("time_"):
        time_slot = data.replace("time_", "")
        service = context.user_data.get("selected_service", "стрижка")
        date = datetime.now().strftime("%Y-%m-%d")

        if user_id not in bookings:
            bookings[user_id] = []
        bookings[user_id].append({"service": service, "time": time_slot, "date": date})

        await query.edit_message_text(
            f"✅ Запись подтверждена!\n\n"
            f"Услуга: {service.capitalize()}\n"
            f"Дата: {datetime.now().strftime('%d.%m.%Y')}\n"
            f"Время: {time_slot}\n\n"
            "Мы ждём тебя! ✂️",
            reply_markup=main_menu()
        )

# ---------- ЗАПУСК ----------
def main():
    app = Application.builder().token(TOKEN).build()

    # Conversation для контактов
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONTACT: [MessageHandler(filters.CONTACT, handle_contact)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()