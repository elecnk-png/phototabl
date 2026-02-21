import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from datetime import datetime
from config import (
    BOT_TOKEN, MAX_PHOTOS_PER_ENTRY, LOG_LEVEL, LOG_FORMAT
)
from database import db
from utils import create_excel_with_embedded_photos, format_entry_preview, validate_photo, cleanup_old_files

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
    user_id = update.effective_user.id
    context.user_data['state'] = UserState.MAIN
    
    # Очищаем временные данные при старте
    if user_id in temp_data:
        for photo in temp_data[user_id].get('photos', []):
            try:
                if os.path.exists(photo):
                    os.remove(photo)
            except:
                pass
        del temp_data[user_id]
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить запись", callback_data='add')],
        [InlineKeyboardButton("📊 Мои записи", callback_data='view')],
        [InlineKeyboardButton("📥 Экспорт в Excel", callback_data='export')],
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Добро пожаловать в Table Bot!\n\n"
        "Я помогу вам создавать таблицы с информацией и фотографиями.\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🤖 *Справка по командам*\n\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n"
        "/cancel - Отмена текущего действия\n\n"
        "*Как пользоваться:*\n"
        "1️⃣ Нажмите 'Добавить запись'\n"
        "2️⃣ Введите название\n"
        "3️⃣ Введите описание\n"
        "4️⃣ Загрузите фотографии (до 5 шт.)\n"
        "5️⃣ Нажмите кнопку '✅ Готово' для сохранения\n\n"
        "📸 Поддерживаются форматы: JPG, PNG\n"
        "📊 В Excel файле фото будут ВСТРОЕНЫ прямо в таблицу"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    user_id = update.effective_user.id
    context.user_data.clear()
    
    if user_id in temp_data:
        for photo in temp_data[user_id].get('photos', []):
            try:
                if os.path.exists(photo):
                    os.remove(photo)
                    logger.info(f"Удалено временное фото: {photo}")
            except Exception as e:
                logger.error(f"Ошибка при удалении фото {photo}: {e}")
        del temp_data[user_id]
    
    await update.message.reply_text(
        "❌ Действие отменено. Используйте /start для нового действия."
    )

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
            "📊 *Статистика бота*\n\n"
            f"👥 Пользователей: {stats['total_users']}\n"
            f"📝 Всего записей: {stats['total_entries']}\n"
            f"📸 Всего фото: {stats['total_photos']}"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data == 'done_upload':
        await save_entry_from_callback(query, context)
    
    elif query.data == 'main':
        await main_menu(query, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    state = context.user_data.get('state')
    text = update.message.text
    
    logger.info(f"Получено сообщение от {user_id}: {text}, состояние: {state}")
    
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
            "После загрузки всех фото нажмите кнопку '✅ Готово':",
            reply_markup=reply_markup
        )
    
    elif state == UserState.UPLOAD_PHOTO:
        if text == '/done':
            await save_entry(update, context)
        else:
            await update.message.reply_text(
                "Пожалуйста, загрузите фото или нажмите кнопку '✅ Готово'"
            )
    
    else:
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Используйте /start для начала работы",
            reply_markup=reply_markup
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    user_id = update.effective_user.id
    state = context.user_data.get('state')
    
    logger.info(f"Получено фото от {user_id}, состояние: {state}")
    
    if state != UserState.UPLOAD_PHOTO:
        await update.message.reply_text(
            "Сначала начните добавление записи через /start",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Главное меню", callback_data='main')
            ]])
        )
        return
    
    if user_id not in temp_data:
        temp_data[user_id] = {'photos': []}
    
    current_photos = temp_data[user_id].get('photos', [])
    
    if len(current_photos) >= MAX_PHOTOS_PER_ENTRY:
        await update.message.reply_text(
            f"❌ Достигнут лимит фото (макс. {MAX_PHOTOS_PER_ENTRY})",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Готово", callback_data='done_upload')
            ]])
        )
        return
    
    try:
        # Получаем фото максимального качества
        photo_file = await update.message.photo[-1].get_file()
        
        # Создаем директорию для фото
        os.makedirs('photos', exist_ok=True)
        
        # Создаем уникальное имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"photos/photo_{user_id}_{timestamp}_{len(current_photos)}.jpg"
        
        # Скачиваем фото
        logger.info(f"Скачивание фото в {filename}")
        await photo_file.download_to_drive(filename)
        
        # Проверяем что файл скачался
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            logger.info(f"Фото скачано, размер: {file_size} байт")
            
            # Проверяем фото
            if validate_photo(filename):
                current_photos.append(filename)
                temp_data[user_id]['photos'] = current_photos
                
                remaining = MAX_PHOTOS_PER_ENTRY - len(current_photos)
                
                keyboard = [[InlineKeyboardButton("✅ Готово", callback_data='done_upload')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if remaining > 0:
                    await update.message.reply_text(
                        f"✅ Фото сохранено!\n"
                        f"📸 Загружено: {len(current_photos)}/{MAX_PHOTOS_PER_ENTRY}\n"
                        f"Осталось мест: {remaining}",
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(
                        f"✅ Все фото загружены! Нажмите '✅ Готово' для сохранения.",
                        reply_markup=reply_markup
                    )
            else:
                os.remove(filename)
                await update.message.reply_text(
                    "❌ Файл поврежден или не является изображением. Попробуйте другое фото."
                )
        else:
            logger.error(f"Файл не создан: {filename}")
            await update.message.reply_text("❌ Ошибка при сохранении фото. Попробуйте еще раз.")
            
    except Exception as e:
        logger.error(f"Ошибка при сохранении фото: {e}")
        await update.message.reply_text(
            "❌ Ошибка при сохранении фото. Попробуйте еще раз."
        )

async def save_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение записи из текстовой команды"""
    user_id = update.effective_user.id
    
    if user_id not in temp_data:
        await update.message.reply_text(
            "❌ Нет данных для сохранения. Начните заново через /start"
        )
        return
    
    await _save_entry_data(update.effective_user, update.message, context)

async def save_entry_from_callback(query, context):
    """Сохранение записи из callback (кнопка)"""
    user_id = query.from_user.id
    
    if user_id not in temp_data:
        await query.edit_message_text(
            "❌ Нет данных для сохранения. Начните заново через /start"
        )
        return
    
    await _save_entry_data(query.from_user, query, context)

async def _save_entry_data(user, message_or_query, context):
    """Общая функция сохранения записи"""
    user_id = user.id
    
    entry_data = temp_data[user_id]
    
    # Проверяем данные
    if 'name' not in entry_data or 'description' not in entry_data:
        text = "❌ Не хватает данных. Начните заново через /start"
        if hasattr(message_or_query, 'edit_message_text'):
            await message_or_query.edit_message_text(text)
        else:
            await message_or_query.reply_text(text)
        return
    
    # Сохраняем в БД
    db.save_entry(user_id, entry_data)
    
    # Получаем сохраненную запись для preview
    entries = db.get_user_entries(user_id)
    saved_entry = entries[-1] if entries else entry_data
    
    # Очищаем временные данные (но НЕ удаляем фото, они теперь в БД)
    if user_id in temp_data:
        # Не удаляем фото, они нужны для будущего экспорта
        # Просто очищаем временные данные
        del temp_data[user_id]
    
    context.user_data['state'] = UserState.MAIN
    
    # Формируем ответ
    response = (
        "✅ *Запись успешно сохранена!*\n\n"
        f"{format_entry_preview(saved_entry)}"
    )
    
    # Создаем клавиатуру для дальнейших действий
    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё", callback_data='add')],
        [InlineKeyboardButton("📊 Мои записи", callback_data='view')],
        [InlineKeyboardButton("📥 Экспорт в Excel", callback_data='export')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем ответ
    if hasattr(message_or_query, 'edit_message_text'):
        await message_or_query.edit_message_text(
            response,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await message_or_query.reply_text(
            response,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

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
    for i, entry in enumerate(entries[-5:], 1):
        text += f"{i}. {format_entry_preview(entry)}\n"
        text += "─" * 20 + "\n"
    
    if len(entries) > 5:
        text += f"\n*Всего записей: {len(entries)}*"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить", callback_data='add'),
         InlineKeyboardButton("📥 Экспорт", callback_data='export')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def export_entries(query, context):
    """Экспорт записей в Excel с ВСТРОЕННЫМИ изображениями"""
    user_id = query.from_user.id
    entries = db.get_user_entries(user_id)
    
    if not entries:
        await query.edit_message_text("📭 Нет данных для экспорта.")
        return
    
    try:
        # Отправляем сообщение о начале экспорта
        await query.edit_message_text(
            "⏳ Создаю Excel файл с ВСТРОЕННЫМИ фотографиями...\n"
            "Это может занять несколько секунд..."
        )
        
        # Проверяем наличие фото
        total_photos = sum(len(entry.get('photos', [])) for entry in entries)
        logger.info(f"Начинаем экспорт {len(entries)} записей с {total_photos} фото")
        
        # Создаем Excel файл с ВСТРОЕННЫМИ изображениями
        filepath = create_excel_with_embedded_photos(entries, user_id)
        
        # Проверяем что файл создан
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            logger.info(f"Excel файл создан, размер: {file_size} байт")
            
            # Отправляем файл
            with open(filepath, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=os.path.basename(filepath),
                    caption=f"📥 Ваш экспорт данных\n"
                            f"📸 Всего фото: {total_photos}\n"
                            f"📦 Размер файла: {file_size/1024:.1f} KB\n\n"
                            f"✅ Фото ВСТРОЕНЫ в файл!"
                )
            
            # Удаляем временный файл
            os.remove(filepath)
            logger.info(f"Временный файл удален: {filepath}")
            
            # Возвращаемся в меню
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data='main')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Экспорт завершен! Файл с встроенными фото отправлен.",
                reply_markup=reply_markup
            )
        else:
            logger.error(f"Excel файл не создан")
            await query.edit_message_text("❌ Ошибка при создании Excel файла")
        
    except Exception as e:
        logger.error(f"Ошибка экспорта: {e}")
        await query.edit_message_text(
            "❌ Ошибка при экспорте. Пожалуйста, попробуйте позже."
        )

async def main_menu(query, context):
    """Возврат в главное меню"""
    user_id = query.from_user.id
    context.user_data['state'] = UserState.MAIN
    
    # Очищаем временные данные при возврате в меню
    if user_id in temp_data:
        for photo in temp_data[user_id].get('photos', []):
            try:
                if os.path.exists(photo):
                    os.remove(photo)
            except:
                pass
        del temp_data[user_id]
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить запись", callback_data='add')],
        [InlineKeyboardButton("📊 Мои записи", callback_data='view')],
        [InlineKeyboardButton("📥 Экспорт в Excel", callback_data='export')],
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👋 Главное меню. Выберите действие:",
        reply_markup=reply_markup
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("❌ Не указан BOT_TOKEN в переменных окружения!")
        return
    
    # Создаем необходимые директории
    os.makedirs('photos', exist_ok=True)
    os.makedirs('exports', exist_ok=True)
    
    # Очищаем старые файлы при запуске
    cleanup_old_files(days=1)
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Регистрируем обработчики callback-кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Регистрируем обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("🚀 Бот запущен и готов к работе!")
    logger.info(f"📸 Максимум фото на запись: {MAX_PHOTOS_PER_ENTRY}")
    
    try:
        application.run_polling()
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")

if __name__ == '__main__':
    main()
