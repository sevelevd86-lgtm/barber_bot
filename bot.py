import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime

# ---------- НАСТРОЙКИ ----------
TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"  # Замени на свой токен

# ---------- СОСТОЯНИЯ ДЛЯ РАЗГОВОРА ----------
NAME, PHONE = range(2)

# ---------- ДАННЫЕ ----------
SERVICES = {
    "стрижка": 1500,
    "борода": 1000,
    "комплекс": 2200,
}

FREE_SLOTS = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"]

# Хранилище
user_data_storage = {}  # {user_id: {"name": "...", "phone": "..."}}
bookings = {}  # {user_id: [{"service": "...", "time": "...", "date": "..."}]}

# ---------- ЛОГИРОВАНИЕ ----------
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

# ---------- ПРОВЕРКА КОНТАКТОВ ----------
def has_contacts(user_id):
    return user_id in user_data_storage and user_data_storage[user_id].get("name") and user_data_storage[user_id].get("phone")

# ---------- ОБРАБОТЧИКИ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Если контакты уже есть — сразу меню
    if has_contacts(user_id):
        await update.message.reply_text(
            f"✂️ С возвращением, {user_data_storage[user_id]['name']}!",
            reply_markup=main_menu()
        )
        return

    # Если нет — просим ввести имя
    await update.message.reply_text(
        "👋 Привет! Давай познакомимся.\n\n"
        "Как я могу к тебе обращаться? Напиши своё имя:"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()

    if len(name) < 2:
        await update.message.reply_text("Имя слишком короткое. Напиши, пожалуйста, полностью:")
        return NAME

    # Сохраняем имя в контексте
    context.user_data["temp_name"] = name

    await update.message.reply_text(
        f"Отлично, {name}! Теперь укажи номер телефона, чтобы мы могли связаться с тобой:\n\n"
        "Например: +7 (999) 123-45-67"
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    phone = update.message.text.strip()

    # Простая проверка — есть ли цифры
    if not any(ch.isdigit() for ch in phone):
        await update.message.reply_text(
            "В номере должны быть цифры. Попробуй ещё раз (например: +7 999 123-45-67):"
        )
        return PHONE

    # Сохраняем в постоянное хранилище
    user_data_storage[user_id] = {
        "name": context.user_data.get("temp_name", "Гость"),
        "phone": phone
    }

    await update.message.reply_text(
        f"✅ Спасибо, {user_data_storage[user_id]['name']}! Твой номер сохранён.\n\n"
        "Теперь ты можешь пользоваться всеми функциями бота:",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    # Если контактов нет — просим их ввести
    if data != "edit_contacts" and not has_contacts(user_id):
        await query.edit_message_text(
            "Сначала укажи свои контакты, чтобы я знал, как к тебе обращаться.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Ввести контакты", callback_data="edit_contacts")]
            ])
        )
        return

    if data == "services":
        text = "💇 **Наши услуги и цены:**\n\n"
        for service, price in SERVICES.items():
            text += f"• {service.capitalize()} — {price} ₽\n"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "contacts":
        info = user_data_storage.get(user_id, {})
        text = (
            "📞 **Контакты:**\n\n"
            f"👤 Твоё имя: {info.get('name', 'Не указано')}\n"
            f"📱 Твой телефон: {info.get('phone', 'Не указан')}\n\n"
            "📍 Адрес: ул. Примерная, д. 10\n"
            "📱 Телефон: +7 (999) 123-45-67\n"
            "📷 Instagram: @barbershop_example"
        )
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "book":
        keyboard = [[InlineKeyboardButton(service.capitalize(), callback_data=f"service_{service}")] for service in SERVICES]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        await query.edit_message_text(
            "Выбери услугу:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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
        # Очищаем старые данные и запускаем Conversation заново
        if user_id in user_data_storage:
            del user_data_storage[user_id]
        await query.edit_message_text(
            "✏️ Давай обновим твои контакты.\n\n"
            "Напиши своё имя:"
        )
        return NAME

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

    # ConversationHandler для сбора контактов
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен и работает...")
    app.run_polling()

if __name__ == "__main__":
    main()