import json
from pathlib import Path
from collections import defaultdict

#path = Path(r'C:\Users\g.lubov.UNI-ENG\Desktop\ЮНИТ-СК\lib')
path = Path(r'\\uni-eng.ru\unit\Ivanovo\Документация ЮНИТ М300\Разработка\Схемы ФБ ЮНИТ-М300\Проект\БД500')


def get_table_latex(version, func_type, lib_path, only):
    full_path = path / version / lib_path
    composition_path = full_path / "Composition.json"

    # Загрузка JSON файла
    with open(composition_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Словарь для группировки уставок по макроблокам
    macro_settings = defaultdict(list)

    # Проход по макроблокам
    macro_blocks = data.get("MacroBlocks", [])
    if not macro_blocks:
        print("Нет макроблоков в файле.")
        return []

    for macro in macro_blocks:
        macro_name = macro.get("Name", "Безымянный")

        # Если only задан как конкретное имя — пропускаем все, кроме него
        if only != "-" and macro_name != only:
            continue

        # Уставки
        for setting in macro.get("Settings", []):
            setting_data = setting.get("Setting", {}).get("Data")
            if setting_data and not setting_data.get("IsConstant", True):
                # Формируем уставку без поля "MacroBlock" (оно будет на уровне группы)
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
                    #"Id": setting_data.get("Id")
                }
                macro_settings[macro_name].append(setting_info)

    # Формируем результат
    result = []
    for macro_name, settings_list in macro_settings.items():
        if only != "-":
            # Заменяем имя макроблока на "-", если запрошен конкретный
            result.append({"MacroBlock": "-", "Settings": settings_list})
        else:
            # Иначе оставляем настоящее имя
            result.append({"MacroBlock": macro_name, "Settings": settings_list})

    return result


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








if __name__=="__main__":
    version = "0.0.0.2"
    func_type = "FSU"
    lib_path = "ФСУ\Тестовая ФСУ"
    get_table_signals_FSU(version, func_type, lib_path)