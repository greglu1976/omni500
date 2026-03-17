# Класс представляющий объект вспомогательных функций служебных модулей в составе устройства (Регистрация, Синхронизация, Модуль ЦП)

from core.SQLiteFBDataManager import SQLiteFBDataManager


class AuxFuncs:
    def __init__(self, db_path="fbdata.db", aux_funcs = ["Синхр", "МодульЦП", "Регистр"]):
        self.db_path = db_path

        self.aux_funcs = []

        self.manager = SQLiteFBDataManager(self.db_path)

        for aux_func in aux_funcs:
            obj = self.manager.load_fb_data(aux_func)
            self.aux_funcs.append(obj)

    def get_config_sync(self):
        for func in self.aux_funcs:
            if func.info.russian_name == "Синхр":
                result = {
                    "Общие параметры": func.get_parameters_for_setting_table("Общие уставки"),
                    "Параметры летнего времени": func.get_parameters_for_setting_table("Параметры летнего времени"),
                    "Параметры зимнего времени": func.get_parameters_for_setting_table("Параметры зимнего времени"),
                }
                return result
        return None

    def get_config_cpu(self):
        for func in self.aux_funcs:
            if func.info.russian_name == "МодульЦП":
                result = {
                    "Резервирование": func.get_parameters_for_setting_table("Резервирование"),
                }
                return result
        return None

    def get_config_disturb(self):
        for func in self.aux_funcs:
            if func.info.russian_name == "Регистр":
                result = {
                    "Общие уставки": func.get_parameters_for_setting_table("Общие уставки"),
                }
                return result
        return None        