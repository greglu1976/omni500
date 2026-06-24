# Класс, представляющий руководство по эксплуатации

import os
import re
import json
from pathlib import Path

from utils.abbrs import start_abbr
from logger.logger import Logger

from core.LIB500Manager import LIB500Manager
from core.FBData import FBData

class Manual:
    def __init__(self, device_data):
        self.device_data = device_data
        self.path_to_latex_desc = device_data["path_to_latex_desc"]
        self.path_to_ru_desc = device_data["path_to_ru_desc"]

        #self.path_to_json = device_data["path_to_json"]
        self.meta_manager = LIB500Manager(device_data["path_to_json"])

        self.paths = []

    def __find_fbpath(self, tex_file_path):
        with open(tex_file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line.startswith(r'\newcommand{\fbpath}'):
                    start = line.find('{', line.find('}') + 1) + 1
                    end = line.rfind('}')
                    fbpath = line[start:end]
                    return fbpath.replace('\\', '/')  # нормализуем слеши
        return None

    # Ищем пути к функциям из general.tex
    def _get_all_paths_from_general_tex(self):
        self.path_to_general_tex = Path(self.path_to_latex_desc) / "_manual_latex" / "general.tex"

        # === Шаг 1: Найти значение \fbpath ===
        fbpath = self.__find_fbpath(self.path_to_general_tex)
        if not fbpath:
            Logger.error("Ошибка: переменная \\fbpath не найдена в файле.")
        else:
            Logger.info("Найден путь \\fbpath:")
            Logger.info(fbpath)

            # === Шаг 2: Извлечь пути из блока %===f ===
            in_block = False

            with open(self.path_to_general_tex, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()

                    # Переключаем флаг при встрече %===f
                    if line.startswith('%===f'):
                        in_block = not in_block
                        continue

                    # Обрабатываем только внутри блока и не комментарии
                    if in_block and line.startswith(r'\input{\fbpath') and not line.startswith('%'):
                        # Извлекаем относительный путь
                        start = line.find('{') + 1
                        end = line.find('}')
                        relative_path = line[start:end]

                        # Формируем полный путь
                        full_path = os.path.normpath(relative_path.replace(r'\fbpath', fbpath))
                        self.paths.append(full_path)

            # === Вывод результата ===
            Logger.info("Список путей:")
            for p in self.paths:
                Logger.info(p)


    #########################################################
    ###### Метод для обновления таблиц уставок в РЭ #########
    #########################################################


    def _render_latex_settings_block(self, settings_data):
        table = []
        for data in settings_data:
            if data["MacroBlock"]!='-':
                head_latex = '\multicolumn{5}{|c|}{ ' + data["MacroBlock"].replace('_', r'\_') + ' } \\\\ \hline \n'
                table.append(head_latex)            
            for setting in data["Settings"]:
                str_ = '\\raggedright '
                str_ += str(setting["Name"])
                str_ += ' & \centering '
                str_ += str(setting["Description"])
                str_ += ' & \centering '
                if setting["PredefinedValues"]=='':
                    ############# Форматирование Min и Max к требуемому виду в РЭ ####################
                    Min=FBData._format_by_step(FBData,setting["Min"],setting["Step"]).replace('.',',') 
                    Max=FBData._format_by_step(FBData,setting["Max"],setting["Step"]).replace('.',',')
                    ##################################################################################
                    str_ += f'{str(Min)} ... {str(Max)}'
                    str_ += ' & \centering '
                    str_ += str(setting["Unit"])
                    str_ += ' & \centering \\arraybackslash '
                    str_ += str(setting["Step"]).replace('.',',')
                else:
                    str_ += str(setting["PredefinedValues"])
                    str_ += ' & \centering '
                    str_ += str("---")
                    str_ += ' & \centering \\arraybackslash '
                    str_ += str("---")
                str_ += ' \\\\\n'  # Закрываем строку таблицы и переносим строку
                table.append(str_)  # Добавляем строку таблицы
                table.append('\\hline\n')  # Добавляем \hline отдельным элементом
        return table


    ##########################################################################
    ############################ ДЛЯ М500 ####################################

    def _parse_start_tag(self, raw_tag):
        """
        Полный парсинг тега
        """
    
        parts = raw_tag[6:].split('|')
        
        if len(parts) not in (1, 2):
            raise ValueError(f"Неверный формат: {raw_tag}")
        
        # Если есть разделитель и после него что-то есть
        if len(parts) == 2:
            path_part = parts[0].strip()
            function_name = parts[1].strip() if parts[1].strip() else "-"
        else:
            # Если разделителя нет
            path_part = parts[0].strip()
            function_name = "-"

        return path_part, function_name


##########################################################################################


    def renew_setting_tables_re(self):
        start_tag_prefix = '%===m>'
        end_tag = '%===m\n'

        self._get_all_paths_from_general_tex() # Это список всех путей , если уставки в каждом разделе описания функций

        #self.paths.append("\\\\uni-eng.ru\\unit\\Ivanovo\\Документация ЮНИТ М300\\Разработка\\Схемы ФБ ЮНИТ-М300\\Проект\\РЭ500\\30. РЭ ЮНИТ-М500-ЛВ Уст\\Приложение. Уставки\\settings.tex")
        path_to_desc = self.device_data.get("path_to_latex_desc")
        if not path_to_desc:
            Logger.error("Error: path_to_latex_desc is empty or missing")
            return
        path_to_desc = path_to_desc.rstrip('/\\')   
        self.paths = [path_to_desc + "/Приложение. Уставки/settings.tex",] # Перезаписываем self.paths одной строкой пути к файлу settings в приложении Уставки

        for path in self.paths:
            if not os.path.exists(path):
                Logger.warning(f"Файл не найден: {path}")
                continue

            with open(path, 'r', encoding='utf-8') as f:
                content = f.readlines()

            new_content = []
            i = 0
            modified = False  # <-- Объявляем флаг здесь

            while i < len(content):
                line = content[i]

                if line.startswith(start_tag_prefix):
                    # Сохраняем начальный тег
                    start_line = line
                    new_content.append(start_line)

                    # Собираем старое содержимое до %===t1
                    old_block = []
                    i += 1
                    line = content[i]
                    #if line.startswith('%===t1*'):
                        # Сохраняем старый тег, если есть
                        #new_content.append(line)
                        #i += 1

                    while i < len(content):
                        current_line = content[i]
                        #if current_line.startswith('%===t1*'):
                            # Сохраняем старый тег %===t1*...
                            #old_block.append(current_line)
                            #i += 1                        
                        if current_line == end_tag:
                            break
                        else:
                            old_block.append(current_line)
                            i += 1

                    # Парсим тэг
                    lib_path, macroblock = self._parse_start_tag(start_line)

                    # Генерируем новое содержимое
                    latex_new = []

                    settings_data = self.meta_manager.get_table_latex(lib_path, macroblock)

                    if settings_data:
                        latex_new = self._render_latex_settings_block(settings_data)
                    else:
                        Logger.error(f"Не найдено уставок для ФБ: {lib_path}. МБ: {macroblock}")
                        latex_new = old_block

                    # Проверяем результат get_table_settings_latex
                    if not latex_new:  # None или пустой список
                        Logger.info("Новое содержимое не сгенерировано - оставляем старое.")
                        new_content.extend(old_block)
                        new_content.append(end_tag)
                    elif old_block != latex_new:
                        Logger.info("Контент отличается - будет обновлён.")
                        new_content.extend(latex_new)
                        new_content.append(end_tag)
                        modified = True  # <-- Теперь корректно
                    else:
                        Logger.info("Контент не изменился - пропускаем обновление.")
                        new_content.extend(old_block)
                        new_content.append(end_tag)

                    i += 1  # Пропускаем закрывающий тег после добавления

                else:
                    # Копируем остальные строки
                    new_content.append(line)
                    i += 1

            # Записываем только если были изменения
            if modified:
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(new_content)
                Logger.info(f"Файл обновлён: {path}")
            else:
                Logger.info(f"Изменений в файле нет: {path}")

    #########################################################
    # Метод для обновления суммарной таблицы сигналов в РЭ ##
    #########################################################

    # Упрощенная проверка - сравниваем только существенное содержимое
    def _blocks_are_equivalent(self, block1, block2):
        """Проверяет, эквивалентны ли блоки по содержанию (игнорируя форматирование)"""
        # Объединяем все строки и удаляем лишние пробелы/переносы
        content1 = ' '.join(block1).replace('\n', ' ').replace('  ', ' ')
        content2 = ' '.join(block2).replace('\n', ' ').replace('  ', ' ')
        return content1 == content2

    def renew_sum_table_latex(self):
        
        path_to_appA_tex = Path(self.device_data["path_to_latex_desc"]) / "Приложение А. Сигналы" / "_latex" / "app1.tex"
        start_tag = '%===t2\n'

        if not os.path.exists(path_to_appA_tex):
            Logger.error(f"Файл описания приложения суммарных сигналов не найден: {path_to_appA_tex}")
            return

        with open(path_to_appA_tex, 'r', encoding='utf-8') as f:
            content = f.readlines()

        new_content = []
        i = 0
        modified = False

        while i < len(content):
            line = content[i]

            if line == start_tag:
                # Найден начальный тег
                new_content.append(line)  # Сохраняем начальный тег
                i += 1

                # Собираем старое содержимое до закрывающего %===t2
                old_block = []
                while i < len(content) and content[i] != start_tag:
                    old_block.append(content[i])
                    i += 1

                # Генерируем новое содержимое
                latex_new = self._generate_summ_table_latex() # old_block #self._fsu.get_summ_table_latex()

                # Проверяем результат
                if not latex_new:
                    Logger.warning("Сгенерирована пустая таблица суммарных сигналов! Оставляем старую.")
                    new_content.extend(old_block)
                    new_content.append(start_tag)  # Добавляем закрывающий тег
                elif not self._blocks_are_equivalent(old_block, latex_new):
                    Logger.info("Контент отличается - будет обновлён.")
                    new_content.extend(latex_new)
                    new_content.append(start_tag)  # Добавляем закрывающий тег
                    modified = True
                else:
                    Logger.info("Контент не изменился - пропускаем обновление.")
                    new_content.extend(old_block)
                    new_content.append(start_tag)

                i += 1  # Пропускаем закрывающий тег после добавления

            else:
                # Копируем остальные строки
                new_content.append(line)
                i += 1

        # Записываем только если были изменения
        if modified:
            with open(path_to_appA_tex, 'w', encoding='utf-8') as f:
                f.writelines(new_content)
            Logger.info(f"Файл обновлён: {path_to_appA_tex}")
        else:
            Logger.info(f"Изменений в файле нет: {path_to_appA_tex}")










    def prepare_latex_structure(self):
        """Подготовка полной структуры данных для LaTeX рендера"""
        
        # Создаем словарь для быстрого доступа к блокам по ID
        blocks_by_id = {info['Id']: info for info in self.fsu_information}
        
        # Находим все корневые блоки (ParentId == None)
        root_blocks = [info for info in self.fsu_information if info['ParentId'] is None]
        
        # Сортируем корневые блоки по имени
        root_blocks.sort(key=lambda x: x['Name'])
        
        latex_structure = []
        
        for root in root_blocks:
            # Информация о корневом блоке
            root_entry = {
                'type': 'root',
                'id': root['Id'],
                'name': root['Name'],
                'display_name': root['DisplayName'],
                'type_name': root['TypeName'],
                'variables': root.get('Variables', []),
                'children': [],
                'level': 0,
                'is_root': True
            }
            
            # Находим все дочерние блоки
            children = [info for info in self.fsu_information 
                    if info.get('ParentId') == root['Id']]
            children.sort(key=lambda x: x['Name'])
            
            for child in children:
                child_entry = {
                    'type': 'child',
                    'id': child['Id'],
                    'name': child['Name'],
                    'display_name': child['DisplayName'],
                    'type_name': child['TypeName'],
                    'variables': child.get('Variables', []),
                    'parent_id': child['ParentId'],
                    'parent_name': root['Name'],
                    'level': 1,
                    'is_root': False
                }
                root_entry['children'].append(child_entry)
            
            latex_structure.append(root_entry)
        
        return latex_structure


    ###################################################
    ### Генерация суммарной таблицы в формате LATEX ###
    ###################################################
    def _generate_summ_table_latex(self):
        def _generate_row(row):
            row_str = '\\raggedright '
            row_str += row[0].replace('_', r'\_')
            row_str += ' & \\centering '
            row_str += row[1].replace('_', r'\_')
            row_str += ' & \\centering '
            row_str += row[2].replace('-', r'--').replace('*', r'$\ast$')
            row_str += ' & \\centering '
            row_str += row[3].replace('-', r'--').replace('*', r'$\ast$')
            row_str += ' & \\centering '
            row_str += row[4].replace('-', r'--').replace('*', r'$\ast$')
            row_str += ' & \\centering '
            row_str += row[5].replace('-', r'--').replace('*', r'$\ast$')
            row_str += ' & \\centering '
            row_str += row[6].replace('-', r'--').replace('*', r'$\ast$')
            row_str += ' & \\centering '
            row_str += row[7].replace('-', r'--').replace('*', r'$\ast$')
            row_str += ' & \\centering \\arraybackslash '
            row_str += row[8].replace('-', r'--').replace('*', r'$\ast$')
            row_str += ' \\\\ \\hline\n'
            return row_str

        def _generate_section(data, title=''): # Удалить потом - не используется
            section = []
            if data:
                #section.append(f'\\multicolumn{{9}}{{c|}}{{{title}}} \\\\\n\\hline\n')
                if title:
                    section.append(f'\\multicolumn{{9}}{{c}}{{\\textbf{{{title}}}}} \\\\\n\\hline\n')
                for row in data:
                    section.append(_generate_row(row))
            return section

        path_to_json = self.device_data["path_to_json"]
        # Загрузка вспомогательного файла, где находятится полное описание
        with open(path_to_json+'/fsu-information.json', 'r', encoding='utf-8') as f:
            self.fsu_information = json.load(f)['FunctionalBlocksInformation']


        table = []

        #temp_buttons = device.fsu.get_controls_for_latex()["buttons"]
        #if temp_buttons:
            #table.extend(_generate_section(temp_buttons, "Виртуальные кнопки"))
        #temp_keys = device.fsu.get_controls_for_latex()["keys"]
        #if temp_keys:
            #table.extend(_generate_section(temp_keys, "Виртуальные ключи"))

        # Список сигналов ФСУ
        g = self.prepare_latex_structure()

        table.append(f'\\multicolumn{{9}}{{c}}{{\\textbf{{{"Общие сигналы функциональной логики"}}}}} \\\\\n\\hline\n')
        for info in g:
            table.append('\\rowcolor{gray!15}\n')
            header = f'\\multicolumn{{9}}{{c}}{{{info["display_name"]} }} \\\\\n\\hline\n'
            table.append(header)
            
            # Переменные корневого блока
            if info["variables"]:
                # Сначала проверяем, есть ли сигналы с RTE_OUTPUT
                has_rte_output = any(var.get("Comment") == "RTE_OUTPUT" for var in info["variables"])
                
                if has_rte_output:
                    header2 = f'\\multicolumn{{9}}{{c}}{{ Общие сигналы блока }} \\\\\n\\hline\n'
                    table.append(header2)
                    
                    for var in info["variables"]:
                        if var.get("Comment") == "RTE_OUTPUT":
                            description = var.get("Description", {})
                            full_description = description.get("FullDescription", "") if isinstance(description, dict) else ""
                            desc_text = description.get("Description", "") if isinstance(description, dict) else str(description)                
                            row = (full_description, desc_text, "-", "-", "-", "-", "-", "-", "-")
                            row_str = _generate_row(row)
                            table.append(row_str)
            
            # Переменные дочерних блоков
            if info["children"]:
                for child in info["children"]:
                    # Проверяем, есть ли сигналы RTE_OUTPUT в дочернем блоке
                    has_rte_output = False
                    if child.get("variables"):
                        for var in child["variables"]:
                            if var.get("Comment") == "RTE_OUTPUT":
                                has_rte_output = True
                                break
                    
                    # Выводим заголовок только если есть сигналы
                    if has_rte_output:
                        # Добавляем заголовок дочернего блока
                        child_header = f'\\multicolumn{{9}}{{c}}{{\\text{{{child["display_name"]}}}}} \\\\\n\\hline\n'
                        table.append(child_header)
                        
                        # Переменные дочернего блока
                        for var in child["variables"]:
                            if var.get("Comment") == "RTE_OUTPUT":
                                description = var.get("Description", {})
                                full_description = description.get("FullDescription", "") if isinstance(description, dict) else ""
                                desc_text = description.get("Description", "") if isinstance(description, dict) else str(description)                
                                row = (full_description, desc_text, "-", "-", "-", "-", "-", "-", "-")
                                row_str = _generate_row(row)
                                table.append(row_str)

        # Список сигналов ЖЕЛЕЗА
        #statuses_list = device.modules.get_statuses_for_latex_sum_table()
        #if statuses_list:
            #table.append(f'\\multicolumn{{9}}{{c}}{{\\textbf{{{"Дискретные сигналы модулей в составе устройства"}}}}} \\\\\n\\hline\n')
            #for module in device.modules.get_statuses_for_latex_sum_table():
                #table.append('\\rowcolor{gray!15}\n')
                #header = f'\\multicolumn{{9}}{{c}}{{{module["module"]}}} \\\\\n\\hline\n'
                #table.append(header)
                #table.extend(_generate_section(module["statuses"]))

        return table

    ###################################################
           ### Обновить перечень сокращений  ###
    ###################################################        

    def renew_abbrs(self):
        path_to = Path(self.path_to_latex_desc)  / '_manual_latex' / 'general.pdf'
        Logger.info(path_to)
        start_abbr(path_to) 

    def renew_abbrs_ru(self):
        if not self.path_to_ru_desc:
            Logger.error("Пустой путь к pdf с уставками!")
            return 1
        path_to = Path(self.path_to_ru_desc) 
        Logger.info(path_to)
        start_abbr(path_to) 
        return 0










    def _render_latex_settings_blockOLD(self, settings_data, header):
        table = []
        if header is not None and header != "":
            head_latex = '\multicolumn{5}{|c|}{ ' + header + ' } \\\\ \hline \n'
            table.append(head_latex)
        for row in settings_data:
            str_ = '\centering '
            str_ += row[0].replace('_', r'\_')
            str_ += ' & \centering '
            str_ += row[1].replace('-', r'--').replace('_', r'\_')
            str_ += ' & \centering '
            str_ += row[2].replace('\n', r'\\')
            str_ += ' & \centering '
            str_ += row[3].replace('-', r'--').replace('%', r'\%')
            str_ += ' & \centering \\arraybackslash '
            str_ += row[4].replace('-', r'--')
            str_ += ' \\\\\n'  # Закрываем строку таблицы и переносим строку
            table.append(str_)  # Добавляем строку таблицы
            table.append('\\hline\n')  # Добавляем \hline отдельным элементом
        return table