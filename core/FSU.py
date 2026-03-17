import re
import html
from core.SQLiteFBDataManager import SQLiteFBDataManager
from core.FSUManager import FSUManager

from logger.logger import Logger
from utils.general import format_status 

class FSU:
    def __init__(self, db_path="fbdata.db", fsu_type = ''):
        self.db_path = db_path
        self.fsu_type = fsu_type
        self.fbs = []

        self.manager = SQLiteFBDataManager(self.db_path)
        self.fsu_manager = FSUManager()
        self.fb_list = self.fsu_manager.get_fbs_by_fsu_type(fsu_type)
        #self.fb_list = get_fbs_by_fsu_type(fsu_type)
        for fb_name in self.fb_list:
            obj = self.manager.load_fb_data(fb_name)
            self.fbs.append(obj)

        self.merged_fbs = self._merge_fbs_by_settings() # ФУНКЦИЯ ОБЪЕДИНЕНИЯ ФБ и Функ для блака уставок DOCX - (из -за кривости АРНТ!)

        self.all_fbs_in_db = [] # для всех ФБ

        all_names = self.manager.get_all_device_names()
        for name in all_names:
            obj = self.manager.load_fb_data(name)
            self.all_fbs_in_db.append(obj)        


        #for fb in self.fbs:
            #print(fb.info.russian_name)
            #print(fb.info.get_function_names())
            #for name in fb.info.get_function_names():
                #n = fb.get_func_description_by_name(name)
                #t = fb.get_parameters_for_setting_table(name)
                #if t:
                    #print(name, n,  ' >>> ',fb.get_parameters_for_setting_table(name))



    ###################################################################################
    ################################## WORD ###########################################
    ###################################################################################

    # ФУНКЦИЯ ОБЪЕДИНЕНИЯ ФБ и Функ для блака уставок DOCX - (из -за кривости АРНТ!)
    def _merge_fbs_by_settings(self):
        """
        Объединяет self.fbs по (russian_name, description_fb).
        Для каждой функции собирает ВСЕ уставки из всех экземпляров.
        Возвращает список словарей.
        """
        merged = {}

        for fb in self.fbs:
            key = (fb.info.russian_name, fb.info.description_fb)
            if key not in merged:
                merged[key] = {
                    "russian_name": fb.info.russian_name,
                    "description_fb": fb.info.description_fb,
                    "functions": {}  # func_name -> {description, settings: []}
                }

            # Получаем все функции у этого ФБ
            try:
                func_names = fb.info.get_function_names()
            except AttributeError:
                continue  # если метода нет

            for func_name in func_names:
                settings = fb.get_parameters_for_setting_table(func_name)
                if not settings:
                    continue

                # Получаем описание функции
                func_desc = fb.get_func_description_by_name(func_name) or func_name

                if func_name not in merged[key]["functions"]:
                    merged[key]["functions"][func_name] = {
                        "description": func_desc,
                        "settings": []
                    }
                else:
                    # Описание можно оставить первое (или проверить, что совпадает)
                    pass

                # Уникальность по имени уставки (второй элемент кортежа)
                existing_names = {s[1] for s in merged[key]["functions"][func_name]["settings"]}
                for s in settings:
                    if s[1] not in existing_names:
                        merged[key]["functions"][func_name]["settings"].append(s)
                        existing_names.add(s[1])

        # Преобразуем в список для удобства в шаблоне
        result = []
        for data in merged.values():
            func_list = []
            for name, func_data in data["functions"].items():
                if func_data["settings"]:
                    func_list.append({
                        "name": name,
                        "description": func_data["description"],
                        "settings": func_data["settings"]
                    })
            if func_list:
                result.append({
                    "russian_name": data["russian_name"],
                    "description_fb": data["description_fb"],
                    "functions": func_list
                })
        #print(result)
        return result


    def _natural_sort_key(self, s):
        """
        Ключ для естественной сортировки строк с числами
        """
        return [int(text) if text.isdigit() else text.lower()
                for text in re.split(r'(\d+)', s)]

    # Возврат 
    def get_statuses(self):
        statuses = []
        for fb in self.fbs:
            #print(fb.get_all_statuses())
            for status in fb.get_all_statuses():
                if status.type == 'BOOL':
                    full_desc = status.full_description #.replace('<<', '«').replace('>>','»')
                    short_desc = status.short_description #.replace('<<', '«').replace('>>','»')
                    statuses.append([html.escape(fb.info.russian_name +' / '+ status.node_name_rus + ': '+ full_desc), html.escape(short_desc)])
                    #print(fb.info.russian_name +' / '+ status.node_name_rus + ': '+ status.full_description, status.short_description )
                #statuses.append(fb.get_all_statuses())
        return statuses

    def get_controls(self):
        controls_buttons = []
        controls_keys = []
        for fb in self.fbs:
            for control in fb.get_all_controls():
                if control.type == 'BOOL' and control.reserved1 == "button":
                    full_desc = control.full_description #.replace('<<', '«').replace('>>','»')
                    short_desc = control.short_description #.replace('<<', '«').replace('>>','»')
                    controls_buttons.append([full_desc, short_desc])
                else:
                    full_desc = control.full_description #.replace('<<', '«').replace('>>','»')
                    short_desc = control.short_description #.replace('<<', '«').replace('>>','»')
                    controls_keys.append([full_desc, short_desc])                        

        result_buttons = list({item[0]: item for item in controls_buttons}.values()) # sorted(list({item[0]: item for item in controls_buttons}.values()), key=lambda x: self._natural_sort_key(x[0]))
        result_keys = list({item[0]: item for item in controls_keys}.values()) # sorted(list({item[0]: item for item in controls_keys}.values()), key=lambda x: self._natural_sort_key(x[0]))
        return result_buttons+result_keys

    def get_inputs(self):
        inputs = []
        for fb in self.fbs:
            for input in fb.get_all_inputs():

                if input.type == 'BOOL':
                    full_desc = input.full_description #.replace('<<', '«').replace('>>','»')
                    short_desc =input.short_description #.replace('<<', '«').replace('>>','»')
                    inputs.append([full_desc, short_desc])

        unique_inputs = list({item[0]: item for item in inputs}.values())
        #unique_inputs = sorted(unique_inputs, key=lambda x: self._natural_sort_key(x[0]))
        return unique_inputs

    def has_any_setting(self):
        """Возвращает true если в ФСУ есть какие либо уставки"""
        for fb in self.fbs:
            if fb.has_any_setting():
                return True
        return False    



    ###################################################################################
    ################################## LATEX ###########################################
    ####################################################################################

    def get_controls_for_latex(self):
        controls_buttons = []
        controls_keys = []
        for fb in self.fbs:
            for control in fb.get_all_controls():
                full_desc = control.full_description #.replace('<<', '«').replace('>>','»')
                short_desc = control.short_description #.replace('<<', '«').replace('>>','»')
                digital_input = format_status(control.digital_input)
                digital_output = format_status(control.digital_output)
                led = format_status(control.led)
                functional_button = format_status(control.functional_button)
                logger = format_status(control.logger)
                disturber = format_status(control.disturber)
                start_disturber = format_status(control.start_disturber)

                statuses = [
                    digital_input, digital_output, led, 
                    functional_button, logger, disturber, start_disturber
                ]
                if any(status == '?' for status in statuses):
                    Logger.error(f"Обнаружены значения '?' в статусах! {full_desc}")


                if control.type == 'BOOL' and control.reserved1 == "button":
                    controls_buttons.append([full_desc, short_desc, digital_input, digital_output, led, functional_button, logger, disturber, start_disturber])
                else:
                    controls_keys.append([full_desc, short_desc, digital_input, digital_output, led, functional_button, logger, disturber, start_disturber])                        

        result_buttons = list({item[0]: item for item in controls_buttons}.values()) # sorted(list({item[0]: item for item in controls_buttons}.values()), key=lambda x: self._natural_sort_key(x[0]))
        result_keys = list({item[0]: item for item in controls_keys}.values()) # sorted(list({item[0]: item for item in controls_keys}.values()), key=lambda x: self._natural_sort_key(x[0]))
        return ({'buttons':result_buttons, 'keys':result_keys})


    def get_statuses_for_latexOLD(self): # Работает без пересекающихся функциональных блоков , обновленная функция пересобирает блоки из отрывком (как в АРНТ)
        fbs_statuses = []
        for fb in self.fbs:
            # Получаем статусы сгруппированные по функциям
            grouped_statuses = fb.get_statuses_grouped_by_function()
            #print(fb.info.russian_name, fb.info.description_fb, grouped_statuses)
            fb_status_data = {
                "description_fb": fb.info.description_fb, 
                "russian_name": fb.info.russian_name,
                "statuses_by_function": [],
                "funcs_count":len(grouped_statuses)
            }
            
            # Обрабатываем статусы для каждой функции
            for func_name, func_data in grouped_statuses.items():
                func_statuses = []
                func_description = func_data["description"]
                
                for status in func_data["statuses"]:
                    if status.type == 'BOOL':
                        full_desc = status.full_description.replace('_','\_') #.replace('<<', '«').replace('>>','»').replace('_','\_')
                        short_desc = status.short_description.replace('_','\_') #.replace('<<', '«').replace('>>','»').replace('_','\_')
                        digital_input = format_status(status.digital_input)
                        digital_output = format_status(status.digital_output)
                        led = format_status(status.led)
                        functional_button = format_status(status.functional_button)
                        logger = format_status(status.logger)
                        disturber = format_status(status.disturber)
                        start_disturber = format_status(status.start_disturber)

                        func_statuses.append([
                            full_desc, short_desc, digital_input, digital_output, 
                            led, functional_button, logger, disturber, start_disturber
                        ])
                
                # Добавляем статусы для текущей функции
                if func_statuses:
                    fb_status_data["statuses_by_function"].append({
                        "function_name": func_name.replace('_','\_'),
                        "function_description": func_description.replace('_','\_'),
                        "statuses": func_statuses
                    })
            
            fbs_statuses.append(fb_status_data)   
        
        return fbs_statuses


    def get_statuses_for_latex(self):
        # Первый проход: объединяем ФБ по (russian_name, description_fb)
        merged_fbs = {}

        for fb in self.fbs:
            key = (fb.info.russian_name, fb.info.description_fb)
            grouped_statuses = fb.get_statuses_grouped_by_function()

            if key not in merged_fbs:
                merged_fbs[key] = {
                    "description_fb": fb.info.description_fb,
                    "russian_name": fb.info.russian_name,
                    "functions": {}  # будет содержать func_name -> {description, statuses}
                }

            # Объединяем функции
            for func_name, func_data in grouped_statuses.items():
                if func_name not in merged_fbs[key]["functions"]:
                    merged_fbs[key]["functions"][func_name] = {
                        "description": func_data["description"],
                        "statuses": []
                    }
                # Добавляем статусы в существующую или новую функцию
                merged_fbs[key]["functions"][func_name]["statuses"].extend(func_data["statuses"])

        # Второй проход: формируем итоговый список для LaTeX
        fbs_statuses = []
        for key, merged_data in merged_fbs.items():
            fb_status_data = {
                "description_fb": merged_data["description_fb"],
                "russian_name": merged_data["russian_name"],
                "statuses_by_function": [],
                "funcs_count": len(merged_data["functions"])
            }

            for func_name, func_data in merged_data["functions"].items():
                func_statuses = []
                func_description = func_data["description"]

                for status in func_data["statuses"]:
                    if status.type == 'BOOL':
                        full_desc = status.full_description.replace('_', r'\_') # .replace('<<', '«').replace('>>', '»').replace('_', r'\_')
                        short_desc = status.short_description.replace('_', r'\_') #  .replace('<<', '«').replace('>>', '»').replace('_', r'\_')
                        digital_input = format_status(status.digital_input)
                        digital_output = format_status(status.digital_output)
                        led = format_status(status.led)
                        functional_button = format_status(status.functional_button)
                        logger = format_status(status.logger)
                        disturber = format_status(status.disturber)
                        start_disturber = format_status(status.start_disturber)

                        statuses_for_test = [
                            digital_input, digital_output, led, 
                            functional_button, logger, disturber, start_disturber
                        ]
                        if any(status == '?' for status in statuses_for_test):
                            Logger.error(f"Обнаружены значения '?' в статусах: {func_name} / {func_description}")


                        func_statuses.append([
                            full_desc, short_desc, digital_input, digital_output,
                            led, functional_button, logger, disturber, start_disturber
                        ])

                if func_statuses:
                    fb_status_data["statuses_by_function"].append({
                        "function_name": func_name.replace('_', r'\_'),
                        "function_description": func_description.replace('_', r'\_'),
                        "statuses": func_statuses
                    })

            fbs_statuses.append(fb_status_data)

        return fbs_statuses

    ###################################################################################
    # Разработана для М500
    # Генерация таблицы в формате LATEX для подраздела РЭ с выбором функции   
    def get_table_settings_latex(self, version, func_type, lib_path):
        print(version, func_type, lib_path)

        return None

    ######################################################################################

    def get_table_settings_latexOLD(self, func_iec_name, fb_iec_name):
        #print(func_iec_name, fb_iec_name)
        for fb in self.all_fbs_in_db: #self.fbs:
            if fb.info.iec61850_name == fb_iec_name:
                #print(fb.get_all_iec_names())
                for iec_name in fb.get_all_iec_names():
                    if iec_name == func_iec_name:
                        return fb.get_parameters_for_setting_table_latex(iec_name)
        return None




# Запуск
if __name__ == "__main__":
    fsu = FSU(fsu_type = "TEST")
    fsu.get_statuses()
    #for fb in fsu.fbs:
        #fb.print_summary()
        #if fb.info.russian_name == "КСВ":
            #print(fb.to_dict())
            #names = fb.get_all_iec_names()
            #print(names)
            #pars = fb.find_parameter_by_iecname("LLN0")
            #for par in pars:
                #print(par.name_geb)

    #fb = manager.load_fb_data("LVDIS")