import fitz  # Импортируем библиотеку PyMuPDF
import re
import os
import sys
import json

from logger.logger import Logger

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.append(parent_dir)


intro_strs = []
intro_strs.append("\phantomsection"+"\n") # чтобы правильно генерировать ссылку
intro_strs.append("\color{unidarkgreen}\section*{\centering{\large{ПЕРЕЧЕНЬ СОКРАЩЕНИЙ}}}"+"\n")
intro_strs.append("\\addcontentsline{toc}{section}{Перечень сокращений}"+"\n") # строка для включения в содержание
intro_strs.append("{\color{white}\\fontsize{0.1pt}{0.1pt}\selectfont<begABBRS>}"+"\n") # невидимый тег начала перечня сокращений
intro_strs.append("\color{black}"+"\n")
intro_strs.append('\\begin{longtable}{>{\\raggedright\\arraybackslash}m{2cm}>{\\raggedright\\arraybackslash}m{0.5cm}>{\\raggedright\\arraybackslash}m{20cm}}'+'\n')
intro_strs.append('\endfirsthead\endhead\endfoot\endlastfoot'+'\n')
outro_strs = []
outro_strs.append('\end{longtable}'+'\n')
outro_strs.append("{\color{white}\\fontsize{0.1pt}{0.1pt}\selectfont<endABBRS>}") # невидимый тег начала перечня сокращений

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
    EXCLUDE_LIST = ["AB", "BC", "CA", "DZ", "II", "RS", "SF", "SFP", "SGF", "TOF", "TON", "TP", "UA", "UB", "UC", "UI", "UА", "UБНН", "UС", "VD", "АВ", "ВС", "СА", "ЗАКАЗА", "ЗАЩИТ", "РЕМОНТ", "СХЕМ", "СХЕМЫ", "ФУНКЦИИ",
                     "ЦЕПЕЙ", "KR", "KХ", "RJ", "RU", "АААА", "ВC", "ВЭД", "ИК", "ИЛИ", "ИС", "ИФ", "КОД", "НЕ", "НИ", "НК", "НФ", "ОКПД", "ООО", "ПАО", "РАБОТА", "СЕРВИС", "ТП", "ФЗ", "ФФ", "ЮНИТ", "ЮТКБ"]
    
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
    return tex_list 

def parse_tex_new(new_word_list, dict):
    tex_list = []
    for key in new_word_list:
        if key in dict:
            val = dict[key] 
            if val.startswith('!'):
                val = val[1:]
                temp = '\\textcolor{red}{'+val+'}'
                tex_list.append(f'{key} & -- & {temp}; \\\\'+'\n')
            else:
                tex_list.append(f'{key} & -- & {val}; \\\\'+'\n')
    # Меняем в последней строке ; на точку
    if tex_list:
            last_element_index = len(tex_list) - 1
            last_element = tex_list[last_element_index]
            updated_last_element = last_element.replace('; \\\\\n', '. \\\\\n')
            tex_list[last_element_index] = updated_last_element
    return tex_list

########################## ТОЧКА ВХОДА ###################################
def start_abbr(filepath):

    Logger.info("Запуск скрипта обновления абревиатур...")

    #pdf_path = filepath+'/general.pdf'
    path_to_pdf = replace_pdf_with_attrs_txt(filepath)

    Logger.info(f"Обработка {path_to_pdf[0]}")
    word_list_origin = extract_words_from_pdf(path_to_pdf[0])

    # убираем повторяющиеся слова
    word_set = set(word_list_origin)
    word_list = sorted(list(word_set))
    # вытаскиваем абревиатуры
    new_word_list = sorted(get_abbrs(word_list))
    Logger.info(new_word_list)

    # если список пустой возвращаемся
    if not new_word_list:
        Logger.info("Нет распознанных абревиатур в текущем файле pdf...")
        return 'noabbrs'

    ####################################################
    # Вывод списка аббревиатур в файл
    with open(path_to_pdf[2], 'w', encoding='utf-8') as file:
        file.write(', '.join(new_word_list))

    with open('dictionary.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Извлекаем множество ключей (сокращений)
        exclude_keys = set(data.keys())

    # Фильтруем new_word_list, оставляя только те слова, которых нет в exclude_keys
    new_abbrs = [word for word in new_word_list if word not in exclude_keys]

    # Записываем (или перезаписываем) файл с двумя строками
    with open(path_to_pdf[2], 'w', encoding='utf-8') as file:
        file.write("Список всех найденных сокращений в general.pdf: " + ", ".join(new_word_list) + "\n")
        file.write("Список новых сокращений для добавления в dictionary.json: " + ", ".join(new_abbrs))
    
    # Открытие файла, чтобы убедиться, что нет новых аббревиатур. Если есть, добавить новые аббревиатуры в dictionary.json
    os.startfile(path_to_pdf[2])
    ####################################################

    # Ищем файл со словарем
    dict = load_dict(abbrs)
    # старое решение
    tex_list = parse_tex(new_word_list, dict) 
    # новое решение

    #abbrs_got = get_abbrs_new(word_list, dict) # получили все аббревиатуры , причем только те, что в словаре
    #tex_list = parse_tex_new(abbrs_got, dict)
    final_tex = intro_strs + tex_list + outro_strs

    # Открываем файл для записи в UTF-8
    with open(path_to_pdf[1], 'w', encoding='utf-8') as file:
        for line in final_tex:
            file.write(line)  # Добавляем символ новой строки после каждой строки

    Logger.info("Останов скрипта поиска абревиатур...")
    return

