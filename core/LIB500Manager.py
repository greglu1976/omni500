import json
from pathlib import Path
from collections import defaultdict

path = Path(r'\\uni-eng.ru\unit\Ivanovo\Документация ЮНИТ М300\Разработка\Схемы ФБ ЮНИТ-М300\Проект\БД500\ФСУ\Э2 03.01 (КСЗ+АУВ)_v3.JSON')

def get_table_latex(lib_path, macroblock):
    # Загрузка JSON файла
    with open(path, 'r', encoding='utf-8') as f:
        functional_blocks = json.load(f)['Schema']['Info']['Composition']['FunctionalBlocks']
    
    # Ищем нужный функциональный блок
    target_fb = None
    for fb in functional_blocks:
        if isinstance(fb, dict) and fb.get('DisplayName') == lib_path:
            target_fb = fb
            break
    
    if target_fb is None:
        print(f"Функциональный блок с именем '{lib_path}' не найден.")
        return []
    
    # Определяем, какие режимы нужно обработать
    modes_to_process = []
    if macroblock == 'general+-':
        modes_to_process = ['general', '-']
    else:
        modes_to_process = [macroblock]
    
    # Общий словарь для всех результатов
    all_results = []
    
    for current_mode in modes_to_process:
        # Словарь для группировки уставок по макроблокам
        macro_settings = defaultdict(list)
        
        if current_mode != 'general':
            # Проверяем наличие Info и Composition
            if 'Info' not in target_fb or 'Composition' not in target_fb['Info']:
                print("Нет структуры Info/Composition в блоке.")
                continue
            
            data = target_fb['Info']['Composition']
            
            # Проход по макроблокам
            macro_blocks = data.get("MacroBlocks", [])
            if not macro_blocks:
                print("Нет макроблоков в файле.")
                continue
            
            for macro in macro_blocks:
                macro_name = macro.get("DisplayName", "Безымянный")
                
                # Если macroblock задан как конкретное имя — пропускаем все, кроме него
                if current_mode != "-" and macro_name != current_mode:
                    continue
                
                # Уставки
                for setting in macro.get("Settings", []):
                    setting_data = setting.get("Setting", {}).get("OriginData")
                    if setting_data and not setting_data.get("IsConstant", True):
                        # Формируем уставку
                        setting_info = {
                            "Name": setting_data.get("Name", "Безымянная уставка"),
                            "Value": setting_data.get("Value"),
                            "Unit": setting_data.get("Unit"),
                            "Min": setting_data.get("Min"),
                            "Max": setting_data.get("Max"),
                            "Default": setting_data.get("Default"),
                            "Step": setting_data.get("Step"),
                            "Description": setting_data.get("Description"),
                            "IsConstant": setting_data.get("IsConstant"),
                            "DataType": setting_data.get("DataType"),
                            "PredefinedValues": get_PredefinedValues(setting_data.get("LogicValue")),
                            "Id": setting_data.get("Id")
                        }
                        macro_settings[macro_name].append(setting_info)
        else:
            # Режим 'general' - берем уставки из корневого блока
            macro_name = lib_path
            
            # Уставки из корневого блока
            for setting in target_fb.get("Settings", []):
                setting_data = setting.get("Setting", {}).get("OriginData")
                if setting_data and not setting_data.get("IsConstant", True):
                    setting_info = {
                        "Name": setting_data.get("Name", "Безымянная уставка"),
                        "Value": setting_data.get("Value"),
                        "Unit": setting_data.get("Unit"),
                        "Min": setting_data.get("Min"),
                        "Max": setting_data.get("Max"),
                        "Default": setting_data.get("Default"),
                        "Step": setting_data.get("Step"),
                        "Description": setting_data.get("Description"),
                        "IsConstant": setting_data.get("IsConstant"),
                        "DataType": setting_data.get("DataType"),
                        "PredefinedValues": get_PredefinedValues(setting_data.get("LogicValue")),
                        "Id": setting_data.get("Id")
                    }
                    macro_settings[macro_name].append(setting_info)
        
        # Формируем результат для текущего режима
        for macro_name, settings_list in macro_settings.items():
            if macroblock not in ("-", "general+-"):
                # Заменяем имя макроблока на "-", если запрошен конкретный
                all_results.append({"MacroBlock": "-", "Settings": settings_list})
            else:
                # Иначе оставляем настоящее имя
                all_results.append({"MacroBlock": macro_name, "Settings": settings_list})
    
    return all_results

def get_table_signals_FB(version, func_type, lib_path):
    full_path = path / version / lib_path
    composition_path = full_path / "Composition.json"

    # Загрузка JSON файла
    with open(composition_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    outputs_list = []

    # Создаём словари для быстрого поиска блоков по ID
    output_blocks_by_id = {blk["Id"]: blk for blk in data.get("OutputBlocks", [])}

    # Все связи (Links)
    all_links = data.get("Links", [])

    # Инвертируем связи: для каждого целевого блока (куда входит сигнал) — откуда он идёт
    link_to_source = {}
    for link in all_links:
        to_id = link["SchemaNodeToId"]
        from_id = link["SchemaNodeFromId"]
        leg_to_id = link["LegToId"]
        leg_from_id = link["LegFromId"]
        link_to_source[to_id] = {
            "from_node_id": from_id,
            "from_leg_id": leg_from_id,
            "to_leg_id": leg_to_id
        }

    # Проход по макроблокам
    macro_blocks = data.get("MacroBlocks", [])
    if not macro_blocks:
        print("Нет макроблоков в файле.")
    else:
        for macro in macro_blocks:
            macro_id = macro["Id"]
            macro_name = macro.get("Name", "Безымянный")

            # Выходы
            for out in macro.get("Outputs", []):
                if out.get("DataType") == "Undefined":
                    continue

                # Ищем все OutputBlocks, которые подключены к этому выходу макроблока
                # Для этого ищем связи, исходящие из этого макроблока и этого Leg'а
                matched_output_blocks = []
                for link in all_links:
                    if link["SchemaNodeFromId"] == macro_id and link["LegFromId"] == out["Id"]:
                        to_block_id = link["SchemaNodeToId"]
                        if to_block_id in output_blocks_by_id:
                            matched_output_blocks.append(output_blocks_by_id[to_block_id])

                # Добавляем информацию в outputs_list
                output_record = {
                    "MacroBlock": macro_name,
                    "Type": "Output",
                    "Name": out.get("Name", "Безымянный выход"),
                    "DataType": out.get("DataType"),
                    "Index": out.get("Index"),
                    "ConnectedOutputBlocks": [
                        {
                            "Id": ob["Id"],
                            "Name": ob.get("Name"),
                            "DisplayName": ob.get("DisplayName"),
                            "VariableId": ob.get("VariableId")
                        }
                        for ob in matched_output_blocks
                    ]
                }
                outputs_list.append(output_record)

    # ---- Вывод результатов ----

    print("\n=== ВЫХОДЫ ===")
    for o in outputs_list:
        print(f"[{o['MacroBlock']}] Выход: {o['ConnectedOutputBlocks'][0]['Name']} ")

def get_table_signals_FSU(version, func_type, lib_path):
    path = Path(r'\\uni-eng.ru\unit\Ivanovo\Документация ЮНИТ М300\Разработка\Схемы ФБ ЮНИТ-М300\Проект\БД500')
    full_path = path / version / lib_path
    composition_path = full_path / "Composition.json"

    with open(composition_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Собираем блоки из всех возможных секций
    all_blocks = []
    for section in [
        "FunctionalBlocks",
        "MacroBlocks",         # ← КЛЮЧЕВОЕ ДОБАВЛЕНИЕ!
        "InputBlocks",
        "OutputBlocks",
        "PrimitiveBlocks",
        "ConstantBlocks",
        "SettingBlocks"
    ]:
        section_data = data.get(section, [])
        if isinstance(section_data, list):
            all_blocks.extend(section_data)
        else:
            print(f"⚠️  Секция {section} не является списком: {type(section_data)}")

    outputs_list = []

    for blk in all_blocks:
        if not isinstance(blk, dict):
            continue

        blk_name = blk.get("DisplayName", blk.get("Name", "<без имени>"))
        blk_var_id = blk.get("VariableId")

        # Обрабатываем все Outputs
        for out_leg in blk.get("Outputs", []):
            if out_leg.get("DataType") == "Undefined":
                continue
            if out_leg.get("LegUsage") != "Output":
                continue

            # Ищем VariableId: сначала у ноги, потом у блока
            var_id = out_leg.get("VariableId") or blk_var_id or "отсутствует"

            outputs_list.append({
                "SourceBlock": blk_name,
                "SourceLeg": out_leg.get("Name", "<без имени>"),
                "DataType": out_leg.get("DataType"),
                "VariableId": var_id
            })

    # Вывод
    print("\n=== ВЫХОДЫ ===")
    if not outputs_list:
        print("Нет найденных выходов.")
    else:
        for rec in outputs_list:
            print(f"[{rec['SourceBlock']}:{rec['SourceLeg']}] → {rec['DataType']} (VariableId: {rec['VariableId']})")

    return outputs_list

def get_PredefinedValues(data, field='DisplayText', separator=' \\\ ', sort_by=None):
    items = data.get('PredefinedValues', [])
    if sort_by:
        items = sorted(items, key=lambda x: x[sort_by])
    values = [item[field] for item in items if field in item]
    return separator.join(values)





if __name__=="__main__":
    version = "0.0.0.2"
    func_type = "FSU"
    lib_path = "ФСУ\Тестовая ФСУ"
    get_table_signals_FSU(version, func_type, lib_path)