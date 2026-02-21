import logging
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from datetime import datetime
from config import (
    BOT_TOKEN, MAX_PHOTOS_PER_ENTRY, PHOTOS_DIR, 
    EXPORTS_DIR, LOG_LEVEL, LOG_FORMAT, DEBUG, USE_WEBHOOK, WEBHOOK_URL
)
from database import db
from utils import create_excel_export, format_entry_preview, validate_photo, cleanup_old_files

# Настройка логирования
logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
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
    user_id = update.effective_user.id
    
    # Сбрасываем состояние
    context.user_data['state'] = UserState.MAIN
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить запись", callback_data='add')],
        [InlineKeyboardButton("📊 Мои записи", callback_data='view')],
        [InlineKeyboardButton("📥 Экспорт в Excel", callback_data='export')],
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "👋 Добро пожаловать в Table Bot!\n\n"
        "Я помогу вам создавать таблицы с информацией и фотографиями.\n\n"
        "📌 Что я умею:\n"
        "• Добавлять записи с названием и описанием\n"
        "• Прикреплять до 5 фото к каждой записи\n"
        "• Показывать все записи в удобном виде\n"
        "• Экспортировать данные в Excel\n\n"
        "Выберите действие:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🤖 *Справка по командам*\n\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n"
        "/cancel - Отмена текущего действия\n"
        "/stats - Статистика записей\n\n"
        "*Как пользоваться:*\n"
        "1️⃣ Нажмите 'Добавить запись'\n"
        "2️⃣ Введите название\n"
        "3️⃣ Введите описание\n"
        "4️⃣ Загрузите фото (до 5 шт.)\n"
        "5️⃣ Нажмите 'Готово' для сохранения\n\n"
        "📸 Поддерживаются форматы: JPG, PNG, GIF"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    context.user_data.clear()
    user_id = update.effective_user.id
    if user_id in temp_data:
        del temp_data[user_id]
    
    await update.message.reply_text(
        "❌ Действие отменено. Используйте /start для нового действия."
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику"""
    stats = await db.get_stats()
    
    text = (
        "📊 *Статистика бота*\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📝 Всего записей: {stats['total_entries']}\n"
        f"📸 Всего фото: {stats['total_photos']}"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

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
        stats = await db.get_stats()
        text = (
            "📊 *Ваша статистика*\n\n"
            f"📝 Всего записей: {stats['total_entries']}\n"
            f"📸 Всего фото: {stats['total_photos']}"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data.startswith('delete_'):
        # Обработка удаления записи
        entry_index = int(query.data.split('_')[1])
        user_id = query.from_user.id
        deleted = await db.delete_entry(user_id, entry_index)
        
        if deleted:
            await query.edit_message_text("✅ Запись удалена!")
        else:
            await query.edit_message_text("❌ Ошибка при удалении")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    state = context.user_data.get('state')
    text = update.message.text
    
    if text == '/cancel':
        await cancel(update, context)
        return
    
    if state == UserState.ENTER_NAME:
        temp_data[user_id]['name'] = text
        context.user_data['state'] = UserState.ENTER_DESCRIPTION
        await update.message.reply_text("📋 Введите описание:")
    
    elif state == UserState.ENTER_DESCRIPTION:
        temp_data[user_id]['description'] = text
        context.user_data['state'] = UserState.UPLOAD_PHOTO
        
        keyboard = [[InlineKeyboardButton("✅ Готово", callback_data='done_upload')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📸 Загрузите фотографии (до {MAX_PHOTOS_PER_ENTRY} шт.)\n"
            "После загрузки всех фото нажмите 'Готово':",
            reply_markup=reply_markup
        )
    
    elif state == UserState.UPLOAD_PHOTO:
        if text == '/done':
            await save_entry(update, context)
        else:
            await update.message.reply_text(
                "Пожалуйста, загрузите фото или используйте /done"
            )

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
        await update.message.reply_text(f"❌ Достигнут лимит фото (макс. {MAX_PHOTOS_PER_ENTRY})")
        return
    
    # Получаем фото
    photo_file = await update.message.photo[-1].get_file()
    
    # Создаем уникальное имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"photo_{user_id}_{timestamp}_{len(current_photos)}.jpg"
    filepath = os.path.join(PHOTOS_DIR, filename)
    
    # Сохраняем фото
    await photo_file.download_to_drive(filepath)
    
    # Проверяем, что файл действительно изображение
    if validate_photo(filepath):
        current_photos.append(filepath)
        temp_data[user_id]['photos'] = current_photos
        
        remaining = MAX_PHOTOS_PER_ENTRY - len(current_photos)
        await update.message.reply_text(
            f"✅ Фото сохранено!\n"
            f"📸 Загружено: {len(current_photos)}/{MAX_PHOTOS_PER_ENTRY}\n"
            f"Осталось мест: {remaining}"
        )
    else:
        os.remove(filepath)
        await update.message.reply_text("❌ Файл поврежден или не является изображением")

async def save_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение записи в БД"""
    user_id = update.effective_user.id
    
    if user_id not in temp_data:
        await update.message.reply_text("❌ Нет данных для сохранения")
        return
    
    entry_data = temp_data[user_id]
    
    # Проверяем обязательные поля
    if 'name' not in entry_data or 'description' not in entry_data:
        await update.message.reply_text("❌ Не хватает данных. Начните заново через /start")
        return
    
    # Сохраняем в БД
    await db.save_entry(user_id, entry_data)
    
    # Очищаем временные данные
    del temp_data[user_id]
    context.user_data['state'] = UserState.MAIN
    
    # Формируем ответ
    response = (
        "✅ *Запись успешно сохранена!*\n\n"
        f"{format_entry_preview(entry_data)}"
    )
    
    # Создаем клавиатуру для дальнейших действий
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё", callback_data='add')],
        [InlineKeyboardButton("📊 Мои записи", callback_data='view')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        response, 
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_entries(query, context):
    """Показать записи пользователя"""
    user_id = query.from_user.id
    entries = await db.get_user_entries(user_id)
    
    if not entries:
        keyboard = [[InlineKeyboardButton("➕ Добавить запись", callback_data='add')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📭 У вас пока нет записей.",
            reply_markup=reply_markup
        )
        return
    
    # Формируем сообщение с записями
    text = "📊 *Ваши записи:*\n\n"
    
    for i, entry in enumerate(entries, 1):
        text += f"{i}. {format_entry_preview(entry)}\n"
        text += "─" * 20 + "\n"
    
    # Добавляем кнопки управления
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
    entries = await db.get_user_entries(user_id)
    
    if not entries:
        await query.edit_message_text("📭 Нет данных для экспорта.")
        return
    
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
    
    # Очищаем временный файл
    os.remove(filepath)
    
    await query.edit_message_text("✅ Экспорт завершен! Файл отправлен.")

async def post_init(application: Application):
    """Действия после инициализации бота"""
    # Очищаем старые файлы при запуске
    cleanup_old_files(days=1)
    logger.info("Бот успешно запущен!")

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("Не указан BOT_TOKEN! Проверьте config.py или переменные окружения.")
        return
    
    # Создаем приложение
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Регистрируем обработчики сообщений
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Запуск бота
    if USE_WEBHOOK and WEBHOOK_URL:
        # Режим webhook (для продакшена)
        application.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            webhook_url=WEBHOOK_URL
        )
    else:
        # Режим polling (для разработки)
        logger.info("Бот запущен в режиме polling...")
        application.run_polling()

if __name__ == '__main__':
    main()
