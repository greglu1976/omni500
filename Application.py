import dearpygui.dearpygui as dpg

import gui.themes as themes

from logger.logger import Logger

from core.Device import Device
from core.DeviceDataManager import DeviceDataManager
from core.SettingBlanc import SettingBlanc

from core.Manual import Manual

from utils.xlsx2fbdata import process_all_xlsx_files

class Application:
    def __init__(self):

        self.device = None
        self.device_data = None

        self.device_data_manager = DeviceDataManager()
        self.devices_data = self.device_data_manager.get_all_devices()

        # Создаём список строк для отображения
        self.display_names = [
            f"Устройство: {device['name']}, Версия: {device['version']}"
            for device in self.devices_data
        ]

        self.init_button = None  # Будет хранить идентификатор кнопки
        self.setup_gui()

        self.load_config_callback()


        self.re_ = None # УДАЛИТЬ ПОТОМ
        self.sum_table_type = 2  # По умолчанию выбран тип 2
        
    def setup_gui(self):
        dpg.create_context()

        # Подключаем светлую тему
        light_theme = themes.create_theme_imgui_light()
        dpg.bind_theme(light_theme)        
        # Настройка шрифтов
        with dpg.font_registry():
            default_font = dpg.add_font("gui/Montserrat-Regular.ttf", 15)
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic, parent=default_font)
        dpg.bind_font(default_font)
        

        # Главное окно
        with dpg.window(label="Главное окно", width=400, height=450):
           
            # Сохраняем идентификатор комбобокса
            self.device_combo = dpg.add_combo(
                label="Устройство",
                items=[],
                width=300,
                enabled=False
            )
            dpg.add_spacer(height=5)

            # Сохраняем идентификатор кнопки
            self.init_button = dpg.add_button(
                label="Инициализировать устройство",
                callback=self.start_device_task,
                enabled=False,
                width=300
            )

            dpg.add_separator() 
            dpg.add_spacer(height=5)             
            dpg.add_button(label="Создать бланк уставок в docx", callback=self.generate_setting_blanc_docx, width=300)
            dpg.add_spacer(height=5)
            dpg.add_separator() 
            dpg.add_spacer(height=5)           
            dpg.add_button(label="Обновить таблицы с уставками в РЭ", callback=self.renew_setting_tables_re, width=300)
            dpg.add_button(label="Обновить таблицу сигналов в РЭ", callback=self.renew_sum_table_latex, width=300)
            dpg.add_button(label="Обновить перечень сокращений в РЭ", callback=self.renew_abbrs, width=300)            
            dpg.add_spacer(height=5)   
            dpg.add_separator()
            dpg.add_spacer(height=5)   

            dpg.add_button(label="Обновить перечень сокращений в РУ", callback=self.renew_abbrs_ru, width=300)
            dpg.add_spacer(height=5)
            dpg.add_separator() 
            dpg.add_spacer(height=5)  
            dpg.add_button(label="Очистить логи", callback=Logger.clear_logs, width=300)

            dpg.add_button(
                label="Перезагрузить config.ini",
                callback=self.load_config_callback,
                width=300
            )

            dpg.add_spacer(height=5)
            dpg.add_separator() 
            dpg.add_spacer(height=5) 

            dpg.add_button(
                label="Занести xlsx из папки db в базу SQLite",
                callback=self.add_to_sqlite,
                width=300
            )

        # Окно логов
        with dpg.window(label="Логи", width=800, height=400, pos=[400, 0], tag="log_window"):
            with dpg.child_window(tag="log_container", height=325):
                dpg.add_group(tag="log_content")  # для добавления строк

        Logger.set_container("log_content", "log_window")
        
        dpg.create_viewport(title="Omni-500 v0.0.1 05.12.25", width=1215, height=450)
        dpg.setup_dearpygui()

    def renew_abbrs_ru(self):
        if self.device is None:
            Logger.error('Устройство не инициализировано!')
        else:
            manual = Manual(device_data=self.device_data)
            if manual.renew_abbrs_ru()==0:
                Logger.info('Перечень сокращений в РУ обновлен')
            else:
                Logger.error('При обновлении перечня сокращений РУ возникли ошибки')               

    def renew_abbrs(self):
        if self.device is None:
            Logger.error('Устройство не инициализировано!')
        else:
            manual = Manual(device_data=self.device_data)
            manual.renew_abbrs()
            Logger.info('Перечень сокращений в РЭ обновлен')

    def generate_setting_blanc_docx(self):
        if self.device is None:
            Logger.error('Устройство не инициализировано!')
        else:
            Logger.info('Начинаем создавать бланк уставок...')
            setting_blanc = SettingBlanc(code=self.device_data["setting_blanc_code"], versions=self.device_data["versions"])
            setting_blanc.get_blanc(device=self.device)
            #Logger.info('Бланк уставок в docx создан')

    def renew_setting_tables_re(self):
        if self.device is None:
            Logger.error('Устройство не инициализировано!')
        else:
            manual = Manual(device_data=self.device_data)
            manual.renew_setting_tables_re()
            Logger.info('Таблицы с уставками в РЭ обновлены')

    def renew_sum_table_latex(self):
        if self.device is None:
            Logger.error('Устройство не инициализировано!')
        else:
            manual = Manual(device_data=self.device_data)
            manual.renew_sum_table_latex(self.device)
            #self.re_.renew_sum_table_latex(table_type=self.sum_table_type)
            #Logger.info('Суммарная таблица сигналов приложения в РЭ обновлена')

    def add_to_sqlite(self):
        Logger.info('Запуск задачи обновления БД')
        process_all_xlsx_files("db")
        Logger.info('Задача обновления БД завершена')

#######################################################################
######################################################################

    def load_config_callback(self):
        """Обработчик загрузки конфига"""
        #if self.device_manager.load_config():
        #devices = self.device_manager.get_device_names()
        #devices = self.device_names_with_versions
        devices = self.display_names
        if devices:
            # Используем сохраненные идентификаторы
            dpg.configure_item(self.device_combo, items=devices, enabled=True)
            dpg.configure_item(self.init_button, enabled=True)
            Logger.info("Конфигурация загружена успешно")
        else:
            Logger.warning("Устройства не найдены в конфигурации")
        #else:
            #Logger.error("Ошибка загрузки конфигурации")

    def start_device_task(self):
        """Запуск задачи устройства"""

        selected_text = dpg.get_value(self.device_combo)

        if not selected_text:
            Logger.error("Устройство не выбрано")
            return

        # Создаем словарь для быстрого поиска
        display_to_device_map = {
            f"Устройство: {device['name']}, Версия: {device['version']}": device
            for device in self.devices_data
        }

        # Находим устройство по отображаемому тексту
        device = display_to_device_map.get(selected_text)
        if device is None:
            Logger.error("Выбранное устройство не найдено в конфигурации")
            return

        Logger.info(f"Выбрано устройство: {device['name']} v{device['version']}")

        try:
            # Получаем данные устройства
            self.device_data = self.device_data_manager.get_device_by_name_and_version(
                name=device['name'], 
                version=device['version']
            )
            
            if not self.device_data:
                Logger.error(f"Не удалось получить данные для устройства {device['name']} v{device['version']}")
                return False

            # Создаем устройство
            order_code = self.device_data["order_code"]
            full_description = self.device_data["full_description"]
            order_code_hmi = self.device_data["order_code_hmi"]
            
            self.device = Device(
                order_code=order_code, 
                full_description=full_description, 
                order_code_hmi=order_code_hmi
            )

            # Проверяем, что устройство успешно инициализировалось
            if self.device is None:
                Logger.error("Ошибка: устройство не было создано")
                return False
            
            # Дополнительные проверки (если есть в классе Device)
            if hasattr(self.device, 'is_initialized'):
                if not self.device.is_initialized:
                    Logger.error("Устройство создано, но не инициализировано корректно")
                    return False
            
            Logger.info(f"Устройство: {device['name']} v{device['version']} успешно инициализировано")
            return True

        except KeyError as e:
            Logger.error(f"Отсутствует обязательное поле в данных устройства: {e}")
            return False
        except Exception as e:
            Logger.error(f"Ошибка при создании устройства: {str(e)}")
            return False


    def run(self):
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()