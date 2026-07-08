# Класс LatexDoc - создает проект в формате Latex
# принимает при инициализации путь к документу general.tex
# создает директории latex_build и latex_build/images

import re, shutil
from pathlib import Path

from logger.logger import Logger

class LatexDoc:
    def __init__(self, path_to_latex_doc):

        self.path_to_latex_doc = Path(path_to_latex_doc).resolve()
        self.fbpath = None
        self.genpath = None
        self.apppath = None 

        self.image_counter = 1
        self.build_dir = Path("latex_build")
        self.images_dir = self.build_dir / "images"

        self._handle_tex()

    def _process_images(self, lines):
        """
        Обрабатывает \\includegraphics: копирует изображения в latex_build/images,
        переименовывает в img1, img2... и меняет путь в строке.
        """
        pattern = re.compile(r'(\\includegraphics(?:\[[^]]*\])?(?:\{[^}]*\})*)\{([^}]*)\}')

        for i, line in enumerate(lines):
            if '\\includegraphics' not in line:
                continue

            matches = list(pattern.finditer(line))
            if not matches:
                continue

            new_line = line
            for match in reversed(matches):
                before = match.group(1)
                img_ref = match.group(2).strip()

                # --- Проверка: уже обработанный файл? ---
                if re.match(r'img\d+\.(pdf|png|jpg|jpeg|gif)$', img_ref, re.IGNORECASE):
                    Logger.info(f"Пропускаем уже обработанный файл: {img_ref}")
                    continue

                # --- Шаг 1: Определяем полный путь к исходному изображению ---
                full_img_path = None
                
                # Если путь содержит макросы, заменяем их
                if r'\fbpath' in img_ref and self.fbpath:
                    img_ref_clean = img_ref.replace(r'\fbpath', self.fbpath)
                    full_img_path = Path(img_ref_clean.replace('\\', '/'))
                elif r'\genpath' in img_ref and self.genpath:
                    img_ref_clean = img_ref.replace(r'\genpath', self.genpath)
                    full_img_path = Path(img_ref_clean.replace('\\', '/'))
                elif r'\apppath' in img_ref and self.apppath:
                    img_ref_clean = img_ref.replace(r'\apppath', self.apppath)
                    full_img_path = Path(img_ref_clean.replace('\\', '/'))
                else:
                    # Если нет макросов, ищем относительно директории документа
                    possible_paths = [
                        self.path_to_latex_doc / img_ref,
                        self.path_to_latex_doc / "images" / img_ref,
                        self.path_to_latex_doc / "figures" / img_ref,
                        self.path_to_latex_doc / "graphics" / img_ref,
                        Path(img_ref)  # абсолютный путь
                    ]
                    
                    for path in possible_paths:
                        if path.is_file():
                            full_img_path = path
                            break
                
                # Если путь не найден, пробуем найти файл по имени
                if full_img_path is None or not full_img_path.is_file():
                    img_name = Path(img_ref).name
                    search_paths = [
                        self.path_to_latex_doc,
                        self.path_to_latex_doc / "images",
                        self.path_to_latex_doc / "figures",
                        self.path_to_latex_doc / "graphics"
                    ]
                    
                    for base_path in search_paths:
                        if base_path.exists():
                            for file in base_path.rglob(img_name):
                                if file.is_file():
                                    full_img_path = file
                                    break
                            if full_img_path and full_img_path.is_file():
                                break
                
                # --- Шаг 2: Проверяем существование ---
                if full_img_path is None or not full_img_path.is_file():
                    Logger.error(f"Файл изображения не найден: {img_ref}")
                    continue

                # --- Шаг 3: Определяем расширение и новое имя ---
                ext = full_img_path.suffix.lower()
                new_name = f"img{self.image_counter}{ext}"
                dest_path = self.images_dir / new_name

                # --- Шаг 4: Копируем файл ---
                try:
                    shutil.copy(full_img_path, dest_path)
                    Logger.info(f"Скопировано: {full_img_path} в {dest_path}")
                except Exception as e:
                    Logger.error(f"Ошибка копирования {full_img_path}: {e}")
                    continue

                # --- Шаг 5: Формируем новый путь для LaTeX ---
                latex_new_path = new_name
                
                # --- Шаг 6: Заменяем путь в строке ---
                start, end = match.span()
                new_line = new_line[:start] + f"{before}{{{latex_new_path}}}" + new_line[end:]
                
                # --- Шаг 7: Увеличиваем счётчик ---
                self.image_counter += 1

            lines[i] = new_line

    def _add_lines_from_tex(self, target_list, file_path):
        """
        Добавляет строки из .tex-файла в target_list.
        Пропускает комментарии и пустые строки.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    #  Пропускаем комментарии и ПОКА НЕ !!! пустые строки - ломается верстка - например в КС контроле синхронизма
                    if stripped.startswith('%'):
                        continue
                    # Добавляем оригинальную строку (не stripped!), но без \input обработки
                    target_list.append(line)
        except Exception as e:
            Logger.error(f"Ошибка чтения файла {file_path}: {e}")

    def _get_normalized_path(self, line):
        # Удаляем комментарии (всё после %)
        clean_line = line.split('%', 1)[0].strip()
        
        # Ищем \input{...} и извлекаем путь
        match = re.search(r'\\input\{([^}]*)\}', clean_line)
        if not match:
            return None  # или raise, если ожидается, что строка должна быть с \input

        relative_path = match.group(1).strip()

        # Заменяем макросы на реальные пути
        full_path = relative_path
        if r'\fbpath' in full_path:
            full_path = full_path.replace(r'\fbpath', self.fbpath)
        elif r'\genpath' in full_path:
            full_path = full_path.replace(r'\genpath', self.genpath)
        elif r'\apppath' in full_path:
            full_path = full_path.replace(r'\apppath', self.apppath)
        else:
            full_path = str(self.path_to_latex_doc / relative_path)
        
        # Если макросов не было, просто используем как есть (относительный путь)
        # Предполагаем, что он относительно какой-то базовой директории, если нужно — можно добавить base_path

        # Нормализуем путь: убираем дублирующие слеши, приводим к стандарту
        normalized_path = Path(full_path).resolve()

        # Если нужно — возвращаем как строку с прямыми слешами (удобно для LaTeX и кроссплатформенности)
        return normalized_path

    def _handle_tex(self):

        with open(self.path_to_latex_doc / 'general.tex', 'r', encoding='utf-8') as file:
            lines = file.readlines()
            #lines = [line.rstrip('\n') for line in file]

        ################################## 1 проход ######################################
        # Первый проход - ищем пути
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('%'):  # Пропускаем комментарии
                continue
            if r'\newcommand{\fbpath}' in line:
                # Извлекаем путь из фигурных скобок
                if '{' in line and '}' in line:
                    self.fbpath = line.split('{', 2)[2].split('}', 1)[0]
                else:
                    self.fbpath = None  # Путь пустой или некорректный
            if r'\newcommand{\genpath}' in line:
                # Извлекаем путь из фигурных скобок
                if '{' in line and '}' in line:
                    self.genpath = line.split('{', 2)[2].split('}', 1)[0]
                else:
                    self.genpath = None  # Путь пустой или некорректный
            if r'\newcommand{\apppath}' in line:
                # Извлекаем путь из фигурных скобок
                if '{' in line and '}' in line:
                    self.apppath = line.split('{', 2)[2].split('}', 1)[0]
                else:
                    self.apppath = None  # Путь пустой или некорректный
            # Проверяем, что все пути найдены (могут быть None)
            if self.fbpath is not None and self.genpath is not None and self.apppath is not None:
                break
     

        ################################## 2 проход ######################################
        # Второй проход - собираем inputs

        raw_tex =[]
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('%') or not line.strip():  # Пропускаем комментарии и пустые строки
                continue
            if r'\input' in line: # если есть input в строке то добавляем содержимое в raw_tex, сначала находя полный путь
                normal_path = self._get_normalized_path(line)
                self._add_lines_from_tex(raw_tex, normal_path)
                continue
            raw_tex.append(line)

        ################################## 3 проход ######################################
        # Третий проход - меняем пути в includegraphics

        #for line in raw_tex:
        self._process_images(raw_tex)

        # Сохраняем
        with open('latex_build/raw.tex', 'w', encoding='utf-8') as f:
            f.writelines(raw_tex)

