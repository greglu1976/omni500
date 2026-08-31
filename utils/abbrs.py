import fitz  # Импортируем библиотеку PyMuPDF
import re
import os
import sys
import json

from logger.logger import Logger

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.append(parent_dir)

abbrs = {
    'ОСФ':'Орган сравнения фаз',
    'КИТЦ':'Контроль исправности токовых цепей',
    'КИЦТ':'Контроль исправности токовых цепей - неправильная абр',
    'ЗП':'Защита от перегрузки',
    'ЗПО':'Защита от потери охлаждения',
    'УРОВ':'Устройство резервирования при отказе выключателя',
    'ТЗНП':'Токовая защита нулевой последовательности',
    'ТЗОП':'Токовая защита обратной последовательности',
    'ФСУ':'Функционально-структурная схема',
    'ЗПНОП':'Защита от повышения напряжения обратной последовательности',
}


# Определяем словарь абревиатур
def load_dict(abbrs):
    data = abbrs
    # Ищем файл со словарем
    path_to_dict = 'dictionary.json'
    if os.path.isfile(path_to_dict):
        with open(path_to_dict, 'r', encoding='utf-8') as file:
            data = json.load(file)
            Logger.info("Найден внешний словарь абревиатур dictionary.json")
            return data
    Logger.warning("Не найден внешний словарь абревиатур dictionary.json, будет использоваться пустой внутренний словарь!")
    return data

def get_abbrs_new(word_list, abbr_dict):
    abbr_set = set(abbr_dict.keys())
    new_list = []
    for word in word_list:
        for abbr in abbr_set:
            if abbr in word:
                new_list.append(abbr)
    word_set = set(new_list)
    word_list = sorted(list(word_set))    
    return word_list

def get_abbrs(word_list):
    # Список слов, которые нужно исключить (можно изменять внутри функции)
    EXCLUDE_LIST = ["AB", "AI", "BI", "CI", "BC", "CA", "CН", "DIN", "DZ", "ЕС", "EC", "EH", "EL", "FB", "FBS", "FTP", "GPR", "GPS", "GPT", "HL", "HNT", "II", "III", "IA", "IB", "IВ", "IC", "IP", "IРЗН", "IT", "IШОН", "JDG", "KA", "KD", "KL", "KPX", "KS", "LS", "MIC", "MSC", "MSK", "MT", "NO", "PC", "PE", "PTU", "RPV", "RTK", "RUT",
                     "RS", "SA", "SB", "SG", "SF", "SFP", "SGF", "SMA", "SQ", "TOF", "TON", "TP", "TT", "UA", "UB", "UC", "UАВ", "UВН", "UВС", "UНК", "BH", "BН", "CH", "UAB", "UBC", "UBС", "НH", "UI", "UZ", "UА", "UБНН", "UС", "UШОН", "UЭ", "VD", "АВ", "ВС", "СА", "XA", "XА", "WE", "XP",
                     "АК", "АПВл", "АПВш", "АУТС", "БАТ", "БТ", "ВИДА", "ВНИИР", "ГОСТ", "ДЛЯ", "ЖКХ", "ЗАЖИМОВ", "ЗАКАЗА", "ЗАЩИТ", "ЗАЩИТЫ", "ИЗДЕЛИЯ", "КАРТА", "ЛИСТ", "МИКО", "МОм", "НЛПР", "ОБЩ", "ОБЩЕЕ", "ОЖ", "ОЖО", "ОРТИС", "ПОРЯДОК", "ППЗ", "ПРM", "РАЗМЕРЫ", "РЕМОНТ", "РЯДОВ", "СЕРИИ", "СКЛ", "СРЕДСТВ", "СТО", "CTO", "СТЭЗ", "СХЕМ", "СХЕМА", "СХЕМЫ", "ТОКА", "ТФ", "ТЭ", "ОБЩЕГО", "ФП", "ФСК", "ФУНКЦИИ",
                     "ЦЕПЕЙ", "ЧЕРТЕЖ", "ШКАФ", "ШКАФА", "KR", "KХ", "RJ", "RU", "АААА", "ВC", "ВЭД", "ИК", "ИЛИ", "ИС", "ИФ", "КОД", "НЕ", "НИ", "НК", "НФ", "ОКПД", "ООО", "ПАО", "РАБОТА", "СЕРВИС", "ТП", "ФЗ", "ФФ", "ЭПББ", "ЭПРК", "ЭПРОМ", "ЮИРЗ", "ЮНИТ", "ЮТКБ", "ЯШГК"]
    
    # оставляем только слова по шаблону - первые две бкувы заглавные - остальные любые
    new_word_list = []
    for word in word_list:
        cleaned_string = re.sub(r'^[^A-Za-zА-Яа-я]+', '', word)
        cleaned_string = re.sub(r'[^A-Za-zА-Яа-я]+$', '', cleaned_string)
        if re.match('^[A-ZА-Я]{2}[A-Za-zА-Яа-я~\s]*$', cleaned_string): #^[A-ZА-Я]{2}[A-Za-zА-Яа-я~\s]*$ # ^[A-ZА-Я]{2}[A-Za-zА-Яа-я]*$
            new_word_list.append(cleaned_string)
        
    abbrs = []
    for word in new_word_list:
        if len(word)<=7 and word not in EXCLUDE_LIST:
            abbrs.append(word)
    set_abbrs = set(abbrs)
    return list(set_abbrs)

def extract_words_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    words = []
    skip = False  # игнорировать слова, если True
    for page in doc:
        # Получаем текст страницы как строку
        text = page.get_text("text")
        # Объединяем "АСУ ТП" в "АСУ~ТП" (тильда предотвратит разбиение)
        text = re.sub(r'АСУ\s+ТП', 'АСУ~ТП', text)
        # Разбиваем текст на токены (по любым пробельным символам)
        tokens = text.split()
        i = 0
        while i < len(tokens):
            token = tokens[i]
            # Обработка маркеров начала и конца таблицы
            if token == '<begABBRS>':
                skip = True
                i += 1
                continue
            if token == '<endABBRS>':
                skip = False
                i += 1
                continue
            # Если не в режиме пропуска – добавляем слово
            if not skip:
                words.append(token)
            i += 1 
    doc.close()
    return words

#  переработаная функция для GUI
def replace_pdf_with_attrs_txt(path):
    path = os.path.normpath(path)
    base_path, file_name = os.path.split(path)
    file_name_without_extension = os.path.splitext(file_name)[0]
    new_txt_filename ='toa_' + file_name_without_extension + '.tex'
    new_attrs_filename = 'attrs_' + file_name_without_extension + '.txt'
    new_doc_filename = file_name_without_extension + '.docx'
    new_txt_path = os.path.join(base_path, new_txt_filename)
    new_attrs_path = os.path.join(base_path, new_attrs_filename)
    new_doc_path = os.path.join(base_path, new_doc_filename)
    return (path, os.path.abspath(new_txt_path), os.path.abspath(new_attrs_path), os.path.abspath(new_doc_path))

def parse_tex(new_word_list, data):
    used_keys = []
    tex_list = []
    doc_list = []
    for word in new_word_list:
        # Проверяем, встречается ли ключ словаря в списке слов и не использовался ли уже
        if word in data.keys() and word not in used_keys:
            used_keys.append(word)
            value = data[word]
            #value = value[0].lower() + value[1:] # с маленькой буквы ?
            # Формируем строку tex и добавляем ее в tex_list
            if value.startswith('!'):
                value = value[1:]
                temp = '\\textcolor{red}{'+value+'}'
                tex_list.append(f'{word} & -- & {temp}; \\\\'+'\n')
            else:
                tex_list.append(f'{word} & -- & {value}; \\\\'+'\n')
            doc_list.append(f'{word} - {value}')
    # Меняем в последней строке ; на точку
    if tex_list:
            last_element_index = len(tex_list) - 1
            last_element = tex_list[last_element_index]
            updated_last_element = last_element.replace('; \\\\\n', '. \\\\\n')
            tex_list[last_element_index] = updated_last_element
            tex_list.append("{\color{white}\\fontsize{0.1pt}{0.1pt}\selectfont<endABBRS>}"+'\n')            
    return tex_list 

def parse_tex_new(key_list, dict):
    """
    Формирует строки для окружения list.
    key_list – список сокращений, которые есть в словаре.
    dict – словарь сокращений.
    Возвращает список строк вида \item[Ключ] Значение;
    """
    tex_list = []
    for key in key_list:
        if key in dict:
            val = dict[key]
            if val.startswith('!'):
                val = val[1:]
                val = '\\textcolor{red}{' + val + '}'
            tex_list.append(f'\\item[{key}] {val};' + '\n')
    # Заменяем последнюю точку с запятой на точку
    if tex_list:
        last = tex_list[-1]
        tex_list[-1] = last.replace(';', '.', 1)
    return tex_list

def start_abbr(filepath):
    Logger.info("Запуск скрипта обновления абревиатур...")

    path_to_pdf = replace_pdf_with_attrs_txt(filepath)
    Logger.info(f"Обработка {path_to_pdf[0]}")
    word_list_origin = extract_words_from_pdf(path_to_pdf[0])

    word_set = set(word_list_origin)
    word_list = sorted(list(word_set))
    # Получаем список всех распознанных аббревиатур (new_word_list)
    new_word_list = sorted(get_abbrs(word_list))
    Logger.info(new_word_list)

    if not new_word_list:
        Logger.info("Нет распознанных абревиатур в текущем файле pdf...")
        return 'noabbrs'

    # Запись списков в файл attrs (без изменений)
    with open(path_to_pdf[2], 'w', encoding='utf-8') as file:
        file.write(', '.join(new_word_list))

    with open('dictionary.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        exclude_keys = set(data.keys())

    new_abbrs = [word for word in new_word_list if word not in exclude_keys]
    with open(path_to_pdf[2], 'w', encoding='utf-8') as file:
        file.write("Список всех найденных сокращений в general.pdf: " + ", ".join(new_word_list) + "\n")
        file.write("Список новых сокращений для добавления в dictionary.json: " + ", ".join(new_abbrs))

    os.startfile(path_to_pdf[2])

    # Загружаем словарь
    dict_data = load_dict(abbrs)

    # ----- ОСНОВНОЕ ИЗМЕНЕНИЕ -----
    # Берём только те сокращения из new_word_list, для которых есть расшифровка в словаре
    filtered_abbrs = [w for w in new_word_list if w in dict_data]
    # Формируем строки \item
    tex_lines = parse_tex_new(filtered_abbrs, dict_data)

    # Вычисляем самое длинное сокращение (для подстановки в \settowidth)
    longest_abbr = max(filtered_abbrs, key=len) if filtered_abbrs else "ААААА"

    # Динамическое вступление (исправленное)
    intro_parts = [
        "\\phantomsection\n",
        "\\color{unidarkgreen}\\section*{\\centering{\\large{ПЕРЕЧЕНЬ СОКРАЩЕНИЙ}}}\n",
        "\\addcontentsline{toc}{section}{Перечень сокращений}\n",
        "\n",
        "% ===== НАСТРОЙКИ =====\n",
        "\\newlength{\\abbrgap}\n",
        "\\setlength{\\abbrgap}{1.5em}   % <-- расстояние между \"--\" и расшифровкой (меняйте здесь)\n",
        "\n",
        "% Автоматическая ширина метки: самое длинное сокращение + тире + пробел + запас\n",
        "\\newlength{\\abbrwidth}\n",
        f"\\settowidth{{\\abbrwidth}}{{{longest_abbr}}}   % самое длинное сокращение\n",
        "\\addtolength{\\abbrwidth}{3.5em}% запас под \"-- \" и отступ\n",
        "% ======================\n",
        "\n",
        "{\\color{white}\\fontsize{0.1pt}{0.1pt}\\selectfont<begABBRS>}\n",
        "\\color{black}\n",
        "\n",
        "\\begin{list}{}%\n",
        "{%\n",
        "  \\setlength{\\labelwidth}{\\abbrwidth}%\n",
        "  \\setlength{\\labelsep}{0pt}%      <-- теперь весь отступ задаётся через \\abbrgap в метке\n",
        "  \\setlength{\\leftmargin}{\\dimexpr\\labelwidth+\\labelsep\\relax}%\n",
        "  \\setlength{\\itemindent}{0pt}%\n",
        "  \\setlength{\\parsep}{0pt}%\n",
        "  \\setlength{\\itemsep}{0pt}\n",
        "  \\renewcommand{\\makelabel}[1]{#1 --\\hspace{\\abbrgap}}%   <-- метка = сокращение + \"--\" + пробел\n",
        "}\n"
    ]

    outro_parts = [
        "{\\color{white}\\fontsize{0.1pt}{0.1pt}\\selectfont<endABBRS>}\n",
        "\\end{list}\n"
    ]

    final_tex = intro_parts + tex_lines + outro_parts

    # Запись итогового .tex-файла
    with open(path_to_pdf[1], 'w', encoding='utf-8') as file:
        file.writelines(final_tex)

    Logger.info("Останов скрипта поиска абревиатур...")
    return