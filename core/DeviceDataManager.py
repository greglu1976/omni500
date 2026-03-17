import configparser
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class DeviceDataManager:
    def __init__(self, config_path: str = 'devices.ini'):
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации устройств не найден: {self.config_path}")
        self._devices = self._load_devices()

    def _load_devices(self) -> Dict[str, Dict[str, Any]]:
        """Загружает и парсит devices.ini в словарь устройств."""
        config = configparser.ConfigParser()
        # Сохраняем регистр имён параметров (по умолчанию ConfigParser приводит к нижнему)
        config.optionxform = str
        config.read(self.config_path, encoding='utf-8')

        devices = {}
        for section in config.sections():
            device = {}
            for key, value in config.items(section):
                # Попытка распарсить JSON (например, для поля 'versions')
                if self._looks_like_json(value):
                    try:
                        device[key] = json.loads(value)
                    except json.JSONDecodeError:
                        # Если не JSON — оставляем как строку
                        device[key] = value
                else:
                    device[key] = value
            devices[section] = device
        return devices

    def _looks_like_json(self, value: str) -> bool:
        """Эвристика: похоже ли значение на JSON?"""
        value = value.strip()
        return (value.startswith('[') and value.endswith(']')) or \
               (value.startswith('{') and value.endswith('}'))

    def get_device(self, device_key: str) -> Optional[Dict[str, Any]]:
        """Возвращает устройство по имени секции (например, 'DEVICE1')."""
        return self._devices.get(device_key)

    def get_device_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Возвращает устройство по полю 'name' (например, 'ЮНИТ-М300-ДЗТ2')."""
        for device in self._devices.values():
            if device.get('name') == name:
                return device
        return None

    def get_device_by_name_and_version(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает устройство по полю 'name' и полю 'version'.
        
        Args:
            name (str): Имя устройства (например, "ЮНИТ-М300-ДЗТ2")
            version (str): Версия устройства (например, "1.0")
        
        Returns:
            dict или None: Найденное устройство или None, если не найдено.
        """
        for device in self._devices.values():
            if device.get('name') == name and device.get('version') == version:
                return device
        return None

    def get_all_device_keys(self) -> List[str]:
        """Возвращает список всех ключей устройств (имена секций)."""
        return list(self._devices.keys())

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Возвращает список всех устройств."""
        return list(self._devices.values())

    def add_device(self, key: str, device_data: Dict[str, Any]):
        """Добавляет новое устройство (в памяти). Для сохранения в файл — нужен отдельный метод."""
        # Преобразуем сложные типы в строки (например, list/dict → JSON)
        safe_data = {}
        for k, v in device_data.items():
            if isinstance(v, (dict, list)):
                safe_data[k] = json.dumps(v, ensure_ascii=False)
            else:
                safe_data[k] = str(v)
        self._devices[key] = safe_data

    def save_to_file(self, output_path: str = None):
        """Сохраняет текущие данные обратно в INI-файл."""
        output_path = Path(output_path) if output_path else self.config_path
        config = configparser.ConfigParser()
        config.optionxform = str  # сохраняем регистр

        for key, device in self._devices.items():
            config[key] = {}
            for param, value in device.items():
                # Убеждаемся, что значение — строка
                if isinstance(value, (dict, list)):
                    config[key][param] = json.dumps(value, ensure_ascii=False)
                else:
                    config[key][param] = str(value)

        with open(output_path, 'w', encoding='utf-8') as f:
            config.write(f, space_around_delimiters=False)
