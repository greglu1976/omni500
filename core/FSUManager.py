# fsu_manager.py
import json
from pathlib import Path

class FSUManager:
    def __init__(self, config_path='fsu.json'):
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self):
        """Загружает конфигурацию FSU из JSON файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Конфигурационный файл {self.config_path} не найден")
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка парсинга {self.config_path}: {e}")
    
    def get_fbs_by_fsu_type(self, fsu_type):
        """Возвращает список ФБ для указанного типа ФСУ"""
        if fsu_type not in self._config:
            available_types = list(self._config.keys())
            raise ValueError(f"Тип ФСУ '{fsu_type}' не найден. Доступные типы: {available_types}")
        
        return self._config[fsu_type]
    
    def get_available_fsu_types(self):
        """Возвращает список доступных типов ФСУ"""
        return list(self._config.keys())
    
    def add_fsu_type(self, fsu_type, fb_list):
        """Добавляет новый тип ФСУ в конфигурацию"""
        self._config[fsu_type] = fb_list
        self._save_config()
    
    def _save_config(self):
        """Сохраняет конфигурацию обратно в файл"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)