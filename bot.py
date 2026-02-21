import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from datetime import datetime
from config import (
    BOT_TOKEN, MAX_PHOTOS_PER_ENTRY, LOG_LEVEL, LOG_FORMAT, DEBUG
)
from database import db
from utils import create_excel_export, format_entry_preview, validate_photo

# Настройка логирования
logging.basicConfig(format=LOG_FORMAT, level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

# Состояния пользователей
class UserState:
    MAIN = 0
    ENTER_NAME = 1
    ENTER_DESCRIPTION = 2
    UPLOAD_PHOTO = 3

# Хранилище временных данных
temp_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    context.user_data['state'] = UserState.MAIN
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить запись", callback_data='add')],
        [InlineKeyboardButton("📊 Мои записи", callback_data='view')],
        [InlineKeyboardButton("📥 Экспорт в Excel", callback_data='export')],
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Добро пожаловать! Выберите действие:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🤖 *Справка*\n\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n"
        "/cancel - Отмена\n\n"
        "*Как пользоваться:*\n"
        "1️⃣ Нажмите 'Добавить запись'\n"
        "2️⃣ Введите название\n"
        "3️⃣ Введите описание\n"
        "4️⃣ Загрузите фото (до 5 шт.)\n"
        "5️⃣ Нажмите 'Готово'"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    user_id = update.effective_user.id
    context.user_data.clear()
    if user_id in temp_data:
        del temp_data[user_id]
    
    await update.message.reply_text("❌ Действие отменено. Используйте /start")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == 'add':
        context.user_data['state'] = UserState.ENTER_NAME
        temp_data[user_id] = {'photos': []}
        await query.edit_message_text("📝 Введите название записи:")
    
    elif query.data == 'view':
        await show_entries(query, context)
    
    elif query.data == 'export':
        await export_entries(query, context)
    
    elif query.data == 'stats':
        stats = db.get_stats()
        text = (
            "📊 *Статистика*\n\n"
            f"👥 Пользователей: {stats['total_users']}\n"
            f"📝 Записей: {stats['total_entries']}\n"
            f"📸 Фото: {stats['total_photos']}"
        )
        await query.edit_message_text(text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    state = context.user_data.get('state')
    text = update.message.text
    
    if state == UserState.ENTER_NAME:
        temp_data[user_id]['name'] = text
        context.user_data['state'] = UserState.ENTER_DESCRIPTION
        await update.message.reply_text("📋 Введите описание:")
    
    elif state == UserState.ENTER_DESCRIPTION:
        temp_data[user_id]['description'] = text
        context.user_data['state'] = UserState.UPLOAD_PHOTO
        await update.message.reply_text(
            f"📸 Загрузите фото (до {MAX_PHOTOS_PER_ENTRY} шт.)\n"
            "Отправьте /done когда закончите"
        )
    
    elif state == UserState.UPLOAD_PHOTO:
        if text == '/done':
            await save_entry(update, context)
        else:
            await update.message.reply_text("Загрузите фото или отправьте /done")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    user_id = update.effective_user.id
    
    if context.user_data.get('state') != UserState.UPLOAD_PHOTO:
        await update.message.reply_text("Сначала начните добавление записи через /start")
        return
    
    if user_id not in temp_data:
        temp_data[user_id] = {'photos': []}
    
    current_photos = temp_data[user_id].get('photos', [])
    
    if len(current_photos) >= MAX_PHOTOS_PER_ENTRY:
        await update.message.reply_text(f"❌ Максимум {MAX_PHOTOS_PER_ENTRY} фото")
        return
    
    # Получаем фото
    photo_file = await update.message.photo[-1].get_file()
    
    # Создаем директорию для фото
    os.makedirs('photos', exist_ok=True)
    
    # Сохраняем фото
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"photos/photo_{user_id}_{timestamp}_{len(current_photos)}.jpg"
    await photo_file.download_to_drive(filename)
    
    # Проверяем фото
    if validate_photo(filename):
        current_photos.append(filename)
        temp_data[user_id]['photos'] = current_photos
        
        remaining = MAX_PHOTOS_PER_ENTRY - len(current_photos)
        await update.message.reply_text(
            f"✅ Фото сохранено! Осталось: {remaining}"
        )
    else:
        os.remove(filename)
        await update.message.reply_text("❌ Ошибка при сохранении фото")

async def save_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение записи"""
    user_id = update.effective_user.id
    
    if user_id not in temp_data:
        await update.message.reply_text("❌ Нет данных для сохранения")
        return
    
    entry_data = temp_data[user_id]
    
    # Проверяем данные
    if 'name' not in entry_data or 'description' not in entry_data:
        await update.message.reply_text("❌ Не хватает данных. Начните заново через /start")
        return
    
    # Сохраняем в БД
    db.save_entry(user_id, entry_data)
    
    # Очищаем временные данные
    del temp_data[user_id]
    context.user_data['state'] = UserState.MAIN
    
    # Формируем ответ
    response = (
        "✅ *Запись сохранена!*\n\n"
        f"{format_entry_preview(entry_data)}"
    )
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def show_entries(query, context):
    """Показать записи пользователя"""
    user_id = query.from_user.id
    entries = db.get_user_entries(user_id)
    
    if not entries:
        keyboard = [[InlineKeyboardButton("➕ Добавить запись", callback_data='add')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📭 У вас пока нет записей.",
            reply_markup=reply_markup
        )
        return
    
    # Формируем сообщение
    text = "📊 *Ваши записи:*\n\n"
    for i, entry in enumerate(entries[-5:], 1):  # Показываем последние 5
        text += f"{i}. {format_entry_preview(entry)}\n"
        text += "─" * 20 + "\n"
    
    if len(entries) > 5:
        text += f"\n*Всего записей: {len(entries)}*"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить", callback_data='add'),
         InlineKeyboardButton("📥 Экспорт", callback_data='export')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def export_entries(query, context):
    """Экспорт записей в Excel"""
    user_id = query.from_user.id
    entries = db.get_user_entries(user_id)
    
    if not entries:
        await query.edit_message_text("📭 Нет данных для экспорта.")
        return
    
    try:
        # Создаем Excel файл
        filepath = create_excel_export(entries, user_id)
        
        # Отправляем файл
        with open(filepath, 'rb') as f:
            await context.bot.send_document(
                chat_id=user_id,
                document=f,
                filename=os.path.basename(filepath),
                caption="📥 Ваш экспорт данных"
            )
        
        # Удаляем временный файл
        os.remove(filepath)
        
        await query.edit_message_text("✅ Экспорт завершен!")
    except Exception as e:
        logger.error(f"Ошибка экспорта: {e}")
        await query.edit_message_text("❌ Ошибка при экспорте")

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("Не указан BOT_TOKEN!")
        return
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
