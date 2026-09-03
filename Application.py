import dearpygui.dearpygui as dpg

import gui.themes as themes

from logger.logger import Logger

from core.Device import Device
from core.DeviceDataManager import DeviceDataManager
from core.SettingBlanc2 import SettingBlanc

from core.Manual import Manual

from core.LatexDoc import LatexDoc
from utils.additional import create_directories, save_obj, load_obj
from utils.arranger import start_arrange

from core.CabDwgProcessor import CabDwgProcessor

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
        
        # Переменная для хранения режима таблиц уставок
        self.settings_table_mode = 1  # 1 - без общего описания, 2 - с общим описанием
        
        self.setup_gui()

        self.load_config_callback()

        
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
        with dpg.window(label="Главное окно", width=400, height=520):
           
            # Сохраняем идентификатор комбобокса
            self.device_combo = dpg.add_combo(
                label="Устройство",
                items=[],
                width=300,
                enabled=False,
                callback=self.on_device_selected
            )
            dpg.add_spacer(height=5)

            # Сохраняем идентификатор кнопки
            #self.init_button = dpg.add_button(
                #label="Инициализировать устройство",
                #callback=self.start_device_task,
                #enabled=False,
                #width=300
            #)

            dpg.add_separator() 
            dpg.add_spacer(height=5)
            
            # Добавляем радиокнопки для выбора режима
            dpg.add_text("Режим генерации таблиц уставок:")
            dpg.add_radio_button(
                items=["Без общего описания", "С общим описанием"],
                default_value=0,  # По умолчанию выбран первый вариант
                callback=self.settings_mode_callback,
                tag="settings_mode_radio",
                horizontal=True
            )
            dpg.add_spacer(height=5)
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
            dpg.add_button(label="Ранжировать приложение с уставками", callback=self.arrange, width=300)  
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
                label="Обновить приложения РЭ ШЭТ",
                callback=self.update_appx_shet,
                width=300
            )

            dpg.add_spacer(height=5)
            dpg.add_separator() 
            dpg.add_spacer(height=5) 


            dpg.add_button(
                label="Собрать в один файл latex (raw.tex)",
                callback=self.gen_raw_latex,
                width=300
            )

        # Окно логов
        with dpg.window(label="Логи", width=800, height=400, pos=[400, 0], tag="log_window"):
            with dpg.child_window(tag="log_container", height=325):
                dpg.add_group(tag="log_content")  # для добавления строк

        Logger.set_container("log_content", "log_window")
        
        dpg.create_viewport(title="OMNI-500 v.0.0.10  02.09.26", width=1215, height=600)
        dpg.setup_dearpygui()


    #################################### CALLBACKS ######################################

    def on_device_selected(self, sender, app_data):
        """Обработчик выбора устройства из комбобокса"""
        # Сбрасываем старые данные устройства при выборе нового
        self.device_data = None
        self.device = None
        #Logger.info(f"Выбрано новое устройство. Данные будут загружены при необходимости.")
        if app_data:
            # Извлекаем имя устройства из строки вида "Устройство: XXX, Версия: YYY"
            try:
                # Разбиваем строку по запятой и берем первую часть
                device_name_part = app_data.split(',')[0]  # "Устройство: XXX"
                device_name = device_name_part.split(':')[1].strip()  # "XXX"
                Logger.info(f"Выбрано новое устройство: {device_name}")
            except:
                Logger.info(f"Выбрано новое устройство: {app_data}")
        else:
            Logger.info("Выбор устройства сброшен")      
        # Можно сразу загрузить данные нового устройства
        #self.init_device_data()


    def settings_mode_callback(self, sender, app_data):
        """Обработчик изменения режима таблиц уставок"""
        # app_data - это строка с текстом выбранного элемента
        if app_data == "Без общего описания":
            self.settings_table_mode = 1
            mode_name = "без общего описания"
        else:  # "С общим описанием"
            self.settings_table_mode = 2
            mode_name = "с общим описанием"
        Logger.info(f"Выбран режим таблиц уставок: {mode_name}")

    def renew_abbrs_ru(self):
        if not self.is_device_selected():
            Logger.warning('Устройство не выбрано')
            return          
        if self.device_data is None:
            self.init_device_data()   
        else:
            manual = Manual(device_data=self.device_data)
            if manual.renew_abbrs_ru()==0:
                Logger.info('Перечень сокращений в РУ обновлен')
            else:
                Logger.error('При обновлении перечня сокращений РУ возникли ошибки')               


##########################################################################################################
    def renew_abbrs(self):
        if not self.is_device_selected():
            Logger.warning('Устройство не выбрано')
            return          
        if self.device_data is None:
            self.init_device_data()        
        manual = Manual(device_data=self.device_data)
        manual.renew_abbrs()
        Logger.info('Перечень сокращений в РЭ обновлен')
############################################################################################################

    def generate_setting_blanc_docx(self):
        if not self.is_device_selected():
            Logger.warning('Устройство не выбрано')
            return        
        if self.device_data is None:
            self.init_device_data()
        Logger.info('Начинаем создавать бланк уставок в формате word...')
        setting_blanc = SettingBlanc(device_data=self.device_data)
        setting_blanc.get_blanc(mode=self.settings_table_mode)
        #Logger.info('Бланк уставок в docx создан')


################################################################################################
    def renew_setting_tables_re(self):
        if not self.is_device_selected():
            Logger.warning('Устройство не выбрано')
            return
        if self.device_data is None:
            self.init_device_data()
        
        # Передаем режим в метод renew_setting_tables_re
        manual = Manual(device_data=self.device_data)
        manual.renew_setting_tables_re(mode=self.settings_table_mode)
        
        mode_text = "без общего описания" if self.settings_table_mode == 1 else "с общим описанием"
        Logger.info(f'Таблицы с уставками в РЭ обновлены (режим: {mode_text})')
#################################################################################################

    def renew_sum_table_latex(self):
        if not self.is_device_selected():
            Logger.warning('Устройство не выбрано')
            return        
        if self.device_data is None:
            self.init_device_data()
        manual = Manual(device_data=self.device_data)
        manual.renew_sum_table_latex()
        Logger.info('Суммарная таблица сигналов приложения в РЭ обновлена')

#####################################################################################################


    def update_appx_shet(self):
        if not self.is_device_selected():
            Logger.warning('Устройство не выбрано')
            return        
        if self.device_data is None:
            self.init_device_data()        
        appx = CabDwgProcessor()
        appx.run(self.device_data["path_to_latex_desc"])


#####################################################################################################

    def arrange(self):
        if not self.is_device_selected():
            Logger.warning('Устройство не выбрано')
            return        
        if self.device_data is None:
            self.init_device_data()
        path_to_general_tex = self.device_data["path_to_latex_desc"] + "/_manual_latex/general.tex"
        path_to_appset_tex = self.device_data["path_to_latex_desc"] + "/Приложение. Уставки/_latex/appset.tex"
        start_arrange(path_to_general_tex, path_to_appset_tex)     
        Logger.info('Ранжирование выполнено...')

        
#####################################################################################################
    def gen_raw_latex(self):

        Logger.info('Создание единого файл latex')
        Logger.warning('Не обрабатывает циклы latex, например в приложении ФСУ. Нужно доработать...')

        if not self.is_device_selected():
            Logger.warning('Устройство не выбрано')
            return
        if self.device_data is None:
            self.init_device_data()

        create_directories()
        # Сохраняем в файл объект РЭ
        #save_obj(self.re_)

        path =self.device_data["path_to_latex_desc"] + '/_manual_latex'

        LatexDoc(path)
        Logger.info('Проект latex для РЭ создан. См. папку latex_build')        
        #process_all_xlsx_files("db")
        #Logger.info('Задача обновления БД завершена')

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
            #dpg.configure_item(self.init_button, enabled=True)
            Logger.info("Конфигурация загружена успешно")
        else:
            Logger.warning("Устройства не найдены в конфигурации")
        #else:
            #Logger.error("Ошибка загрузки конфигурации")

    def start_device_task(self):
        """Запуск задачи устройства"""
        self.init_device_data()
        self.create_device()

    def init_device_data(self):

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
        self.device_displayed = display_to_device_map.get(selected_text)
        if self.device_displayed is None:
            Logger.error("Выбранное устройство не найдено в конфигурации")
            return

        Logger.info(f"Выбрано устройство: {self.device_displayed['name']} v{self.device_displayed['version']}")

        # Получаем данные устройства
        self.device_data = self.device_data_manager.get_device_by_name_and_version(
            name=self.device_displayed['name'], 
            version=self.device_displayed['version']
        )
        
        if not self.device_data:
            Logger.error(f"Не удалось получить данные для устройства {self.device_displayed['name']} v{self.device_displayed['version']}")
            return False


    def create_device(self):

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
            
            Logger.info(f"Устройство: {self.device_displayed['name']} v{self.device_displayed['version']} успешно инициализировано")
            return True



    def is_device_selected(self):
        """Проверяет, выбрано ли устройство и инициализированы ли его данные"""
        # Проверяем, что в комбобоксе что-то выбрано
        selected_text = dpg.get_value(self.device_combo)
        if not selected_text:
            return False
        return True

    def run(self):
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()