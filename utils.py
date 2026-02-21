import os
from datetime import datetime
from typing import List
import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, Border, Side
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)

def create_excel_with_embedded_photos(entries: List[dict], user_id: int) -> str:
    """
    Создает Excel файл с ВСТРОЕННЫМИ изображениями
    """
    try:
        # Создаем директорию для экспорта
        os.makedirs('exports', exist_ok=True)
        
        # Создаем новый Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Записи с фото"
        
        # Заголовки
        headers = ['№', 'Название', 'Описание', 'Фото', 'Количество фото', 'Дата создания']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, size=12)
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Настройка ширины колонок
        ws.column_dimensions['A'].width = 5
        ws.column_dimensions['B'].width = 25
        ws.column_dimensions['C'].width = 35
        ws.column_dimensions['D'].width = 25
        ws.column_dimensions['E'].width = 12
        ws.column_dimensions['F'].width = 18
        
        current_row = 2
        
        for idx, entry in enumerate(entries, 1):
            logger.info(f"Обработка записи {idx}: {entry.get('name', 'Без названия')}")
            
            # Основные данные
            ws.cell(row=current_row, column=1, value=idx)
            ws.cell(row=current_row, column=2, value=entry.get('name', ''))
            ws.cell(row=current_row, column=3, value=entry.get('description', ''))
            
            photos = entry.get('photos', [])
            ws.cell(row=current_row, column=5, value=len(photos))
            
            # Дата
            timestamp = entry.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    ws.cell(row=current_row, column=6, value=dt.strftime('%d.%m.%Y %H:%M'))
                except:
                    ws.cell(row=current_row, column=6, value=timestamp)
            
            # ВСТРАИВАЕМ ФОТО В ЯЧЕЙКУ
            if photos and len(photos) > 0:
                # Берем первое фото
                photo_path = photos[0]
                logger.info(f"Обработка фото: {photo_path}")
                
                if os.path.exists(photo_path):
                    try:
                        # Открываем изображение
                        with Image.open(photo_path) as img:
                            # Конвертируем в RGB если нужно
                            if img.mode in ('RGBA', 'LA', 'P'):
                                if img.mode == 'RGBA':
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    background.paste(img, mask=img.split()[3])
                                    img = background
                                else:
                                    img = img.convert('RGB')
                            
                            # Изменяем размер
                            img.thumbnail((180, 120), Image.Resampling.LANCZOS)
                            
                            # Сохраняем в байтовый поток
                            img_bytes = io.BytesIO()
                            img.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            
                            # Создаем изображение для Excel
                            xl_img = XLImage(img_bytes)
                            
                            # ВСТРАИВАЕМ в ячейку D
                            ws.add_image(xl_img, f'D{current_row}')
                            
                            # Настраиваем высоту строки
                            ws.row_dimensions[current_row].height = max(70, img.height * 0.75)
                            
                            logger.info(f"✅ Фото встроено в ячейку D{current_row}")
                            
                    except Exception as e:
                        logger.error(f"Ошибка при встраивании фото: {e}")
                        ws.cell(row=current_row, column=4, value="[Ошибка фото]")
                else:
                    logger.warning(f"Фото не найдено: {photo_path}")
                    ws.cell(row=current_row, column=4, value="[Фото не найдено]")
            else:
                ws.cell(row=current_row, column=4, value="Нет фото")
            
            current_row += 1
        
        # Добавляем границы
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for row in ws.iter_rows(min_row=1, max_row=current_row-1, min_col=1, max_col=6):
            for cell in row:
                cell.border = thin_border
        
        # Сохраняем Excel файл
        filename = f"export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join('exports', filename)
        wb.save(filepath)
        
        # Проверяем размер файла
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            logger.info(f"✅ Excel файл создан: {filepath}, размер: {file_size} байт")
        else:
            logger.error("❌ Файл не был создан!")
        
        return filepath
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании Excel: {e}")
        # В случае ошибки создаем простой Excel
        return create_simple_excel(entries, user_id)

def create_simple_excel(entries: List[dict], user_id: int) -> str:
    """Создает простой Excel файл без изображений"""
    try:
        os.makedirs('exports', exist_ok=True)
        
        data = []
        for entry in entries:
            photos = entry.get('photos', [])
            photo_names = []
            for path in photos:
                if os.path.exists(path):
                    photo_names.append(os.path.basename(path))
                else:
                    photo_names.append("[файл не найден]")
            
            data.append({
                'Название': entry.get('name', ''),
                'Описание': entry.get('description', ''),
                'Количество фото': len(photos),
                'Файлы фото': ', '.join(photo_names) if photo_names else 'Нет фото',
                'Дата создания': entry.get('timestamp', '')
            })
        
        df = pd.DataFrame(data)
        
        filename = f"export_simple_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join('exports', filename)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Записи', index=False)
            
            # Настраиваем ширину колонок
            worksheet = writer.sheets['Записи']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(f"✅ Простой Excel файл создан: {filename}")
        return filepath
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании простого Excel: {e}")
        raise

def format_entry_preview(entry: dict) -> str:
    """Форматирует запись для предпросмотра"""
    lines = [
        f"📝 **{entry.get('name', 'Без названия')}**",
        f"📋 {entry.get('description', 'Нет описания')}",
        f"📸 Фото: {len(entry.get('photos', []))} шт.",
    ]
    
    if 'timestamp' in entry:
        try:
            dt = datetime.fromisoformat(entry['timestamp'])
            lines.append(f"🕐 {dt.strftime('%d.%m.%Y %H:%M')}")
        except:
            lines.append(f"🕐 {entry['timestamp']}")
    
    return '\n'.join(lines)

def validate_photo(file_path: str) -> bool:
    """Проверяет, является ли файл корректным изображением"""
    try:
        if not os.path.exists(file_path):
            logger.warning(f"Файл не существует: {file_path}")
            return False
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.warning(f"Файл пустой: {file_path}")
            return False
        
        if file_size > 20 * 1024 * 1024:
            logger.warning(f"Файл слишком большой: {file_size} байт")
            return False
        
        # Проверяем что это изображение
        with Image.open(file_path) as img:
            img.verify()
        
        # Дополнительная проверка
        with Image.open(file_path) as img:
            img.load()
            logger.info(f"✅ Фото проверено: {os.path.basename(file_path)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка валидации фото {file_path}: {e}")
        return False

# ДОБАВЛЯЕМ ЭТУ ФУНКЦИЮ
def cleanup_old_files(days: int = 7):
    """Очищает старые файлы"""
    try:
        now = datetime.now().timestamp()
        deleted = 0
        errors = 0
        
        for directory in ['photos', 'exports']:
            if os.path.exists(directory):
                for filename in os.listdir(directory):
                    filepath = os.path.join(directory, filename)
                    if os.path.isfile(filepath):
                        try:
                            file_time = os.path.getmtime(filepath)
                            if now - file_time > days * 24 * 60 * 60:
                                os.remove(filepath)
                                deleted += 1
                                logger.info(f"Удален старый файл: {filepath}")
                        except Exception as e:
                            errors += 1
                            logger.error(f"Ошибка при удалении {filepath}: {e}")
        
        logger.info(f"Очистка завершена. Удалено файлов: {deleted}, ошибок: {errors}")
        return deleted
    except Exception as e:
        logger.error(f"Ошибка при очистке файлов: {e}")
        return 0

def get_photo_stats(entries: List[dict]) -> dict:
    """Получает статистику по фото"""
    try:
        total_photos = 0
        entries_with_photos = 0
        total_size = 0
        
        for entry in entries:
            photos = entry.get('photos', [])
            if photos:
                entries_with_photos += 1
                total_photos += len(photos)
                
                for photo_path in photos:
                    if os.path.exists(photo_path):
                        try:
                            total_size += os.path.getsize(photo_path)
                        except:
                            pass
        
        return {
            'total_entries': len(entries),
            'entries_with_photos': entries_with_photos,
            'total_photos': total_photos,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return {}
