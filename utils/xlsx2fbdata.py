# Генерация объекта FBData из XLSX описания ФБ
# Вспомогательный скрипт, заносит в базу объекты 
from pathlib import Path

import pandas as pd
import numpy as np
import json
from typing import Dict, Any
from core.FBData import FBData  # импортируйте ваши классы
from core.SQLiteFBDataManager import SQLiteFBDataManager

from logger.logger import Logger

COLUMN_DTYPES = {
    'minValue': 'float64',
    'maxValue': 'float64', 
    'step': 'float64',
    'DefaultValue': 'float64',
    'Logger': 'Int64',
    'Disturber': 'Int64',
    'StartDisturber': 'Int64',
    'reserved1': 'string',
    'reserved2': 'string',
    '61850_EnumDAType': 'string',
    'units': 'string',
    'Note (Справочная информация)': 'string',
}

REQUIRED_COLUMNS = [
    'Категория (group)', 'NodeName (рус)', 'FullDescription (Описание параметра для пояснения в ПО ЮНИТ Сервис)',
    'ShortDescription', 'AppliedDescription', 'Note (Справочная информация)', 'Name GEB', 'type', 'units',
    'minValue', 'maxValue', 'step', 'DefaultValue', '61850_TypeLN', '61850_DataObjectName',
    '61850_CommonDataClass', '61850_AttributeName', '61850_EnumDAType', '61850_FC',
    'DigitalInput', 'DigitalOutput', 'FunctionalButton', 'LED', 'Logger', 'Disturber',
    'StartDisturber', 'reserved1', 'reserved2'
]

def parse_tech_info_sheet(df):
    df = df.dropna(subset=['Parameter']).copy()
    df['Value'] = df['Value'].where(pd.notnull(df['Value']), None)

    result_dict = {}
    func_list = []
    current_block = None

    for _, row in df.iterrows():
        param = row['Parameter']
        value = row['Value']

        if param == "DescriptionFuncList":
            if current_block is not None and current_block:
                func_list.append(current_block)
            current_block = {}
        else:
            if current_block is not None:
                current_block[param] = value
            else:
                result_dict[param] = value

    if current_block is not None and current_block:
        func_list.append(current_block)

    result_dict["DescriptionFuncList"] = func_list
    return result_dict

def convert_xlsx_to_fbdata(xlsx_path: str) -> FBData:
    """
    Конвертирует XLSX файл напрямую в объект FBData
    Возвращает: объект FBData
    """
    target_sheets = ["Controls", "Status information", "Settings", "TechInfo"]
    result_data = {}
    
    for sheet_name in target_sheets:
        try:
            if sheet_name == "TechInfo":
                df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=1)
                result_data[sheet_name] = parse_tech_info_sheet(df)
            else:
                df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=1)

                # Добавляем недостающие столбцы
                for col in ['reserved1', 'reserved2', 'Logger', 'Disturber', 'StartDisturber']:
                    if col not in df.columns:
                        df[col] = np.nan

                # Заменяем "null" на np.nan
                df = df.replace("null", np.nan)

                # Убедимся, что все нужные столбцы присутствуют
                for col in REQUIRED_COLUMNS:
                    if col not in df.columns:
                        df[col] = np.nan

                # Преобразуем типы
                for col, dtype in COLUMN_DTYPES.items():
                    if col not in df.columns:
                        continue

                    if dtype in ('float64', 'Int64'):
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        df[col] = df[col].astype(dtype)
                    elif dtype == 'string':
                        df[col] = df[col].astype('string')

                # Ручная замена NaN на None
                data = []
                for _, row in df[REQUIRED_COLUMNS].iterrows():
                    record = {}
                    for col in REQUIRED_COLUMNS:
                        value = row[col]
                        
                        # Проверяем на NaN/nat
                        if pd.isna(value):
                            record[col] = None
                        else:
                            record[col] = value
                    
                    data.append(record)
                #print(data)
                result_data[sheet_name] = data
                
                print(f"✅ Обработан лист: {sheet_name} ({len(data)} строк)")
                Logger.info(f"Обработан лист: {sheet_name} ({len(data)} строк)")
            
        except Exception as e:
            print(f"⚠️ Ошибка при обработке листа {sheet_name}: {e}")
            Logger.error(f"Ошибка при обработке листа {sheet_name}: {e}")
            result_data[sheet_name] = []
    
    # Создаем объект FBData
    fb_data = FBData(result_data)
    print(f"✅ Создан объект FBData")
    print(f"   - Controls: {len(fb_data.controls)}")
    print(f"   - Statuses: {len(fb_data.statuses)}") 
    print(f"   - Settings: {len(fb_data.settings)}")
    print(f"   - Устройство: {fb_data.info.russian_name}")

    Logger.info(f"Создан объект FBData")
    Logger.info(f"   - Controls: {len(fb_data.controls)}")
    Logger.info(f"   - Statuses: {len(fb_data.statuses)}") 
    Logger.info(f"   - Settings: {len(fb_data.settings)}")
    Logger.info(f"   - Устройство: {fb_data.info.russian_name}")

    return fb_data

def convert_xlsx_to_dict(xlsx_path: str) -> Dict[str, Any]:
    """
    Конвертирует XLSX файл в словарь (если нужны сырые данные)
    Возвращает: словарь с данными
    """
    target_sheets = ["Controls", "Status information", "Settings", "TechInfo"]
    result_data = {}
    
    for sheet_name in target_sheets:
        try:
            if sheet_name == "TechInfo":
                df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=1)
                result_data[sheet_name] = parse_tech_info_sheet(df)
            else:
                df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=1)

                # Добавляем недостающие столбцы
                for col in ['reserved1', 'reserved2', 'Logger', 'Disturber', 'StartDisturber']:
                    if col not in df.columns:
                        df[col] = np.nan

                # Заменяем "null" на np.nan
                df = df.replace("null", np.nan)

                # Убедимся, что все нужные столбцы присутствуют
                for col in REQUIRED_COLUMNS:
                    if col not in df.columns:
                        df[col] = np.nan

                # Преобразуем типы
                for col, dtype in COLUMN_DTYPES.items():
                    if col not in df.columns:
                        continue

                    if dtype in ('float64', 'Int64'):
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        df[col] = df[col].astype(dtype)
                    elif dtype == 'string':
                        df[col] = df[col].astype('string')

                # Ручная замена NaN на None
                data = []
                for _, row in df[REQUIRED_COLUMNS].iterrows():
                    record = {}
                    for col in REQUIRED_COLUMNS:
                        value = row[col]
                        
                        if pd.isna(value):
                            record[col] = None
                        else:
                            record[col] = value
                    
                    data.append(record)
                
                result_data[sheet_name] = data
                print(f"✅ Обработан лист: {sheet_name} ({len(data)} строк)")
                Logger.info(f"Обработан лист: {sheet_name} ({len(data)} строк)")
            
        except Exception as e:
            print(f"⚠️ Ошибка при обработке листа {sheet_name}: {e}")
            Logger.error(f"Ошибка при обработке листа {sheet_name}: {e}")
            result_data[sheet_name] = []
    
    return result_data

# Композитная функция для полного workflow
def process_device_xlsx(xlsx_path: str, device_name: str = None, save_to_storage: bool = True):
    """
    Полный процесс: XLSX -> FBData -> Сохранение (опционально)
    """
    # Конвертируем XLSX в FBData
    fb_data = convert_xlsx_to_fbdata(xlsx_path)
    
    # Автоматически определяем имя устройства если не указано
    if device_name is None:
        device_name = fb_data.info.iec61850_name or Path(xlsx_path).stem
        print(f"📝 Используется имя устройства: {device_name}")
        Logger.info(f"Используется имя устройства: {device_name}")
    
    # Сохраняем в хранилище если нужно
    if save_to_storage:
        from core.SQLiteFBDataManager import SQLiteFBDataManager  # ваш менеджер хранилища
        storage = SQLiteFBDataManager()
        storage.save_fb_data(fb_data)
        print(f"💾 Объект сохранен в базу данных под именем: {device_name}")
        Logger.info(f"Объект сохранен в базу данных под именем: {device_name}")
    
    return fb_data



def process_all_xlsx_files(folder_path="db"):
    """Обрабатывает все XLSX файлы в указанной папке"""
    db_folder = Path(folder_path)
    
    if not db_folder.exists():
        print(f"❌ Папка не существует: {db_folder.absolute()}")
        Logger.error(f"Папка не существует: {db_folder.absolute()}")
        return
    
    xlsx_files = list(db_folder.glob("*.xlsx"))
    
    if not xlsx_files:
        print(f"❌ В папке '{folder_path}' не найдено XLSX файлов")
        Logger.warning(f"В папке '{folder_path}' не найдено XLSX файлов")
        return
    
    print(f"📂 Найдено {len(xlsx_files)} XLSX файлов:")
    Logger.info(f"Найдено {len(xlsx_files)} XLSX файлов:")
    for i, file in enumerate(xlsx_files, 1):
        print(f"   {i}. {file.name}")
        Logger.info(f"   {i}. {file.name}")
    
    results = []
    
    for xlsx_file in xlsx_files:
        try:
            print(f"\n{'='*60}")
            print(f"🔄 Обработка: {xlsx_file.name}")
            Logger.info(f"Обработка: {xlsx_file.name}")
            
            # Обрабатываем файл
            fb_data = process_device_xlsx(str(xlsx_file))
            
            if fb_data:
                device_name = getattr(fb_data.info, 'russian_name', None) or \
                                getattr(fb_data.info, 'iec61850_name', None) or \
                                xlsx_file.stem
                
                results.append({
                    'file': xlsx_file.name,
                    'device_name': device_name,
                    'status': 'success',
                    'controls': len(fb_data.controls),
                    'statuses': len(fb_data.statuses),
                    'settings': len(fb_data.settings)
                })
                
                print(f"✅ Успешно: {device_name}")
                print(f"   📊 Controls: {len(fb_data.controls)}")
                print(f"   📊 Statuses: {len(fb_data.statuses)}")
                print(f"   📊 Settings: {len(fb_data.settings)}")

                Logger.info(f" Успешно: {device_name}")
                Logger.info(f"    Controls: {len(fb_data.controls)}")
                Logger.info(f"    Statuses: {len(fb_data.statuses)}")
                Logger.info(f"    Settings: {len(fb_data.settings)}")


            else:
                results.append({
                    'file': xlsx_file.name,
                    'device_name': None,
                    'status': 'error',
                    'error': 'Не удалось создать FBData'
                })
                print(f"❌ Ошибка обработки")
                Logger.error(f"Ошибка обработки")
                
        except Exception as e:
            results.append({
                'file': xlsx_file.name,
                'device_name': None,
                'status': 'error',
                'error': str(e)
            })
            print(f"❌ Критическая ошибка: {e}")
            Logger.error(f"Критическая ошибка: {e}")
    
    # Вывод итоговой статистики
    print(f"\n{'='*60}")
    print("📊 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"{'='*60}")

    Logger.info("ИТОГОВАЯ СТАТИСТИКА:")

    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'error']
    
    print(f"✅ Успешно обработано: {len(successful)}")
    print(f"❌ Ошибок: {len(failed)}")

    Logger.info(f"Успешно обработано: {len(successful)}")
    Logger.info(f"Ошибок: {len(failed)}")


    if successful:
        print(f"\n📋 Успешные устройства:")
        Logger.info(f"Успешные устройства:")
        for result in successful:
            print(f"   📁 {result['file']} → 🏷️ {result['device_name']}")
            print(f"      Controls: {result['controls']}, Statuses: {result['statuses']}, Settings: {result['settings']}")

            Logger.info(f"   {result['file']} -> {result['device_name']}")
            Logger.info(f"      Controls: {result['controls']}, Statuses: {result['statuses']}, Settings: {result['settings']}")            
    
    if failed:
        print(f"\n❌ Файлы с ошибками:")
        Logger.info(f"Файлы с ошибками:")
        for result in failed:
            print(f"   📁 {result['file']}: {result.get('error', 'Unknown error')}")
            Logger.info(f"   {result['file']}: {result.get('error', 'Unknown error')}")
    
    # Показываем содержимое базы
    manager = SQLiteFBDataManager()
    devices_in_db = manager.get_all_device_names()
    
    print(f"\n💾 База данных:")
    print(f"   Всего устройств в базе: {len(devices_in_db)}")

    Logger.info(f"\n База данных:")
    Logger.info(f"   Всего устройств в базе: {len(devices_in_db)}")

    if devices_in_db:
        for device in devices_in_db:
            print(f"   - {device}")
            Logger.info(f"   - {device}")
    
    return results

# Запуск
if __name__ == "__main__":

    # Запускаем обработку
    process_all_xlsx_files("db")