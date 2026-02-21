import os
import shutil
from datetime import datetime
from typing import List
import pandas as pd
from config import PHOTOS_DIR, EXPORTS_DIR

def cleanup_old_files(days: int = 7):
    """
    Очищает старые временные файлы
    Args:
        days: количество дней, после которого файлы удаляются
    """
    now = datetime.now().timestamp()
    
    for directory in [PHOTOS_DIR, EXPORTS_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    file_time = os.path.getmtime(filepath)
                    if now - file_time > days * 24 * 60 * 60:
                        os.remove(filepath)

def create_excel_export(entries: List[dict], user_id: int) -> str:
    """
    Создает Excel файл с записями
    Returns:
        путь к созданному файлу
    """
    # Подготавливаем данные
    data = []
    for entry in entries:
        data.append({
            'Название': entry.get('name', ''),
            'Описание': entry.get('description', ''),
            'Количество фото': len(entry.get('photos', [])),
            'Файлы фото': ', '.join(entry.get('photos', [])),
            'Дата создания': entry.get('timestamp', '')
        })
    
    # Создаем DataFrame
    df = pd.DataFrame(data)
    
    # Сохраняем в Excel
    filename = f"export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(EXPORTS_DIR, filename)
    df.to_excel(filepath, index=False, engine='openpyxl')
    
    return filepath

def format_entry_preview(entry: dict) -> str:
    """Форматирует запись для предпросмотра"""
    lines = [
        f"📝 **{entry.get('name', 'Без названия')}**",
        f"📋 {entry.get('description', 'Нет описания')}",
        f"📸 Фото: {len(entry.get('photos', []))} шт.",
    ]
    
    if 'timestamp' in entry:
        dt = datetime.fromisoformat(entry['timestamp'])
        lines.append(f"🕐 {dt.strftime('%d.%m.%Y %H:%M')}")
    
    return '\n'.join(lines)

def validate_photo(file_path: str) -> bool:
    """Проверяет, является ли файл корректным изображением"""
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            img.verify()
        return True
    except Exception:
        return False
