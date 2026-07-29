import re
import tkinter as tk
from tkinter import messagebox
from logger.logger import Logger

def general_tex_parser(path_to_general_tex):
    # ЧАСТЬ 1
    # Читаем LaTeX-файл
    with open(path_to_general_tex, 'r', encoding='utf-8') as f:
        latex_code = f.read()

    # Извлекаем строки между %===f
    pattern = r'%===f\n(.*?)\n%===f'
    match = re.search(pattern, latex_code, re.DOTALL)

    lines = []

    if match:
        # Разбиваем на строки, удаляем пустые и строки, начинающиеся с %
        lines = [
            line.strip() 
            for line in match.group(1).split('\n') 
            if line.strip() and not line.strip().startswith('%')
        ]
        
    else:
        #print("Маркеры %===f не найдены")
        return []

    # ЧАСТЬ 2 - отладочная версия

    functions = []

    for i, line in enumerate(lines, 1):
        # Удаляем комментарии
        original_line = line
        if '%' in line:
            line = line[:line.index('%')].strip()
        
        
        # Пробуем разные варианты извлечения
        found = False
        
        # Вариант 1: ищем паттерн /папка_с_функцией/файл.tex
        match1 = re.search(r'/([^/]+)/([^/]+)\.tex$', line)
        if match1:
            function_name = match1.group(1)
            functions.append(function_name)
            found = True
        
        # Вариант 2: если не нашли, пробуем извлечь имя файла без .tex
        if not found:
            match2 = re.search(r'/([^/]+)\.tex$', line)
            if match2:
                filename = match2.group(1)
                functions.append(filename)
                found = True
        
        # Вариант 3: если ничего не нашли, разбиваем по слешам
        if not found:
            parts = line.split('/')
            if len(parts) >= 2:
                # Берем предпоследнюю часть
                function_name = parts[-2]
                functions.append(function_name)
                found = True
        
        if not found:
            functions.append("???")

    purified_funcs = []

    for func in functions:
        # Удаляем цифровой префикс в начале строки
        # Паттерн: цифры, точка, цифры, пробел ИЛИ просто цифры и пробел
        # Примеры:
        # "041.0611 ДТЗ" -> "ДТЗ"
        # "261.0621 ДТЗ НП" -> "ДТЗ НП"
        # "9901 Логика отключения" -> "Логика отключения"
        # "91 Сигнализация" -> "Сигнализация"
        
        # Вариант 1: удаляем цифры.цифры в начале
        cleaned = re.sub(r'^\d+\.\d+\s+', '', func)
        
        # Вариант 2: если не изменилось, удаляем просто цифры и пробел в начале
        if cleaned == func:
            cleaned = re.sub(r'^\d+\s+', '', func)
        
        # Вариант 3: если всё еще не изменилось, удаляем любые цифры и точки/пробелы в начале
        if cleaned == func:
            cleaned = re.sub(r'^[\d.]+\s*', '', func)
        
        purified_funcs.append(cleaned)

    return purified_funcs

def reorder_blocks(file_content, new_order):
    """
    Переупорядочивает блоки в файле согласно заданному порядку.
    """
    # Разбиваем на блоки по тегам %>
    blocks = {}
    header = ""
    
    # Находим все теги %>, сохраняя их позиции
    pattern = r'%>\s*([^\n]+)'
    matches = list(re.finditer(pattern, file_content))
    
    if not matches:
        return file_content
    
    # Сохраняем текст до первого тега
    if matches[0].start() > 0:
        header = file_content[:matches[0].start()].rstrip('\n')
    
    # Извлекаем каждый блок
    for i, match in enumerate(matches):
        block_name = match.group(1).strip()
        start_pos = match.start()
        
        # Определяем конец блока (до следующего тега или конца файла)
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(file_content)
        
        # Содержимое блока
        block_content = file_content[start_pos:end_pos]
        
        # ✅ Нормализуем: убираем лишние пустые строки в конце блока
        block_content = block_content.rstrip('\n')
        
        # Сохраняем блок
        blocks[block_name] = block_content
    
    # Создаем новый порядок блоков
    ordered_blocks = []
    
    # Сначала добавляем блоки в новом порядке
    for block_name in new_order:
        if block_name in blocks:
            ordered_blocks.append(blocks[block_name])
            del blocks[block_name]
    
    # Затем добавляем оставшиеся блоки
    for block_name, content in blocks.items():
        ordered_blocks.append(content)
    
    # ✅ Собираем финальный результат с ОДНОЙ пустой строкой между блоками
    if header:
        result = header + "\n\n" + "\n\n".join(ordered_blocks) + "\n"
    else:
        result = "\n\n".join(ordered_blocks) + "\n"
    
    return result


def start_arrange(path_to_general_tex, path_to_appset_tex):

    Logger.info("Пуск ранжирования...")

    funcs = general_tex_parser(path_to_general_tex)
    Logger.info(f"Порядок следования general.tex: {funcs}")    

    # Читаем исходный файл
    with open(path_to_appset_tex, 'r', encoding='utf-8') as f:
        content = f.read()

    # Получаем список всех блоков из файла appset.tex
    pattern = r'%>\s*([^\n]+)'
    all_blocks_in_file = re.findall(pattern, content)
    Logger.info(f"Порядок следования appset.tex: {all_blocks_in_file}")

    # ✅ ПРОВЕРКА: сравниваем количество функций
    #print(f"Функций в general.tex: {len(funcs)}")
    if len(all_blocks_in_file)== 0:
        Logger.error("Нет функций в appset.tex или appset.tex не подготовлен (тэги %>)")
        return
    #Logger.info(f"Функций в general.tex: {len(funcs)}")
    #print(f"Блоков в appset.tex: {len(all_blocks_in_file)}")
    #Logger.info(f"Блоков в appset.tex: {len(all_blocks_in_file)}")

    Logger.info(f"Блоки, которые есть в general.tex, но нет в appset.tex: {set(funcs)-set(all_blocks_in_file)}")
    diff = set(all_blocks_in_file) - set(funcs)
    Logger.info(f"Блоки, которые есть в appset.tex, но нет в general.tex: {diff if diff  else 'отсутствуют'}")
    if diff:
        # Используем Tkinter для диалога
        root = tk.Tk()
        root.withdraw()  # Скрываем главное окно
        
        answer = messagebox.askyesno(
            "Подтверждение",
            f"В appset.tex больше блоков, чем в general.tex.\n"
            f"Лишние блоки: {diff}\n\n"
            "Подтверждаете ранжирование?"
        )
        root.destroy()
        
        if not answer:
            Logger.info("Пользователь отклонил ранжирование")
            return


    # Находим блоки, которые есть в файле, но отсутствуют в списке funcs
    missing_blocks = []
    for block in all_blocks_in_file:
        if block not in funcs:
            missing_blocks.append(block)

    if missing_blocks:
        #print("ВНИМАНИЕ: В списке general.tex отсутствуют следующие блоки:")
        Logger.warning("ВНИМАНИЕ: В списке general.tex отсутствуют следующие блоки:")
        Logger.warning(missing_blocks)
        #for i, block in enumerate(missing_blocks, 1):
            #print(f"   {i}. {block}")
        #print(f"\n   Всего отсутствует: {len(missing_blocks)} блок(ов)")
        Logger.warning(f"Всего отсутствует: {len(missing_blocks)} блок(ов)")
        #print("   Эти блоки будут добавлены в конец файла после переупорядочивания.\n")
        Logger.warning("Эти блоки будут добавлены в конец файла после переупорядочивания.")        
    elif len(funcs) < len(all_blocks_in_file):
        print("ВНИМАНИЕ: В списке general.tex меньше функций, чем блоков в файле!")
        Logger.warning("ВНИМАНИЕ: В списке general.tex меньше функций, чем блоков в файле!")
        print("   Но все блоки из файла присутствуют в списке (возможны дубликаты в списке).\n")
        Logger.warning("Но все блоки из файла присутствуют в списке (возможны дубликаты в списке).")        
    else:
        Logger.info("Все блоки учтены корректно.")
        #print("Все блоки учтены корректно.\n")

    # Переупорядочиваем блоки
    reordered_content = reorder_blocks(content, funcs)

    # Сохраняем результат в новый файл
    with open(path_to_appset_tex, 'w', encoding='utf-8') as f:
        f.write(reordered_content)

    # Проверяем результат
    #matches = re.findall(pattern, reordered_content)
    #print(matches)
    #print(f"\nФайл успешно переупорядочен и сохранен")