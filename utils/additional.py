import os
from pathlib import Path
import shutil
import pickle

from logger.logger import Logger

def create_directories(base_path="."):
    """
    Удаляет существующую директорию latex_build (если есть), затем создаёт
    заново latex_build и latex_build/images в указанной базовой папке.
    """
    base_dir = Path(base_path)
    build_dir = base_dir / "latex_build"
    images_dir = build_dir / "images"
    obj_dir = build_dir / "obj"
    
    try:
        # Если директория latex_build существует — удаляем её и всё содержимое
        if build_dir.exists() and build_dir.is_dir():
            shutil.rmtree(build_dir)
            Logger.info(f"Удалена существующая директория: {build_dir.absolute()}")

        # Создаём заново (с поддиректорией images)
        images_dir.mkdir(parents=True, exist_ok=False)  # parents=True создаст и build_dir тоже
        obj_dir.mkdir(parents=True, exist_ok=False)
        Logger.info(f"Созданы новые директории:")
        Logger.info(f"  - {build_dir.absolute()}")
        Logger.info(f"  - {images_dir.absolute()}")
        Logger.info(f"  - {obj_dir.absolute()}")
        
        return True
    except Exception as e:
        Logger.error(f"Ошибка при обработке директорий: {e}")
        return False
    
def save_obj(obj):
    with open('latex_build/obj/object.pkl', 'wb') as file:
        pickle.dump(obj, file)

def load_obj():
    with open('latex_build/obj/object.pkl', 'rb') as file:
        return pickle.load(file)