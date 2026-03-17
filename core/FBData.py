from typing import List, Optional, Dict, Any
import html

class BaseRecord:
    """Базовый класс для записей с методами"""
    def __init__(self, data: Dict[str, Any]):
        self.category = data.get("Категория (group)")
        self.node_name_rus = data.get("NodeName (рус)")
        self.full_description = data.get("FullDescription (Описание параметра для пояснения в ПО ЮНИТ Сервис)")
        self.short_description = data.get("ShortDescription")
        self.applied_description = data.get("AppliedDescription")
        self.note = data.get("Note (Справочная информация)")
        self.name_geb = data.get("Name GEB")
        self.type = data.get("type")
        self.units = data.get("units")
        self.min_value = data.get("minValue")
        self.max_value = data.get("maxValue")
        self.step = data.get("step")
        self.default_value = data.get("DefaultValue")
        self.ieс61850_type_ln = data.get("61850_TypeLN")
        self.ieс61850_data_object_name = data.get("61850_DataObjectName")
        self.ieс61850_common_data_class = data.get("61850_CommonDataClass")
        self.ieс61850_attribute_name = data.get("61850_AttributeName")
        self.ieс61850_enum_data_type = data.get("61850_EnumDAType")
        self.ieс61850_fc = data.get("61850_FC")
        self.digital_input = data.get("DigitalInput")
        self.digital_output = data.get("DigitalOutput")
        self.functional_button = data.get("FunctionalButton")
        self.led = data.get("LED")
        self.logger = data.get("Logger")
        self.disturber = data.get("Disturber")
        self.start_disturber = data.get("StartDisturber")
        self.reserved1 = data.get("reserved1")
        self.reserved2 = data.get("reserved2")

    def is_digital_input(self) -> bool:
        """Проверяет, является ли цифровым входом"""
        return self.digital_input == 1

    def is_digital_output(self) -> bool:
        """Проверяет, является ли цифровым выходом"""
        return self.digital_output == 1

    def has_led(self) -> bool:
        """Проверяет, есть ли светодиод"""
        return self.led == 1

    def is_loggable(self) -> bool:
        """Проверяет, логируется ли параметр"""
        return self.logger == 1

    def get_description(self) -> str:
        """Возвращает описание параметра"""
        return self.full_description or self.short_description or ""

class TechInfo:
    """Класс для TechInfo с методами"""
    def __init__(self, data: Dict[str, Any]):
        self.russian_name = data.get("RussianName")
        self.weight_coefficient = data.get("WeightCoefficient")
        self.is_coded = data.get("IsCoded")
        self.iec61850_name = data.get("IEC61850Name")
        self.fb_version = data.get("FbVersion")
        self.description_fb = data.get("DescriptionFB")
        
        self.description_func_list = []
        func_list_data = data.get("DescriptionFuncList", [])
        for func_data in func_list_data:
            self.description_func_list.append(func_data)

    def get_function_names(self) -> List[str]:
        """Возвращает список названий функций"""
        names = []
        for func in self.description_func_list:
            names.extend(list(func.keys()))
        return names

class FBData:
    """Основной класс с бизнес-логикой"""
    def __init__(self, data: Dict[str, Any]):
        self.controls = [BaseRecord(item) for item in data.get("Controls", [])]
        self.statuses = [BaseRecord(item) for item in data.get("Status information", [])]
        self.settings = [BaseRecord(item) for item in data.get("Settings", [])]
        self.info = TechInfo(data.get("TechInfo", {}))
        self.slot_number = None

    # 🔧 МЕТОДЫ ДЛЯ РАБОТЫ С ДАННЫМИ

    def get_all_controls(self) -> List[BaseRecord]:
        """Возвращает все сигналы управления"""
        return [item for item in self.controls if item.category == "control"]

    def get_all_statuses(self) -> List[BaseRecord]:
        """Возвращает все сигналы статуса"""
        return [item for item in self.statuses if item.category == "status"]

    def get_all_inputs(self) -> List[BaseRecord]:
        """Возвращает все сигналы дискретных входов"""
        return [item for item in self.controls if item.category == "input"]

    def find_parameter_by_nodename(self, name: str) -> Optional[BaseRecord]:
        """Находит параметр по NodeName (рус)"""
        all_items = self.controls + self.statuses + self.settings
        return [item for item in all_items if item.node_name_rus == name]

    def find_parameter_by_iecname(self, name: str) -> Optional[BaseRecord]: # ПРОВЕРИТЬ РАБОТОСПОСОБНОСТЬ с LLN0
        """Находит параметр по iec name обработанный столбец Name GEB"""
        all_items = self.statuses + self.settings
        if name == "LLN0":
            return [item for item in all_items if len(item.name_geb.split('_')) == 1]
        return [item for item in all_items if item.name_geb.split('_')[0] == name]

    def get_all_settings(self) -> List[BaseRecord]:
        """Возвращает все уставки"""
        return [item for item in self.settings if item.category == "setting"]

    def get_all_iec_names(self) -> List[str]:
        """Возвращает список имен всех функций по iec"""
        all_items = self.statuses + self.settings
        iec_names = []
        for item in all_items:
            iec_name = self._extract_iec_name(item.name_geb)
            iec_names.append(iec_name)
        return list(set(iec_names))  # Уникальные значения

    def _extract_iec_name(self, name_geb: str) -> str:
        """Извлекает IEC имя из name_geb"""
        if not name_geb:
            return "LLN0"
        #if len(name_geb.split('_')) == 1:
            #return 'LLN0'
        else:
            return name_geb.split('_')[0]

    def get_settings_by_iec_name(self, iec_name: str) -> List[BaseRecord]:
        """Возвращает уставки по имени IEC функции"""
        settings = []
        for item in self.settings:
            if item.category == "setting":
                # Извлекаем IEC имя из name_geb
                item_iec_name = self._extract_iec_name(item.name_geb)
                if item_iec_name == iec_name:
                    settings.append(item)
        return settings

    def get_digital_inputs(self) -> List[BaseRecord]:
        """Возвращает все цифровые входы"""
        return [item for item in self.controls if item.is_digital_input()]

    def get_digital_outputs(self) -> List[BaseRecord]:
        """Возвращает все цифровые выходы"""
        all_items = self.controls + self.statuses
        return [item for item in all_items if item.is_digital_output()]

    def get_parameters_with_leds(self) -> List[BaseRecord]:
        """Возвращает параметры со светодиодами"""
        all_items = self.controls + self.statuses
        return [item for item in all_items if item.has_led()]

    def get_loggable_parameters(self) -> List[BaseRecord]:
        """Возвращает параметры для логирования"""
        all_items = self.controls + self.statuses
        return [item for item in all_items if item.is_loggable()]

    def get_parameters_by_category(self, category: str) -> List[BaseRecord]:
        """Возвращает параметры по категории"""
        all_items = self.controls + self.statuses + self.settings
        return [item for item in all_items if item.category == category]

    def get_parameters_by_type(self, param_type: str) -> List[BaseRecord]:
        """Возвращает параметры по типу (BOOL, FLOAT32, etc)"""
        all_items = self.controls + self.statuses + self.settings
        return [item for item in all_items if item.type == param_type]

    def find_parameter_by_name(self, name: str) -> Optional[BaseRecord]:
        """Находит параметр по Name GEB"""
        all_items = self.controls + self.statuses + self.settings
        for item in all_items:
            if item.name_geb == name:
                return item
        return None

    def find_parameters_by_description(self, search_text: str) -> List[BaseRecord]:
        """Находит параметры по тексту в описании"""
        all_items = self.controls + self.statuses + self.settings
        search_text = search_text.lower()
        return [
            item for item in all_items
            if item.get_description().lower().find(search_text) != -1
        ]

    def get_61850_mappings(self) -> List[BaseRecord]:
        """Возвращает параметры с маппингом на 61850"""
        all_items = self.controls + self.statuses + self.settings
        return [item for item in all_items if item.ieс61850_type_ln is not None]

    # 📊 МЕТОДЫ ДЛЯ АНАЛИТИКИ

    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по устройству"""
        return {
            "total_controls": len(self.controls),
            "total_status": len(self.statuses),
            "total_settings": len(self.settings),
            "digital_inputs": len(self.get_digital_inputs()),
            "digital_outputs": len(self.get_digital_outputs()),
            "parameters_with_leds": len(self.get_parameters_with_leds()),
            "loggable_parameters": len(self.get_loggable_parameters()),
            "61850_mappings": len(self.get_61850_mappings()),
        }

    def print_summary(self):
        """Выводит сводку по устройству"""
        stats = self.get_statistics()
        print(f"📊 Устройство: {self.info.russian_name}")
        print(f"   Controls: {stats['total_controls']}")
        print(f"   Status: {stats['total_status']}")
        print(f"   Settings: {stats['total_settings']}")
        print(f"   Цифровые входы: {stats['digital_inputs']}")
        print(f"   Цифровые выходы: {stats['digital_outputs']}")
        print(f"   Параметры с LED: {stats['parameters_with_leds']}")
        print(f"   Логируемые параметры: {stats['loggable_parameters']}")

    # 💾 СЕРИАЛИЗАЦИЯ

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует обратно в словарь (для JSON)"""
        return {
            "Controls": [item.__dict__ for item in self.controls],
            "Status information": [item.__dict__ for item in self.statuses],
            "Settings": [item.__dict__ for item in self.settings],
            "TechInfo": self.info.__dict__
        }

    ########################################################
    # 🔧 МЕТОДЫ ВЫСОКОГО УРОВНЯ ДЛЯ БЛАНКА УСТАВОК DOCX 🔧#
    ########################################################

    def _parse_enum_string_simple(self, enum_str: str, default_value: int = 0) -> tuple:

        #print(enum_str)
        """Парсит строку перечисления (простая версия)"""
        if not enum_str:
            return "", ""
        
        enum_str = enum_str.replace('–', '-')

        # Разделяем по запятым, но только те, за которыми следует " цифра - "
        parts = []
        current_part = ""
        
        for i, char in enumerate(enum_str):
            if char == ',' and i + 3 < len(enum_str):
                # Проверяем, идет ли после запятой шаблон " цифра - "
                next_part = enum_str[i+1:i+4].strip()
                if next_part and next_part[0].isdigit() and ' - ' in enum_str[i+1:]:
                    parts.append(current_part.strip())
                    current_part = ""
                else:
                    current_part += char
            else:
                current_part += char
        
        # Добавляем последнюю часть
        if current_part:
            parts.append(current_part.strip())
        
        # Если не удалось разделить по сложному алгоритму, используем простой
        if len(parts) <= 1:
            parts = enum_str.split(', ')
        
        descriptions = []
        value_dict = {}
        
        for part in parts:
            if ' - ' in part:
                value, description = part.split(' - ', 1)
                try:
                    value_int = int(value.strip())
                    desc_clean = description.strip()
                    value_dict[value_int] = desc_clean
                    descriptions.append(desc_clean)
                except ValueError:
                    continue

        all_descriptions = '\n'.join(f"{k} = {v}" for k, v in sorted(value_dict.items()))        
        #all_descriptions = '\n '.join(descriptions)
        #print('value_dict', value_dict, 'default_value', default_value)
        default_description = value_dict.get(default_value, "")
        #print(all_descriptions)
        #print( '>', enum_str, '>>', all_descriptions, '>>>', default_description, '<<<')
        return all_descriptions, default_description

    def _format_by_step(self, value: float, step: float) -> str:
        """Форматирует одно значение с учетом шага"""
        if value is None:
            return '-'
        if step is None:
            return str(value)
        if step.is_integer():
            return str(int(value))
        decimals = len(str(step).split('.')[1])
        return f"{value:.{decimals}f}"

    def get_parameters_for_setting_table(self, name):
        if name not in self.info.get_function_names():
            return None
        params = [item for item in self.settings if item.node_name_rus == name]
        if not params:
            return None
        params_list = []
        for par in params:
            #applied_desc = par.applied_description or '-'  
            if par.reserved2 and 'Del' in par.reserved2: # убираем строку с Del в поле reserved2
               continue

            is_symbol = False
            if par.units == "Символ" or par.units == "символ":
                is_symbol = True

            full_desc = html.escape(par.full_description) #.replace('<<', '«').replace('>>','»')
            short_desc =  html.escape(par.short_description) #.replace('<<', '«').replace('>>','»')

            # Переводим мс в секунды
            units = par.units
            step = par.step
            default_value_num = par.default_value
            min_value = par.min_value
            max_value = par.max_value
            if units == 'мс':
                units = 'с'
                step = par.step / 1000
                default_value_num = par.default_value / 1000
                min_value = par.min_value / 1000
                max_value = par.max_value / 1000

            # Форматированное значение для отображения
            default_value_formatted = self._format_by_step(default_value_num, step)
            # Для enum передаем ЧИСЛОВОЕ значение
            default_value_for_enum = int(default_value_num) if default_value_num is not None else 0
            note = self._parse_enum_string_simple(par.note, int(default_value_for_enum))

            # Выбираем значение по умолчанию: либо из enum, либо форматированное
            default_value_display = html.escape(note[1]) if par.note else default_value_formatted

            #default_value = self._format_by_step(default_value, step)
            #default_value = self._format_by_step(par.default_value, par.step)
            #note = self._parse_enum_string_simple(par.note, default_value)
            #note = self._parse_enum_string_simple(par.note, par.default_value)

            # Применяем html.escape чтобы заэкранировать <> в ЗИЧ есть например
            #default_value = html.escape(note[1]) if par.note else default_value
            #znach_diap = html.escape(note[0]) if par.note else (self._format_by_step(par.min_value, par.step)).replace('.',',') + ' ... ' + (self._format_by_step(par.max_value, par.step)).replace('.',',')
            znach_diap = html.escape(note[0]) if par.note else (self._format_by_step(min_value, step)).replace('.',',') + ' ... ' + (self._format_by_step(max_value, step)).replace('.',',')
            units = units or '-'
            if is_symbol:
                units = '-'
            #step = str(int(float(par.step))) if par.step and float(par.step).is_integer() else str(par.step)                
            step = str(int(float(step))) if step and float(step).is_integer() else str(step)
            step = step if (not par.note and not is_symbol) else '-'
            znach_diap = znach_diap if not is_symbol else f'Строка из {znach_diap} символов'
            params_list.append((full_desc, short_desc, znach_diap, units, step.replace('.',','), default_value_display.replace('.',',')))

        return params_list

    def get_func_description_by_name(self, name: str) -> str:
        if name not in self.info.get_function_names():
            return None
        
        for func in self.info.description_func_list:
            if name in func.keys():
                return func[name]
        return None

    def has_any_setting(self):
        """Возвращает true если в ФБ есть какие либо уставки"""
        for func_name in self.info.get_function_names():
            settings = self.get_parameters_for_setting_table(func_name)
            if settings:
                return True
        return False    

    def get_functions_with_settings(self):
        """Возвращает список функций, у которых есть настройки"""
        result = []
        for func_name in self.info.get_function_names():
            settings = self.get_parameters_for_setting_table(func_name)
            if settings:
                count =len(self.info.get_function_names()) # чтобы отличить ФБ с одной функцией и не писать общие уставки (например ЗДЗ/ЗДЗ)
                func_name_to_append = func_name
                # Определяем, нужно ли переименовать в "Общие уставки"
                #if count == 1 or func_name == self.info.russian_name:
                    #display_name = 'Общие уставки'
                #else:
                    #display_name = func_name
                #print(display_name, self.get_func_description_by_name(func_name))
                result.append({
                    'name': func_name if (func_name != self.info.russian_name or count==1) else 'Общие уставки',
                    #'name': display_name,
                    'description': self.get_func_description_by_name(func_name),
                    'settings': settings
                })
        return result

    def get_settings_for_configuration_docx_table(self):
        """Возвращает словарь для таблицы раздела конфигурация модулей с группировкой по категориям"""
        result = {
            "Общие настройки конфигурации": [],
            "Входы": [],
            "Выходы": []
        }
        
        for func_name in self.info.get_function_names():
            settings = self.get_parameters_for_setting_table(func_name)
            if not settings:
                continue

            if self.slot_number is not None and any(keyword in func_name for keyword in ['ДВ', 'Реле']):
                updated_settings = [
                    (param[0], f'Слот М{self.slot_number}. {func_name}. {param[1]}', *param[2:])
                    for param in settings
                ]
            else:
                updated_settings = settings

            settings = updated_settings

            func_description = self.get_func_description_by_name(func_name)
            
            # Определяем категорию по названию функции
            if func_name == "Общие настройки конфигурации":
                category = "Общие настройки конфигурации"
            elif "ДВ" in func_name or "дискретный вход" in func_description.lower() or "вход" in func_description.lower():
                category = "Входы"
            elif "Реле" in func_name or "реле" in func_description.lower() or "выход" in func_description.lower():
                category = "Выходы"
            else:
                # Если не удалось определить категорию, пропускаем или добавляем в общие
                category = "Общие настройки конфигурации"
            
            # Добавляем данные в соответствующую категорию
            result[category].append({
                'name': func_name,
                'description': func_description,
                'settings': settings
            })
        
        return result

    ########################################################
    # 🔧 МЕТОДЫ ВЫСОКОГО УРОВНЯ ДЛЯ РУКОВОДСТВА LATEX 🔧#
    ########################################################

    def get_statuses_by_func_name(self, func_name: str = None) -> List[BaseRecord]:
        """Возвращает статусы по имени функции"""
        all_statuses = self.get_all_statuses()
        
        if not func_name:
            return all_statuses
        
        # Фильтруем статусы по имени функции в node_name_rus
        filtered_statuses = []
        for status in all_statuses:
            # Проверяем, относится ли статус к указанной функции
            if status.node_name_rus == func_name:
                filtered_statuses.append(status)
        
        return filtered_statuses

    def get_statuses_grouped_by_function(self) -> Dict[str, List[BaseRecord]]:
        """Возвращает статусы сгруппированные по функциям"""
        all_statuses = self.get_all_statuses()
        grouped_statuses = {}
        
        for status in all_statuses:
            if status.type!='BOOL':
                continue
            func_name = status.node_name_rus
            #print(status.node_name_rus, func_name)
            
            if func_name not in grouped_statuses:
                func_description = self.get_func_description_by_name(func_name) or ""
                grouped_statuses[func_name] = {
                    "description": func_description,
                    "statuses": []
                }
            
            grouped_statuses[func_name]["statuses"].append(status)
        return grouped_statuses


    # Генерация таблицы в формате LATEX для подраздела РЭ с выбором функции   
    def get_parameters_for_setting_table_latex(self, iec_name):
        if iec_name not in self.get_all_iec_names():
            return None
        params = self.get_settings_by_iec_name(iec_name)
        #print(params)
        if not params:
            return None
        params_list = []
        for par in params:
            #print(par)
            if par.reserved2 and 'Del' in par.reserved2: # убираем строку с Del в поле reserved2
               continue

            is_symbol = False
            if par.units == "Символ" or par.units == "символ":
                is_symbol = True

            full_desc = par.full_description
            short_desc = par.short_description.replace('<<', r'\verb|<<|').replace('>>', r'\verb|>>|')
            applied_desc = par.applied_description.replace('<<', r'\verb|<<|').replace('>>', r'\verb|>>|') if par.applied_description else '-'

            # Переводим мс в секунды
            units = par.units
            step = par.step
            default_value = par.default_value
            min_value = par.min_value
            max_value = par.max_value
            if units == 'мс':
                units = 'с'
                step = par.step / 1000
                default_value = par.default_value / 1000
                min_value = par.min_value / 1000
                max_value = par.max_value / 1000

            #default_value = self._format_by_step(par.default_value, par.step)
            default_value = self._format_by_step(default_value, step)
            #note = self._parse_enum_string_simple(par.note, par.default_value)
            note = self._parse_enum_string_simple(par.note, default_value)

            # Применяем html.escape чтобы заэкранировать <> в ЗИЧ есть например
            default_value = html.escape(note[1]) if par.note else default_value
            #znach_diap = html.escape(note[0]) if par.note else (self._format_by_step(par.min_value, par.step)).replace('.',',') + ' ... ' + (self._format_by_step(par.max_value, par.step)).replace('.',',')
            znach_diap = html.escape(note[0]) if par.note else (self._format_by_step(min_value, step)).replace('.',',') + ' ... ' + (self._format_by_step(max_value, step)).replace('.',',')
            #units = par.units or '-'
            units = units or '-'
            if is_symbol:
                units = '-'
            #step = str(int(float(par.step))) if par.step and float(par.step).is_integer() else str(par.step)                
            step = str(int(float(step))) if step and float(step).is_integer() else str(step)
            step = step if (not par.note and not is_symbol) else '-'
            znach_diap = znach_diap if not is_symbol else f'Строка из {znach_diap} символов'
            params_list.append((f'{full_desc} ({short_desc})', applied_desc, znach_diap, units, step.replace('.',','), default_value.replace('.',',')))

        return params_list

    def set_slot_number(self, slot_number):
        self.slot_number = slot_number


if __name__ == "__main__":
    pass
