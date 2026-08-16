import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from datetime import datetime, timedelta

# ---------- НАСТРОЙКИ ----------
TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"  # Замени на свой токен

# ---------- ДАННЫЕ ----------
SERVICES = {
    "стрижка": 1500,
    "борода": 1000,
    "комплекс": 2200,
}

# Свободное время (захардкожено для примера)
FREE_SLOTS = [
    "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"
]

# Хранилище записей (в памяти) — для простоты
bookings = {}  # {user_id: [{"service": "стрижка", "time": "10:00", "date": "2026-08-16"}]

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
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------- ОБРАБОТЧИКИ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и главное меню"""
    user = update.effective_user
    await update.message.reply_text(
        f"✂️ Привет, {user.first_name}! Добро пожаловать в наш барбершоп.\n\n"
        "Здесь ты можешь:\n"
        "✅ Посмотреть услуги\n"
        "✅ Записаться на стрижку\n"
        "✅ Узнать контакты\n"
        "✅ Посмотреть свои записи\n\n"
        "Выбери действие:",
        reply_markup=main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "services":
        text = "💇 **Наши услуги и цены:**\n\n"
        for service, price in SERVICES.items():
            text += f"• {service.capitalize()} — {price} ₽\n"
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "contacts":
        text = (
            "📞 **Контакты:**\n\n"
            "📍 Адрес: ул. Примерная, д. 10\n"
            "📱 Телефон: +7 (999) 123-45-67\n"
            "📷 Instagram: @barbershop_example\n"
            "🕐 Работаем: ежедневно с 10:00 до 21:00"
        )
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "book":
        # Показываем услуги для выбора
        keyboard = []
        for service in SERVICES:
            keyboard.append([InlineKeyboardButton(service.capitalize(), callback_data=f"service_{service}")])
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

    elif data == "back":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu())

    elif data.startswith("service_"):
        service = data.replace("service_", "")
        context.user_data["selected_service"] = service
        # Показываем свободное время на сегодня
        today = datetime.now().strftime("%d.%m.%Y")
        keyboard = []
        for slot in FREE_SLOTS:
            keyboard.append([InlineKeyboardButton(slot, callback_data=f"time_{slot}")])
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

        # Сохраняем запись
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен и работает...")
    app.run_polling()

if __name__ == "__main__":
    main()