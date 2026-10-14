import configparser
import os
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from logger.logger import Logger
Logger.set_mode('gui')
Logger.enable_file_logging("log_ieds.txt")


def find_ieds_by_numbers(numbers, folders):
    """Поиск устройств по номерам (например, 01.01)"""
    result = []
    for num in numbers:
        for folder in folders:
            # Ищем совпадение в начале имени папки (01.01 РЭ ...)
            if folder.startswith(num + ' ') or folder.startswith(num + '.'):
                result.append(folder)
                break
    return result


def sanitize_filename(text):
    invalid_chars = r'[<>:"/\\|?*]'
    cleaned = re.sub(invalid_chars, '_', text)
    return cleaned.strip()


def get_final_pdf_name(tex_file):
    """Формирует имя PDF: Тип (Код)_Версия.pdf"""
    try:
        with open(tex_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        code = re.search(r'\\def\\devicecode\{([^}]+)\}', content)
        dtype = re.search(r'\\def\\devicetype\{([^}]+)\}', content)
        rev = re.search(r'\\def\\rev\{([^}]+)\}', content)
        
        t_val = dtype.group(1).strip() if dtype else "TYPE"
        c_val = code.group(1).strip() if code else "CODE"
        r_val = rev.group(1).strip() if rev else "v1"
        
        invalid_chars = r'[<>:"/\\|?*]'
        t_safe = re.sub(invalid_chars, '_', t_val)  # ← Теперь НЕ удаляем ничего
        c_safe = re.sub(invalid_chars, '_', c_val)
        
        r_clean = re.sub(r'[^a-zA-Z0-9._-]', '', r_val)
        if not r_clean: 
            r_clean = "v1.0"
            
        name = f"{t_safe} ({c_safe})_v{r_clean}.pdf"
        return name
        
    except Exception as e:
        Logger.error(f"Ошибка формирования имени PDF: {e}")
        return "general.pdf"


def compile_latex_ied(tex_dir):
    """Компиляция general.tex в general.pdf (2 прохода)"""
    original_dir = os.getcwd()
    os.chdir(tex_dir)
    
    try:
        for i in range(1, 3):
            Logger.info(f"Компиляция LaTeX IED (проход {i}/2)")
            result = subprocess.run(
                ['lualatex', '-interaction=nonstopmode', '-halt-on-error', 
                 '-synctex=1', '-jobname=general', 'general.tex'],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120
            )
            if result.returncode != 0:
                Logger.error(f"Ошибка LaTeX IED на проходе {i}")
                return False
        return True
    except Exception as e:
        Logger.error(f"Сбой компиляции LaTeX IED: {e}")
        return False
    finally:
        os.chdir(original_dir)


def copy_and_rename_pdf_ied(tex_dir, tex_file, save_path):
    source_pdf = tex_dir / "general.pdf"
    if not source_pdf.exists():
        Logger.error(f"Файл general.pdf не найден после компиляции IED")
        return
    
    target_dir = Path(save_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    final_name = get_final_pdf_name(tex_file)
    dest_pdf = target_dir / final_name
    
    try:
        shutil.copy2(str(source_pdf), str(dest_pdf))
        Logger.success(f"PDF IED скопирован: {dest_pdf}")
    except Exception as e:
        Logger.error(f"Ошибка копирования PDF IED: {e}")



def update_tex_fields_ied(tex_file, rev_cfg, date_cfg):
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





def process_ied(ied_path, tex_dir, tex_file, revision, date, save_path):
    Logger.info(f"Обработка устройства: {ied_path.name}")
    
    update_tex_fields_ied(tex_file, revision, date)
    
    if compile_latex_ied(tex_dir):
        if save_path:
            copy_and_rename_pdf_ied(tex_dir, tex_file, save_path)
        else:
            Logger.info("PATH_TO_SAVE не указан, PDF остался в папке устройства")
    else:
        Logger.error(f"Компиляция IED не удалась: {ied_path.name}")


def process_ieds():
    config = configparser.ConfigParser()
    config.read('ieds.cfg', encoding='utf-8')

    path = Path(config['GENERAL']['PATH']) 
    mode = config['IEDS']['MODE'].lower()
    names_list = [n.strip() for n in config['IEDS']['NAMES'].split(',') if n.strip()]
    
    revision = config.get('LATEX', 'REVISION', fallback='')
    date = config.get('LATEX', 'DATE', fallback='')
    save_path = config.get('LATEX', 'PATH_TO_SAVE', fallback='')

    if not path.exists():
        Logger.error(f"Путь к устройствам не найден: {path}")
        return

    all_ieds = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]

    if mode == 'all':
        target = all_ieds
    elif mode == 'except':
        excluded = find_ieds_by_numbers(names_list, all_ieds)
        target = [c for c in all_ieds if c not in excluded]
    else: 
        target = find_ieds_by_numbers(names_list, all_ieds)

    if not target:
        Logger.warning("Не найдено устройств для обработки")
        return

    for ied_name in target:
        ied_path = path / ied_name
        
        # Ищем general.tex (в _manual_latex или в корне)
        tex_dir = ied_path / "_manual_latex"
        tex_file = tex_dir / "general.tex"
        
        if not tex_file.exists():
            tex_dir = ied_path
            tex_file = ied_path / "general.tex"

        if tex_file.exists():
            process_ied(ied_path, tex_dir, tex_file, revision, date, save_path)
        else:
            Logger.warning(f"general.tex не найден в: {ied_name}")

    Logger.success("Обработка устройств завершена")
    
if __name__ == "__main__":
    process_ieds()