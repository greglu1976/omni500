# logger/logger.py
import time
from datetime import datetime

class Logger:
    # Цвета для GUI
    TEXT_COLORS = {
        "INFO": (80, 80, 80, 255),
        "SUCCESS": (0, 200, 0, 255),    # Зеленый
        "WARNING": (0, 100, 255, 255),
        "ERROR": (255, 0, 0, 255),
        "DEBUG": (100, 100, 100, 255)
    }
    
    # Режим работы: 'console', 'gui' или 'file'
    mode = 'gui'
    
    # Настройки файла
    log_file_path = None
    log_file_enabled = False
    
    log_container = None
    log_window = None
    
    visible_levels = {
        "INFO": True,
        "SUCCESS": True,
        "WARNING": True,
        "ERROR": True,
        "DEBUG": False
    }
    
    @classmethod
    def set_mode(cls, mode):
        """Установить режим: 'console', 'gui' или 'file'"""
        cls.mode = mode
    
    @classmethod
    def set_container(cls, container_tag, window_tag):
        cls.log_container = container_tag
        cls.log_window = window_tag
        cls.mode = 'gui'
    
    @classmethod
    def enable_file_logging(cls, file_path=None):
        """Включить логирование в файл"""
        if file_path is None:
            # По умолчанию создаем файл с датой
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"log_{timestamp}.txt"
        
        cls.log_file_path = file_path
        cls.log_file_enabled = True
        
        # Создаем файл с заголовком
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"=== ЛОГ НАЧАТ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write("=" * 60 + "\n\n")
    
    @classmethod
    def disable_file_logging(cls):
        """Отключить логирование в файл"""
        cls.log_file_enabled = False
    
    @classmethod
    def info(cls, message):
        cls._add_log("INFO", message)
    
    @classmethod
    def success(cls, message):
        cls._add_log("SUCCESS", message)
    
    @classmethod
    def warning(cls, message):
        cls._add_log("WARNING", message)
    
    @classmethod
    def error(cls, message):
        cls._add_log("ERROR", message)

    @classmethod
    def debug(cls, message):
        cls._add_log("DEBUG", message)

    @classmethod
    def _add_log(cls, level, message):
        # Проверяем видимость уровня лога
        if not cls.visible_levels.get(level, True):
            return  # Не выводим ничего, если уровень скрыт
        
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        
        # === ВЫВОД В КОНСОЛЬ ===
        if cls.mode == 'console':
            if level == "ERROR":
                print(f"\033[91m{formatted}\033[0m")
            elif level == "WARNING":
                print(f"\033[93m{formatted}\033[0m")
            elif level == "SUCCESS":
                print(f"\033[92m{formatted}\033[0m")
            elif level == "DEBUG":
                print(f"\033[90m{formatted}\033[0m")
            else:
                print(formatted)
        
        # === ВЫВОД В GUI ===
        elif cls.mode == 'gui':
            if cls.log_container:
                try:
                    import dearpygui.dearpygui as dpg
                    dpg.add_text(
                        formatted,
                        color=cls.TEXT_COLORS[level],
                        parent="log_content"
                    )
                    dpg.set_y_scroll("log_container", -1.0)
                except:
                    print(formatted)
        
        # === ВЫВОД В ФАЙЛ ===
        if cls.log_file_enabled and cls.log_file_path:
            try:
                full_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                file_formatted = f"[{full_timestamp}] [{level}] {message}"
                with open(cls.log_file_path, 'a', encoding='utf-8') as f:
                    f.write(file_formatted + "\n")
            except Exception as e:
                print(f"[ERROR] Не удалось записать в файл лога: {e}")

    @classmethod
    def refresh_display(cls):
        if cls.mode == 'gui' and cls.log_container:
            try:
                import dearpygui.dearpygui as dpg
                dpg.delete_item(cls.log_container, children_only=True)
            except:
                pass
    
    @classmethod
    def set_search_filter(cls, text):
        pass
    
    @classmethod
    def clear_logs(cls):
        if cls.mode == 'gui' and cls.log_container:
            try:
                import dearpygui.dearpygui as dpg
                dpg.delete_item(cls.log_container, children_only=True)
            except:
                pass
    
    @classmethod
    def save_logs_to_file(cls, file_path=None):
        """Сохранить текущие логи в файл (если нет активного файлового лога)"""
        pass