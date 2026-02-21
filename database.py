import json
import os
from datetime import datetime
from typing import List, Dict, Any

class Database:
    """Простая файловая база данных для хранения записей"""
    
    def __init__(self, db_file='data.json'):
        self.db_file = db_file
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Создает файл БД, если его нет"""
        if not os.path.exists(self.db_file):
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    def save_entry(self, user_id: int, entry: Dict[str, Any]) -> bool:
        """Сохраняет запись (синхронная версия)"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        user_id_str = str(user_id)
        if user_id_str not in data:
            data[user_id_str] = []
        
        # Добавляем timestamp
        entry['timestamp'] = datetime.now().isoformat()
        data[user_id_str].append(entry)
        
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    
    def get_user_entries(self, user_id: int) -> List[Dict]:
        """Получает все записи пользователя"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        
        return data.get(str(user_id), [])
    
    def delete_entry(self, user_id: int, entry_index: int) -> Dict | None:
        """Удаляет запись по индексу"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        
        user_id_str = str(user_id)
        if user_id_str in data and 0 <= entry_index < len(data[user_id_str]):
            deleted = data[user_id_str].pop(entry_index)
            
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return deleted
        
        return None
    
    def get_stats(self) -> Dict:
        """Получает статистику по всем записям"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'total_users': 0, 'total_entries': 0, 'total_photos': 0}
        
        total_users = len(data)
        total_entries = sum(len(entries) for entries in data.values())
        total_photos = sum(
            sum(len(entry.get('photos', [])) for entry in entries)
            for entries in data.values()
        )
        
        return {
            'total_users': total_users,
            'total_entries': total_entries,
            'total_photos': total_photos
        }

# Создаем глобальный экземпляр БД
db = Database()
