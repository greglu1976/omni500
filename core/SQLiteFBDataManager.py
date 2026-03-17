import sqlite3
import pickle
import json
from datetime import datetime

from typing import Dict, Any, Optional, List

from .FBData import FBData

from logger.logger import Logger

class SQLiteFBDataManager:
    def __init__(self, db_path="fbdata.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                data BLOB,
                meta_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_fb_data(self, fb_data: FBData): #, device_name: str):
        """Сохраняет объект в SQLite"""
        try:
            # Сериализуем объект
            serialized_data = pickle.dumps(fb_data)
            device_name = fb_data.info.iec61850_name
            # Метаинформация
            meta_data = {
                "russian_name": getattr(fb_data.info, 'russian_name', ''),
                "version": getattr(fb_data.info, 'fb_version', ''),
                "saved_at": datetime.now().isoformat()                
            }
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO devices (name, data, meta_json)
                VALUES (?, ?, ?)
            ''', (device_name, serialized_data, json.dumps(meta_data)))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Объект '{device_name}' сохранен в SQLite")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def load_fb_data(self, device_name: str) -> Optional[FBData]:
        """Загружает объект из SQLite"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT data FROM devices WHERE name = ?', (device_name,))
            result = cursor.fetchone()
            
            if result:
                fb_data = pickle.loads(result[0])
                #print(f"✅ Объект '{device_name}' загружен из SQLite")
                Logger.info(f"Объект '{device_name}' загружен из SQLite")
                return fb_data
            else:
                print(f"❌ Объект '{device_name}' не найден")
                Logger.error(f"Объект '{device_name}' не найден")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка загрузки: {e}")
            return None
        finally:
            if conn:
                conn.close()  # Гарантированное закрытие            

    def get_device_meta(self, device_name: str) -> Optional[Dict]:
        """Возвращает метаинформацию об устройстве"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT meta_json FROM devices WHERE name = ?', (device_name,))
            result = cursor.fetchone()
            
            conn.close()
            
            if result and result[0]:
                return json.loads(result[0])
            return None
            
        except Exception as e:
            print(f"❌ Ошибка получения метаданных: {e}")
            return None
        
    def get_all_device_names(self) -> List[str]:
        """Возвращает список всех устройств"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT name FROM devices')
        results = cursor.fetchall()
        
        conn.close()
        
        return [result[0] for result in results]
    
    def delete_device(self, device_name: str) -> bool:
        """Удаляет устройство из базы"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM devices WHERE name = ?', (device_name,))
            conn.commit()
            conn.close()
            
            print(f"✅ Объект '{device_name}' удален из SQLite")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка удаления: {e}")
            return False



if __name__ == "__main__":
    manager = SQLiteFBDataManager()
    print(manager.get_all_device_names())

    #fb = manager.load_fb_data("LVDIS")
    #print(fb.info.russian_name)
    #print(fb.info.description_fb)
    #funcs = fb.info.get_function_names()
    #print(fb.info.get_function_names())

    #for func in funcs:
        #print(f"=== {func} ===")
        #print(fb.get_func_description_by_name(func))
    #print(fb.get_functions_with_settings())

