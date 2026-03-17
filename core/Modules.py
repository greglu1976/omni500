# Класс представляющий объект модулей в составе устройства (часть железа)
import html

from core.SQLiteFBDataManager import SQLiteFBDataManager

from utils.general import format_status 

from logger.logger import Logger

class Modules:
    def __init__(self, db_path="fbdata.db", order_code=''):
        self.db_path = db_path
        self.module_names = self._parse_order_code(order_code)
        self.modules = []

        self.manager = SQLiteFBDataManager(self.db_path)

        count = 0
        for module_name in self.module_names:
            count += 1
            if module_name != 'х':
                obj = self.manager.load_fb_data(module_name)
                obj.set_slot_number(count)
                self.modules.append({
                    'obj': obj,
                    'slot_number': count,
                    'description': obj.info.description_fb,
                    'russian_name': obj.info.russian_name.split('.')[0]
                })

    def __getitem__(self, index):
        """Позволяет обращаться к modules как к списку"""
        return self.modules[index]

    def __len__(self):
        """Возвращает количество модулей"""
        return len(self.modules)

    def __iter__(self):
        """Позволяет итерироваться по модулям"""
        return iter(self.modules)

    def _parse_order_code(self, order_code):
        """Парсит order code и возвращает обработанный список модулей"""
        if not order_code:
            return []
            
        modules = order_code.split('-')
        length = len(modules)
        
        # Определяем сколько элементов отбросить слева и справа
        if length in (14, 18):
            # Отбрасываем 3 слева, 0 справа
            return modules[3:-1] if length >= 3 else modules
        elif length in (15, 19):
            # Отбрасываем 3 слева, 1 справа
            return modules[3:-2] if length >= 4 else modules
        else:
            # Для других длин возвращаем как есть или пустой список
            return modules

    def get_statuses(self):
        """Возвращает статусы всех модулей"""
        statuses = []
        statuses_dropdown = []
        
        for module in self.modules:
            module_obj = module['obj']
            slot_number = module['slot_number']
            description = module['description']
            russian_name = module['russian_name']
            
            for status in module_obj.get_all_statuses():
                if status.type == 'BOOL':
                    full_desc = status.full_description #.replace('<<', '«').replace('>>', '»')
                    short_desc = status.short_description #.replace('<<', '«').replace('>>', '»')
                    
                    status_text = f"Слот М{slot_number}. {description} ({russian_name}): {full_desc}"
                    dropdown_text = f"Слот М{slot_number}. {description} ({russian_name}): {short_desc}"
                    
                    statuses.append([status_text, short_desc])
                    statuses_dropdown.append(html.escape(dropdown_text))
        
        return statuses_dropdown

    def get_modules_all_inputs(self):
        """Возвращает информацию о всех входах модулей"""
        result = []
        
        for module in self.modules:
            module_obj = module['obj']
            slot_number = module['slot_number']
            description = module['description']
            russian_name = module['russian_name']
            
            # Получаем количество входов из первого элемента description_func_list
            if hasattr(module_obj.info, 'description_func_list') and module_obj.info.description_func_list:
                inputs_count = module_obj.info.description_func_list[0].get("Входы", 0)
                
                if inputs_count != 0:
                    module_text = f"Слот М{slot_number}. {description} ({russian_name})"
                    result.append((module_text, inputs_count))
        
        return result

    def get_modules_binary_inputs(self):
        """Возвращает информацию о дискретных входах модулей"""
        result = []
        
        for module in self.modules:
            module_obj = module['obj']
            slot_number = module['slot_number']
            description = module['description']
            russian_name = module['russian_name']
            if 'М' in russian_name or 'А' in russian_name:
                continue
            
            # Получаем количество входов из первого элемента description_func_list
            if hasattr(module_obj.info, 'description_func_list') and module_obj.info.description_func_list:
                inputs_count = module_obj.info.description_func_list[0].get("Входы", 0)
                
                if inputs_count != 0:
                    module_text = f"Слот М{slot_number}. {description} ({russian_name})"
                    result.append((module_text, inputs_count))
        
        return result

    def get_modules_all_outputs(self):
        """Возвращает информацию о всех выходах модулей"""
        result = []
        
        for module in self.modules:
            module_obj = module['obj']
            slot_number = module['slot_number']
            description = module['description']
            russian_name = module['russian_name']
            
            # Получаем количество выходов из первого элемента description_func_list
            if hasattr(module_obj.info, 'description_func_list') and module_obj.info.description_func_list:
                outputs_count = module_obj.info.description_func_list[0].get("Выходы", 0)
                
                if outputs_count != 0:
                    module_text = f"Слот М{slot_number}. {description} ({russian_name})"
                    result.append((module_text, outputs_count))
        
        return result

    def get_modules_binary_outputs(self):
        """Возвращает информацию о дискретных выходах модулей"""
        result = []
        
        for module in self.modules:
            module_obj = module['obj']
            slot_number = module['slot_number']
            description = module['description']
            russian_name = module['russian_name']
            if 'М' in russian_name:
                continue

            # Получаем количество выходов из первого элемента description_func_list
            if hasattr(module_obj.info, 'description_func_list') and module_obj.info.description_func_list:
                outputs_count = module_obj.info.description_func_list[0].get("Выходы", 0)
                
                if outputs_count != 0:
                    module_text = f"Слот М{slot_number}. {description} ({russian_name})"
                    result.append((module_text, outputs_count))
        
        return result


    def get_modules(self):
        """Возвращает список всех модулей"""
        return self.modules

    def get_module_by_slot(self, slot_number):
        """Возвращает модуль по номеру слота"""
        for module in self.modules:
            if module['slot_number'] == slot_number:
                return module
        return None

    def get_module_descriptions(self):
        """Возвращает список описаний всех модулей"""
        return [
            f"Слот М{module['slot_number']}: {module['description']} ({module['russian_name']})"
            for module in self.modules
        ]


    ##############################################################################
    ############################ LATEX ##########################################
    #############################################################################

    def get_statuses_for_latex_sum_table(self):
        """Возвращает статусы всех модулей для РЭ latex (суммарная таблица) в списке """
        
        result_list = []
        
        for module in self.modules:
            module_obj = module['obj']
            slot_number = module['slot_number']
            description = module['description']
            russian_name = module['russian_name']

            statuses = []
            for status in module_obj.get_all_statuses():
                if status.type == 'BOOL':
                    full_desc = status.full_description
                    short_desc_temp = status.short_description.replace('<<', r'\verb|<<|').replace('>>', r'\verb|>>|')
                    node_name = 'Общие сигналы' if status.node_name_rus=='Модуль' else status.node_name_rus # v0.5.1hf1                   
                    short_desc = f"Слот М{slot_number}. {node_name}. {short_desc_temp}" # v0.5.1hf1
                    digital_input = format_status(status.digital_input)
                    digital_output = format_status(status.digital_output)
                    led = format_status(status.led)
                    fk = format_status(status.functional_button)
                    logger = format_status(status.logger)
                    disturber = format_status(status.disturber)
                    start_disturber = format_status(status.start_disturber)

                    statuses_for_test = [
                        digital_input, digital_output, led, 
                        fk, logger, disturber, start_disturber
                    ]
                    #print(statuses_for_test)
                    if any(status == '?' for status in statuses_for_test):
                        Logger.error(f"Обнаружены значения '?' в статусах! {full_desc}")

                    statuses.append([full_desc, short_desc, digital_input, digital_output, led, fk, logger, disturber, start_disturber])

            # Добавляем словарь для каждого модуля в список
            module_dict = {
                'module': f'Слот М{slot_number}. {description} ({russian_name})',
                'statuses': statuses
            }
            result_list.append(module_dict)

        return result_list
