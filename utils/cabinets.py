import configparser
import os
import re
import shutil
import subprocess
from core.CabDwgProcessor import CabDwgProcessor
from pathlib import Path
from datetime import datetime

from logger.logger import Logger
Logger.set_mode('gui')
Logger.enable_file_logging("log.txt")


def find_cabinets_by_numbers(numbers, folders):
    result = []
    for num in numbers:
        for folder in folders:
            if folder.startswith(num + '.') or folder.startswith(num + ' '):
                result.append(folder)
                break
    return result


def sanitize_filename(text):
    """Очистка имени файла от недопустимых символов"""
    invalid_chars = r'[<>:"/\\|?*]'
    cleaned = re.sub(invalid_chars, '_', text)
    return cleaned.strip()


def get_final_pdf_name(tex_file):
    """Формирует финальное имя PDF на основе параметров general.tex"""
    try:
        with open(tex_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        code = re.search(r'\\def\\devicecode\{([^}]+)\}', content)
        dtype = re.search(r'\\def\\devicetype\{([^}]+)\}', content)
        rev = re.search(r'\\def\\rev\{([^}]+)\}', content)
        
        c = sanitize_filename(code.group(1)) if code else "CODE"
        t = sanitize_filename(dtype.group(1)) if dtype else "TYPE"
        r = sanitize_filename(rev.group(1)) if rev else "v1"
        
        # Чистим версию от мусора для имени файла
        r_clean = re.sub(r'[^a-zA-Z0-9._-]', '', r) or "v1"
        
        #name = f"{t}_{c}_{r_clean}.pdf"
        new_t = t.replace("-ЮИРЗ", "")
        name = f"{new_t} ({c})_v{r_clean}.pdf"
        return re.sub(r'_+', '_', name)
    except Exception as e:
        Logger.error(f"Ошибка формирования имени PDF: {e}")
        return "general.pdf"


def compile_latex(tex_dir):
    """Компилирует general.tex в general.pdf (2 прохода)"""
    original_dir = os.getcwd()
    os.chdir(tex_dir)
    
    try:
        for i in range(1, 3):
            Logger.info(f"Компиляция LaTeX (проход {i}/2)")
            result = subprocess.run(
                ['lualatex', '-interaction=nonstopmode', '-halt-on-error', 
                 '-synctex=1', '-jobname=general', 'general.tex'],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120
            )
            
            if result.returncode != 0:
                Logger.error(f"Ошибка LaTeX на проходе {i}")
                return False
        return True
    except Exception as e:
        Logger.error(f"Сбой компиляции LaTeX: {e}")
        return False
    finally:
        os.chdir(original_dir)


def copy_and_rename_pdf(tex_dir, tex_file, save_path):
    """Копирует general.pdf в целевую папку и переименовывает"""
    source_pdf = tex_dir / "general.pdf"
    
    if not source_pdf.exists():
        Logger.error(f"Файл general.pdf не найден после компиляции")
        return
    
    target_dir = Path(save_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    final_name = get_final_pdf_name(tex_file)
    dest_pdf = target_dir / final_name
    
    try:
        # Копируем файл (копия остается и в источнике)
        shutil.copy2(str(source_pdf), str(dest_pdf))
        Logger.success(f"PDF скопирован: {dest_pdf}")
    except Exception as e:
        Logger.error(f"Ошибка копирования PDF: {e}")


def update_tex_fields(tex_file, cab_name, rev_cfg, date_cfg):
    r"""Меняет ТОЛЬКО \def\rev{...} и \def\revdate{...}.
    Если значения не указаны в конфиге — НЕ МЕНЯЕТ."""
    with open(tex_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Версия (Rev) — меняем ТОЛЬКО если указана в конфиге
    if rev_cfg and rev_cfg.strip():
        new_rev = rev_cfg.strip()
        # Используем lambda для безопасной подстановки
        content = re.sub(
            r'^\\def\\rev\{([^}]+)\}',
            lambda m: f'\\def\\rev{{{new_rev}}}',
            content,
            flags=re.MULTILINE
        )

    # 2. Дата (RevDate) — меняем ТОЛЬКО если указана в конфиге
    if date_cfg and date_cfg.strip():
        new_date = date_cfg.strip()
        # Используем lambda для безопасной подстановки
        content = re.sub(
            r'^\\def\\revdate\{([^}]+)\}',
            lambda m: f'\\def\\revdate{{{new_date}}}',
            content,
            flags=re.MULTILINE
        )

    with open(tex_file, 'w', encoding='utf-8') as f:
        f.write(content)


def process_cabinet(cab_path, latex_mode, revision, date, save_path):
    Logger.info(f"Начало обработки: {cab_path.name}")
    
    tex_dir = cab_path / "_manual_latex"
    tex_file = tex_dir / "general.tex"
    has_latex = tex_file.exists()

    if latex_mode == 'regenerate':
        # ТОЛЬКО обработка DWG
        doc_dir = cab_path / "Документация"
        if doc_dir.exists():
            dwg_files = list(doc_dir.glob("*.dwg"))
            if dwg_files:
                Logger.info("Запуск CabDwgProcessor (регенерация приложений)")
                appx = CabDwgProcessor()
                appx.run(str(cab_path))
            else:
                Logger.warning("Нет DWG для регенерации")
        else:
            Logger.warning("Нет папки Документация")

    elif latex_mode == 'update':
        if has_latex:
            Logger.info("Обновление general.tex и компиляция")
            update_tex_fields(tex_file, cab_path.name, revision, date)
            
            if compile_latex(tex_dir):
                if save_path:
                    copy_and_rename_pdf(tex_dir, tex_file, save_path)
                else:
                    Logger.info("PATH_TO_SAVE не указан, PDF остался в _manual_latex")
            else:
                Logger.error("Компиляция не удалась")
        else:
            Logger.error("Нет general.tex для обновления")

    Logger.success(f"Готово: {cab_path.name}")


def process_cabinets():
    config = configparser.ConfigParser()
    config.read('cabinets.cfg', encoding='utf-8')

    path = Path(config['GENERAL']['PATH'])
    mode = config['CABINETS']['MODE'].lower()
    names_list = [n.strip() for n in config['CABINETS']['NAMES'].split(',') if n.strip()]
    
    latex_mode = config.get('LATEX', 'MODE', fallback='regenerate').lower()
    revision = config.get('LATEX', 'REVISION', fallback='')
    date = config.get('LATEX', 'DATE', fallback='')
    save_path = config.get('LATEX', 'PATH_TO_SAVE', fallback='')

    all_cabs = [f for f in os.listdir(path) 
                if os.path.isdir(os.path.join(path, f)) and "ШЭТ" in f]

    if mode == 'all': target = all_cabs
    elif mode == 'except':
        excluded = find_cabinets_by_numbers(names_list, all_cabs)
        target = [c for c in all_cabs if c not in excluded]
    else: target = find_cabinets_by_numbers(names_list, all_cabs)

    for cab in target:
        process_cabinet(path / cab, latex_mode, revision, date, save_path)

    Logger.success("Пакетная обработка завершена")

if __name__ == "__main__":
    process_cabinets()