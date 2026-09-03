import configparser
import os
from core.CabDwgProcessor import CabDwgProcessor

from pathlib import Path

from logger.logger import Logger
Logger.set_mode('console')
Logger.enable_file_logging("log.txt")  # Включаем файл


# 1. Читаем конфиг
config = configparser.ConfigParser()
config.read('cabinets.cfg', encoding='utf-8')

path = Path(config['GENERAL']['PATH'])
mode = config['CABINETS']['MODE'].lower()
names_list = [n.strip() for n in config['CABINETS']['NAMES'].split(',') if n.strip()]

# 2. Получаем все папки с "ШЭТ" в имени
all_cabs = [f for f in os.listdir(path) 
            if os.path.isdir(os.path.join(path, f)) and "ШЭТ" in f]

# 3. Функция поиска папок по номеру
def find_cabinets_by_numbers(numbers, folders):
    result = []
    for num in numbers:
        for folder in folders:
            if folder.startswith(num + '.') or folder.startswith(num + ' '):
                result.append(folder)
                break
    return result


def process_cabinet(cab_path):
    print(f"Обработка: {cab_path}")
    
    doc_dir = cab_path / "Документация"
    if not doc_dir.exists():
        print(f"❌ Папка Документация не найдена: {doc_dir}")
        return
    
    dwg_files = list(doc_dir.glob("*.dwg"))
    if not dwg_files:
        print(f"❌ DWG файлы не найдены в: {doc_dir}")
        return
    
    print(f"✅ Найден DWG: {dwg_files[0].name}")
    
    appx = CabDwgProcessor()
    appx.run(str(cab_path))


# 4. Определяем целевые шкафы
if mode == 'all':
    target = all_cabs
elif mode == 'except':
    excluded = find_cabinets_by_numbers(names_list, all_cabs)
    target = [c for c in all_cabs if c not in excluded]
else:  # list
    target = find_cabinets_by_numbers(names_list, all_cabs)

#processor = CabDwgProcessor()

# 5. Обрабатываем
for cab in target:
    base_path = path / cab
    print(f"Обработка: {cab}")
    process_cabinet(base_path)