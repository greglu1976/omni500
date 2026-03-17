import dearpygui.dearpygui as dpg
import time

# Класс Logger для демонстрации
class Logger:
    # Цвета текста (R, G, B, A)
    TEXT_COLORS = {
        "INFO": (80, 80, 80, 255),  # Белый (обычный текст)
        "WARNING": (0, 100, 255, 255),   # Синий (новый цвет для WARNING)
        "ERROR": (255, 0, 0, 255)  # Красный
    }

    COLORS = {
        "INFO": (100, 200, 255),
        "WARNING": (255, 255, 100),
        "ERROR": (255, 100, 100)
    }
    
    visible_levels = {
        "INFO": True,
        "WARNING": True,
        "ERROR": True
    }
    
    log_container = None
    log_window = None
    
    @classmethod
    def set_container(cls, container_tag, window_tag):
        cls.log_container = container_tag
        cls.log_window = window_tag
    
    @classmethod
    def info(cls, message):
        cls._add_log("INFO", message)
    
    @classmethod
    def warning(cls, message):
        cls._add_log("WARNING", message)
    
    @classmethod
    def error(cls, message):
        cls._add_log("ERROR", message)
    
    @classmethod
    def _add_log(cls, level, message):
        if cls.visible_levels.get(level, True):
            timestamp = time.strftime("%H:%M:%S")
            dpg.add_text(
                f"[{timestamp}] [{level}] {message}",
                color=cls.TEXT_COLORS[level],
                parent="log_content"  # добавляем в группу
            )

            # Прокручиваем родительское child_window
            dpg.set_y_scroll("log_container", -1.0)


    @classmethod
    def refresh_display(cls):
        dpg.delete_item(cls.log_container, children_only=True)
    
    @classmethod
    def set_search_filter(cls, text):
        pass  # Реализуйте поиск при необходимости
    
    @classmethod
    def clear_logs(cls):
        dpg.delete_item(cls.log_container, children_only=True)
    
    @classmethod
    def save_logs_to_file(cls):
        pass  # Реализуйте сохранение в файл при необходимости
