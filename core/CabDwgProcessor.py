import subprocess
import os
import win32com.client
import time
from win32com.client import constants

from pathlib import Path
import textwrap
import ezdxf
from ezdxf.math import Matrix44, Vec3

import fitz  # PyMuPDF
import json
import re
import shutil

from logger.logger import Logger

# НАСТРОЙКИ ПУТЕЙ К АВТОКАДУ
#ACAD = "AutoCAD.Application" # для AutoCad 2026
ACAD = "AutoCAD.Application.23" # для AutoCad 2020
#ACONSOLE = r"C:\Program Files\Autodesk\AutoCAD 2026\accoreconsole.exe"
ACONSOLE = r"C:\Program Files\Autodesk\AutoCAD 2020\accoreconsole.exe"


class CabDwgProcessor:
    def __init__(self):
        # Конфигурация отступов как атрибут класса
        self.margins_config = {
            'A4_portrait': (6, 6, 6, 21),    # верх, право, низ, лево
            'A4_landscape': (0, 0, 0, 0),
            'A3_portrait': (5, 5, 5, 5),
            'A3_landscape': (5, 5, 5, 20),   # верх, право, низ, лево
            'A2_portrait': (6, 6, 21, 6),
            'A2_landscape': (6, 21, 6, 6),
            'default': (6, 6, 6, 6),
        }
        self.mm_to_points = 2.83465

    def convert_dwg_to_dxf_com(self, dwg_path, dxf_path):
        """Конвертация DWG в DXF через COM-автоматизацию"""
        
        Logger.info("Запуск конвертации DWG → DXF (через COM)...")
        Logger.info(f"Входной файл: {dwg_path}")
        Logger.info(f"Выходной файл: {dxf_path}")
        
        if not os.path.exists(dwg_path):
            Logger.error(f"Ошибка: Входной файл не найден: {dwg_path}")
            return False
        
        try:
            # Создаём экземпляр AutoCAD
            acad = win32com.client.Dispatch(ACAD)
            acad.Visible = False  # Скрытый режим
            
            # Открываем DWG
            doc = acad.Documents.Open(dwg_path)
            
            # Сохраняем как DXF
            # Константы форматов:
            # 13 = AC1015
            # 25 = AC1018
            # 37 = AC1021
            # 49 = AC1024
            # 61 = AC1027
            
            doc.SaveAs(dxf_path, 61) 

            # Закрываем документ
            doc.Close(False)
            
            # Закрываем AutoCAD
            acad.Quit()
            
            # Освобождаем ресурсы
            del acad
            
            # Проверяем результат
            if os.path.exists(dxf_path):
                size = os.path.getsize(dxf_path)
                Logger.info("DXF успешно создан!")
                Logger.debug(f"Путь: {dxf_path}")
                Logger.debug(f" Размер: {size} байт ({size/1024:.2f} KB)")
                return True
            else:
                Logger.error("Ошибка: DXF файл не создан")
                return False
                
        except Exception as e:
            Logger.error(f"Ошибка при конвертации: {e}")
            return False

    def create_dsd_from_dxf(self, dxf_path, dsd_path, output_pdf_path, pdf_printer="DWG To PDF.pc3"):
        """
        Создает DSD-файл на основе листов указанного DXF-чертежа.
        Листы записываются в порядке вкладок AutoCAD (TabOrder).
        """
        try:
            # 1. Подключаемся к AutoCAD для получения списка листов
            acad = win32com.client.Dispatch(ACAD)
            doc = acad.Documents.Open(dxf_path)
            
            # Получаем листы вместе с TabOrder для гарантированной визуальной сортировки
            layouts_with_order = []
            for layout in doc.Layouts:
                if layout.Name != "Model":
                    layouts_with_order.append((layout.TabOrder, layout.Name))
                    
            doc.Close(False)
            
            # Сортировка строго по порядку вкладок в интерфейсе AutoCAD
            layouts_with_order.sort(key=lambda x: x[0])
            layouts = [name for _, name in layouts_with_order]
            
            # 2. Формируем содержимое DSD-файла
            base_name = os.path.basename(dxf_path)
            
            dsd_content = "[DWF6Version]\nVer=1\n[DWF6MinorVersion]\nMinorVer=1\n"
            
            for i, layout_name in enumerate(layouts):
                section_name = f"[DWF6Sheet:{i+1}-{layout_name}]"
                dsd_content += f"{section_name}\n"
                dsd_content += f"DWG={dxf_path}\n"
                dsd_content += f"Layout={layout_name}\n"
                dsd_content += f"Setup=\n"
                dsd_content += f"OriginalSheetPath={dxf_path}\n"
                dsd_content += f"Has Plot Port=0\n"
                dsd_content += f"Has3DDWF=0\n"
                
            out_folder = os.path.dirname(output_pdf_path)
            dsd_content += f"[Target]\nType=6\n"
            dsd_content += f"DWF={output_pdf_path}\n"
            dsd_content += f"OUT={out_folder}\n"
            dsd_content += f"PWD=\n"
            
            dsd_content += f"""[PdfOptions]
        IncludeHyperlinks=TRUE
        CreateBookmarks=TRUE
        CaptureFontsInDrawing=TRUE
        ConvertTextToGeometry=FALSE
        VectorResolution=1200
        RasterResolution=400
        [SheetSet Properties]
        IsSheetSet=FALSE
        NoOfCopies=1
        PlotStampOn=FALSE
        AcadProfile=<<Текущий профиль>>
        """
            with open(dsd_path, 'w', encoding='cp1251') as f:
                f.write(dsd_content)
                
            Logger.success(f"DSD-файл успешно создан: {dsd_path}")
            Logger.info(f"Найдено листов: {len(layouts)}")
            Logger.info(f"Порядок вкладок: {layouts}")
            return True

        except Exception as e:
            Logger.error(f"Ошибка при создании DSD: {e}")
            return False

    def clean_dxf(self, dxf_file):

        # Основные штампы (удаляются вместе с содержимым внутри)
        target_blocks = [
            "Штамп большой нижний", 
            "Штамп большой нижний текстовый", 
            "Штамп левый верхний", 
            "Штамп левый нижний", 
            "Штамп малый нижний", 
            "Штамп угловой верхний"
        ]

        # Специальные блоки (удаляется только сама вставка блока, содержимое остается)
        target_blocks_special = ["Формат_А4", "Формат_А3"]

        target_areas = [124740, 111520]
        area_tolerance = 10.0

        doc = ezdxf.readfile(dxf_file)
        msp = doc.modelspace()

        # --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

        def get_polyline_area(entity):
            """Вычисляет площадь полилинии."""
            dxftype = entity.dxftype()
            if dxftype == 'LWPOLYLINE':
                try:
                    return entity.get_area()
                except:
                    pass
            
            points = []
            if dxftype == 'POLYLINE':
                for v in entity.vertices:
                    points.append((v.dxf.location.x, v.dxf.location.y))
            elif dxftype == 'LWPOLYLINE':
                for p in entity.get_points(format='xyb'):
                    points.append((p[0], p[1]))
            
            if len(points) >= 3:
                n = len(points)
                area = 0.0
                for i in range(n):
                    j = (i + 1) % n
                    area += points[i][0] * points[j][1] - points[j][0] * points[i][1]
                return abs(area) / 2.0
            return None

        def get_block_bbox(entity):
            """Возвращает ограничивающий прямоугольник блока в мировых координатах."""
            block_def = doc.blocks.get(entity.dxf.name)
            if not block_def:
                return None
            
            points = []
            for e in block_def:
                dxftype = e.dxftype()
                if dxftype == 'INSERT':
                    points.append(Vec3(e.dxf.insert.x, e.dxf.insert.y, 0))
                elif dxftype == 'LINE':
                    points.append(Vec3(e.dxf.start.x, e.dxf.start.y, 0))
                    points.append(Vec3(e.dxf.end.x, e.dxf.end.y, 0))
                elif dxftype in ('CIRCLE', 'ARC'):
                    center = Vec3(e.dxf.center.x, e.dxf.center.y, 0)
                    radius = getattr(e.dxf, 'radius', 0)
                    points.append(center)
                    if radius > 0:
                        points.extend([
                            center + Vec3(radius, 0, 0), center + Vec3(-radius, 0, 0),
                            center + Vec3(0, radius, 0), center + Vec3(0, -radius, 0)
                        ])
                elif dxftype in ('LWPOLYLINE', 'POLYLINE'):
                    try:
                        if dxftype == 'LWPOLYLINE':
                            for p in e.get_points(format='xyb'):
                                points.append(Vec3(p[0], p[1], 0))
                        else:
                            for v in e.vertices:
                                points.append(Vec3(v.dxf.location.x, v.dxf.location.y, 0))
                    except:
                        pass
                elif dxftype in ('TEXT', 'MTEXT'):
                    if hasattr(e.dxf, 'insert'): points.append(Vec3(e.dxf.insert.x, e.dxf.insert.y, 0))
                    elif hasattr(e.dxf, 'location'): points.append(Vec3(e.dxf.location.x, e.dxf.location.y, 0))
                elif dxftype == 'SPLINE':
                    try:
                        for p in e.control_points:
                            points.append(Vec3(float(p[0]), float(p[1]), float(p[2])))
                    except: pass
                elif dxftype == 'POINT':
                    if hasattr(e.dxf, 'location'): points.append(Vec3(e.dxf.location.x, e.dxf.location.y, 0))
            
            if not points: return None
            
            min_x = min(p.x for p in points)
            max_x = max(p.x for p in points)
            min_y = min(p.y for p in points)
            max_y = max(p.y for p in points)
            
            m = Matrix44.z_rotate(entity.dxf.rotation)
            m = m @ Matrix44.scale(entity.dxf.xscale, entity.dxf.yscale, 1)
            m = m @ Matrix44.translate(entity.dxf.insert.x, entity.dxf.insert.y, 0)
            
            corners = [
                Vec3(min_x, min_y, 0), Vec3(max_x, min_y, 0),
                Vec3(max_x, max_y, 0), Vec3(min_x, max_y, 0)
            ]
            transformed = [m.transform(c) for c in corners]
            
            xs = [c.x for c in transformed]
            ys = [c.y for c in transformed]
            return (min(xs), min(ys), max(xs), max(ys))

        def is_point_in_bbox(x, y, bbox, tolerance=1.0):
            if bbox is None: return False
            return (bbox[0] - tolerance <= x <= bbox[2] + tolerance and 
                    bbox[1] - tolerance <= y <= bbox[3] + tolerance)

        def get_entity_point(entity):
            dxftype = entity.dxftype()
            if dxftype == 'INSERT': return (entity.dxf.insert.x, entity.dxf.insert.y)
            elif dxftype == 'LINE': return ((entity.dxf.start.x + entity.dxf.end.x) / 2, (entity.dxf.start.y + entity.dxf.end.y) / 2)
            elif dxftype in ('CIRCLE', 'ARC'): return (entity.dxf.center.x, entity.dxf.center.y)
            elif dxftype in ('LWPOLYLINE', 'POLYLINE'):
                try:
                    if dxftype == 'LWPOLYLINE':
                        pts = list(entity.get_points(format='xyb'))
                        if pts: return (pts[0][0], pts[0][1])
                    else:
                        v = list(entity.vertices)
                        if v: return (v[0].dxf.location.x, v[0].dxf.location.y)
                except: pass
            elif dxftype in ('TEXT', 'MTEXT'):
                if hasattr(entity.dxf, 'insert'): return (entity.dxf.insert.x, entity.dxf.insert.y)
                elif hasattr(entity.dxf, 'location'): return (entity.dxf.location.x, entity.dxf.location.y)
            elif dxftype == 'DIMENSION':
                if hasattr(entity.dxf, 'insert'): return (entity.dxf.insert.x, entity.dxf.insert.y)
            elif dxftype == 'POINT':
                if hasattr(entity.dxf, 'location'): return (entity.dxf.location.x, entity.dxf.location.y)
            elif dxftype == 'SPLINE':
                try:
                    cpts = entity.control_points
                    if len(cpts) > 0: return (float(cpts[0][0]), float(cpts[0][1]))
                except: pass
            return None

        def object_inside_stamp(entity, stamp_bboxes, tolerance=2.0):
            point = get_entity_point(entity)
            if point is not None:
                x, y = point
                for bbox in stamp_bboxes:
                    if is_point_in_bbox(x, y, bbox, tolerance): return True
            
            if entity.dxftype() == 'SPLINE':
                try:
                    for p in entity.control_points:
                        x, y = float(p[0]), float(p[1])
                        for bbox in stamp_bboxes:
                            if is_point_in_bbox(x, y, bbox, tolerance): return True
                except: pass
            return False

        # --- ГЛАВНАЯ ЛОГИКА ---

        entities_to_remove = set()
        all_entities = list(msp)

        # ==========================================
        # ЭТАП 1: Удаление штампов и объектов внутри них
        # ==========================================

        Logger.info("ЭТАП 1: Работа со штампами")

        blocks_to_delete = []
        stamp_bboxes = []

        for entity in all_entities:
            if entity.dxftype() == 'INSERT' and entity.dxf.name in target_blocks:
                blocks_to_delete.append(entity)
                bbox = get_block_bbox(entity)
                if bbox:
                    stamp_bboxes.append(bbox)
                    Logger.debug(f"  Найден штамп: {entity.dxf.name}")

        #Logger.info(f"  Найдено штампов: {len(blocks_to_delete)}")

        # Добавляем сами штампы в список на удаление
        for b in blocks_to_delete:
            entities_to_remove.add(b)

        # Ищем объекты внутри штампов
        for entity in all_entities:
            if entity in entities_to_remove: continue
            if object_inside_stamp(entity, stamp_bboxes):
                entities_to_remove.add(entity)

        #Logger.info(f"  Всего объектов к удалению после Этапа 1: {len(entities_to_remove)}")

        # ==========================================
        # ЭТАП 1.5: Удаление специальных блоков (форматок) БЕЗ содержимого
        # ==========================================

        Logger.info("ЭТАП 1.5: Удаление форматок (только блоки)")

        special_blocks_count = 0
        for entity in all_entities:
            if entity in entities_to_remove: continue
            
            if entity.dxftype() == 'INSERT' and entity.dxf.name in target_blocks_special:
                entities_to_remove.add(entity)
                special_blocks_count += 1
                #Logger.info(f"  Помечен на удаление блок: {entity.dxf.name} (содержимое останется)")

        #Logger.info(f"  Найдено форматок для удаления: {special_blocks_count}")

        # ==========================================
        # ЭТАП 2: Удаление полилиний по площади
        # ==========================================

        Logger.info("ЭТАП 2: Удаление рамок по площади")

        area_deleted_count = 0
        for entity in all_entities:
            if entity in entities_to_remove: continue
            
            if entity.dxftype() in ('LWPOLYLINE', 'POLYLINE'):
                area = get_polyline_area(entity)
                if area is not None:
                    for target_area in target_areas:
                        if abs(area - target_area) < area_tolerance:
                            entities_to_remove.add(entity)
                            area_deleted_count += 1
                            Logger.debug(f"  Найдена рамка по площади: {area:.1f} (цель: {target_area})")
                            break

        #Logger.info(f"  Найдено дополнительных рамок по площади: {area_deleted_count}")

        # ==========================================
        # ЭТАП 2.5: Удаление MTEXT с конкретной строкой
        # ==========================================

        Logger.info("ЭТАП 2.5: Удаление MTEXT по тексту")

        target_text = "При наличии у клеммы и пружинного и винтового зажима"
        mtext_deleted_count = 0

        for entity in all_entities:
            if entity in entities_to_remove: continue
            
            if entity.dxftype() == 'MTEXT':
                try:
                    text_content = entity.dxf.text
                    if target_text in text_content:
                        entities_to_remove.add(entity)
                        mtext_deleted_count += 1
                        #Logger.info(f"  Найден MTEXT с целевой строкой (ID: {entity.dxf.handle})")
                except Exception as e:
                    Logger.error(f"  Ошибка при проверке MTEXT: {e}")

        Logger.debug(f"  Найдено MTEXT для удаления: {mtext_deleted_count}")

        # ==========================================
        # ВЫПОЛНЕНИЕ УДАЛЕНИЯ
        # ==========================================
        Logger.debug(f"Итого будет удалено объектов: {len(entities_to_remove)}")

        deleted_count = 0
        for ent in entities_to_remove:
            try:
                msp.delete_entity(ent)
                deleted_count += 1
            except Exception as e:
                Logger.error(f"  Ошибка при удалении {ent.dxftype()}: {e}")

        Logger.debug(f"Фактически удалено: {deleted_count} объектов")

        try:
            doc.saveas("cleaned_dxf.dxf")
            Logger.debug("Файл сохранен как 'cleaned_dxf.dxf'")
        except Exception as e:
            Logger.error(f"Ошибка при сохранении: {e}")

    def print_dxf_to_pdf(self, dxf_name, acadconsole_path, dsd_path, scr_path):

        """
        Создает SCR файл с динамическим путем к DSD
        """
        Logger.info("Запуск публикации...")
        
        # Создаем SCR файл с динамическим путем
        script_content = textwrap.dedent(f"""\
            _.-PUBLISH
            {dsd_path}
            Y
            _.QUIT
        """)

        # Записываем SCR файл
        with open(scr_path, 'w', encoding='cp1251') as f:
            f.write(script_content)
        
        Logger.debug(f"Создан SCR: {scr_path}")
        Logger.debug(f"Используется DSD: {dsd_path}")


        # Меняем кодировку на cp866, чтобы русские логи читались нормально
        result = subprocess.run(
            [acadconsole_path, "/i", str(dxf_name), "/s", str(scr_path)],
            capture_output=True,
            text=True,
            encoding='cp866'
        )

        # Выводим красивый лог
        #print(result.stdout)

        if "Нет ошибок или предупреждений" in result.stdout or "no errors or warnings" in result.stdout.lower():
            #prLogger.infoint("PDF успешно создан!")
            Logger.success("PDF успешно создан!")
        else:
            pass
            #print("Возможны ошибки. Проверьте лог выше.")

    def create_pages_json_from_pdf(self, input_pdf, output_json='pages.json'):
        """
        Анализирует PDF, ищет маркеры группировки и создает pages.json
        """
        if not os.path.exists(input_pdf):
            Logger.error(f"Файл не найден: {input_pdf}")
            return

        # Ключевые фразы и соответствующие им префиксы групп
        markers = {
            "Перечень надписей": "ПН",
            "Перечень элементов": "ПЭ",
            "Схема электрическая принципиальная": "СЭП",
            "Схема электрическая соединений рядов зажимов": "СЭС"
        }
        
        search_phrases = list(markers.keys())
        
        try:
            doc = fitz.open(input_pdf)
            total_pages = len(doc)
            
            Logger.info(f"Анализ PDF: {input_pdf} ({total_pages} страниц)")

            pages_config = {}
            current_group = None
            
            # Временное хранилище: { 'ПН': [1, 2], 'ПЭ': [3] ... }
            temp_groups = {} 

            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()  # Получаем весь текст со страницы
                
                found_phrase = None
                # Ищем любую из фраз-маркеров в тексте страницы
                for phrase in search_phrases:
                    if phrase in text:
                        found_phrase = phrase
                        break
                
                if found_phrase:
                    new_group = markers[found_phrase]
                    Logger.info(f"Стр. {page_num + 1}: Найден маркер '{found_phrase}' -> Группа {new_group}")
                    
                    # Если группа сменилась или это первая страница группы
                    if current_group != new_group:
                        current_group = new_group
                        if current_group not in temp_groups:
                            temp_groups[current_group] = []
                
                # Если у нас есть активная группа, добавляем номер страницы
                if current_group:
                    temp_groups[current_group].append(page_num + 1)
                else:
                    Logger.info(f"  Стр. {page_num + 1}: Пропуск (группа еще не определена)")

            doc.close()

            # Сохраняем результат в JSON
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(temp_groups, f, ensure_ascii=False, indent=4)
                
            Logger.debug(f"Файл {output_json} успешно создан!")
            Logger.info(f"Структура страниц: {json.dumps(temp_groups, ensure_ascii=False)}")

        except Exception as e:
            Logger.error(f"Ошибка при обработке PDF: {e}")
            import traceback
            traceback.print_exc()

    def detect_format(self, width_mm, height_mm, rotation):
        """
        Определяет формат бумаги и ориентацию
        """
        tolerance = 10
        
        # Определяем физический размер без учета поворота
        if rotation in [90, 270]:
            physical_width = height_mm
            physical_height = width_mm
        else:
            physical_width = width_mm
            physical_height = height_mm
        
        # Определяем формат
        if abs(physical_width - 210) < tolerance and abs(physical_height - 297) < tolerance:
            return 'A4_portrait'
        elif abs(physical_width - 297) < tolerance and abs(physical_height - 210) < tolerance:
            return 'A4_landscape'
        elif abs(physical_width - 297) < tolerance and abs(physical_height - 420) < tolerance:
            return 'A3_portrait'
        elif abs(physical_width - 420) < tolerance and abs(physical_height - 297) < tolerance:
            return 'A3_landscape'
        elif abs(physical_width - 420) < tolerance and abs(physical_height - 594) < tolerance:
            return 'A2_portrait'
        elif abs(physical_width - 594) < tolerance and abs(physical_height - 420) < tolerance:
            return 'A2_landscape'
        else:
            # Если не удалось определить, пытаемся определить по фактическому размеру
            if abs(width_mm - 420) < tolerance and abs(height_mm - 297) < tolerance:
                return 'A3_landscape'
            elif abs(width_mm - 297) < tolerance and abs(height_mm - 420) < tolerance:
                return 'A3_portrait'
            else:
                return 'unknown'

    def load_pages_config(self, config_file):
        """
        Загружает конфигурацию страниц из JSON файла
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            Logger.info(f"Загружена конфигурация из {config_file}")
            return config
        except FileNotFoundError:
            Logger.warning("Файл конфигурации {config_file} не найден. Используется стандартное сохранение.")
            return None
        except json.JSONDecodeError as e:
            Logger.error(f"Ошибка чтения JSON файла {config_file}: {e}")
            Logger.info("Используется стандартное сохранение.")
            return None


    def del_files(self, files_list):

        """
        Простое удаление списка файлов
        
        Args:
            files_list: список путей к файлам для удаления
        """
        Logger.info("Удаление временных файлов...")

        
        deleted = 0
        for file_path in files_list:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    Logger.info(f"Удален: {os.path.basename(file_path)}")
                    deleted += 1
                else:
                    Logger.warning(f"Файл не найден: {os.path.basename(file_path)}")
            except Exception as e:
                Logger.error(f"Не удалось удалить {os.path.basename(file_path)}: {e}")
        
        Logger.info(f"Итог: удалено {deleted} из {len(files_list)} файлов")
        
        # Показываем оставшиеся файлы
        remaining = [f for f in files_list if os.path.exists(f)]
        if remaining:
            Logger.warning(f"Остались файлы: {', '.join([os.path.basename(f) for f in remaining])}")
            Logger.info("Возможно, файлы используются другими программами (закройте AutoCAD)")
        else:
            Logger.success("Все файлы успешно удалены!")


    def run(self, base_path):

        self.base_path = base_path

        doc_dir = os.path.join(self.base_path, "Документация")

        # Ищем все PDF файлы в папке
        pdf_files = [f for f in os.listdir(doc_dir) if f.lower().endswith('.dwg')]
        
        if len(pdf_files) > 1:
            Logger.error("Предупреждение: найдено больше одного DWG файла")
            return None
            
        if len(pdf_files) == 0:
            Logger.error("Предупреждение:DWG файлы не найдены")
            return None

        path =  os.path.join(doc_dir, pdf_files[0])
        Logger.info(f"Найден путь к исходному dwg {path}") 

        # Запуск

        dwg_file = path
        # Временные файлы
        current_dir = Path.cwd()
        dxf_file = current_dir/ "temp.dxf"
        dsd_file = current_dir / "temp.dsd"
        pdf_file = current_dir / "temp.pdf"
        pdf_file2 = current_dir / "temp2.pdf"
        scr_path = current_dir/ "publish.scr" # Укажите имя вашего скрипта

        acadconsole_path = ACONSOLE # r"C:\Program Files\Autodesk\AutoCAD 2020\accoreconsole.exe"

        dxf_file_clean = current_dir/ "cleaned_dxf.dxf"


        Logger.info("========================== ШАГ 1 ПРЕОБРАЗУЕМ DWG в DXF ========================")

        self.convert_dwg_to_dxf_com(dwg_file, dxf_file)  
        Logger.info("Ожидание освобождения AutoCAD...")
        time.sleep(3)

        Logger.info("========================== ШАГ 2 СОЗДАЕМ DSD ========================")
        self.create_dsd_from_dxf(dxf_file, dsd_file, pdf_file)
        Logger.info("Ожидание освобождения AutoCAD...")
        time.sleep(3)

        Logger.info("========================== ШАГ 3 - ОЧИСТКА DXF ========================")
        self.clean_dxf(dxf_file)
        Logger.info("Ожидание освобождения AutoCAD...")
        time.sleep(3)

        Logger.info("========================== ШАГ 4 - ПЕЧАТЬ PDF  ========================")
        self.print_dxf_to_pdf(dxf_file, acadconsole_path, dsd_file, scr_path)
        time.sleep(6)

        Logger.info("========================== ШАГ 5 - ИЩЕМ СТРАНИЦЫ  ========================")
        self.create_pages_json_from_pdf(pdf_file) # Должен быть установлен шрият ГОСТ тип А
        time.sleep(3)

        Logger.info("========================== ШАГ 6 - СОЗДАЕМ DSD ДЛЯ ПЕЧАТИ  ========================")
        self.create_dsd_from_dxf(dxf_file_clean, dsd_file, pdf_file2)

        Logger.info("========================== ШАГ 7 - ПЕЧАТЬ ЧИСТОГО PDF  ========================")
        self.print_dxf_to_pdf(dxf_file_clean, acadconsole_path, dsd_file, scr_path)
        time.sleep(3)

        Logger.info("========================== ШАГ 8 - НАРЕЗКА PDF  ========================")
        # Загружаем конфигурацию страниц
        pages_config = self.load_pages_config('pages.json')
        Logger.info("Входной файл: temp.pdf")
        Logger.info("Результат в папке: output_pages")
        self.smart_crop_pdf('temp2.pdf', pages_config)

        Logger.info("========================== ШАГ 9 - УДАЛЯЕМ ВРЕМЕННЫЕ ФАЙЛЫ  ========================")

        # Список файлов для удаления
        files_to_delete = [
            dxf_file,          # temp.dxf
            dsd_file,          # temp.dsd
            scr_path,          # publish.scr
            dxf_file_clean,
            pdf_file,
            pdf_file2,
            current_dir/"pages.json",
            current_dir/"plot.log"                                    # cleaned_dxf.dxf
        ]

        self.del_files(files_to_delete)

        Logger.success("========================== ПРИЛОЖЕНИЯ ОБНОВЛЕНЫ  ========================")




    # ============================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ АВТО-ОБРЕЗКИ
    # ============================================



    def _normalize_page(self, page, content_box):
        """
        Нормализует CropBox по НАИБОЛЬШЕЙ стороне для максимального заполнения.
        Позволяет гибко настраивать отступы для Landscape и Portrait.
        """
        
        media = page.mediabox
        
        # Определяем ориентацию
        is_landscape = media.width > media.height
        
        # --- НАСТРОЙКИ ОТСТУПОВ (в points) ---
        # 1 pt ≈ 0.35 мм
        
        if is_landscape:
            # === LANDSCAPE (Альбомная) ===
            base_margin = 15      # Лево, Право, Низ
            bind_margin = 15      # Верх (или можно сделать Left, если нужно под сшивку слева)
            
            # Виртуальный бокс: большой отступ сверху, остальные стандартные
            virtual_box = fitz.Rect(
                media.x0 + base_margin,   # Лево
                media.y0 + bind_margin,   # Верх (увеличенный)
                media.x1 - base_margin,   # Право
                media.y1 - base_margin    # Низ
            )
            Logger.debug(f"   Ориентация: LANDSCAPE → Top={bind_margin}, Others={base_margin}")
            
        else:
            # === PORTRAIT (Книжная) ===
            base_margin = 10      # Верх, Право, Низ
            bind_margin = 10      # Лево (под сшивку)
            
            # Виртуальный бокс: большой отступ слева, остальные стандартные
            virtual_box = fitz.Rect(
                media.x0 + bind_margin,   # Лево (увеличенный)
                media.y0 + base_margin,   # Верх
                media.x1 - base_margin,   # Право
                media.y1 - base_margin    # Низ
            )
            Logger.debug(f"   Ориентация: PORTRAIT → Left={bind_margin}, Others={base_margin}")

        c_w = content_box.width
        c_h = content_box.height
        
        # Считаем свободное место внутри ВИРТУАЛЬНОГО box
        free_w = virtual_box.width - c_w
        free_h = virtual_box.height - c_h
        
        # === НОРМАЛИЗАЦИЯ ПО МАКСИМУМУ ===
        max_free = max(free_w, free_h)
        
        # Заполняем всё доступное пространство (можно вычесть небольшой зазор, например 5pt, если нужно)
        total_padding = max(0, max_free) 
        offset = total_padding / 2
        #print(offset) 
        if offset < 100:
            offset = 0  
        if free_w >= free_h:
            # Растягиваем по ширине
            offset_x = offset
            offset_y = 0
            Logger.debug(f"   Нормализация по МАКСИМУМУ (ШИРИНА). Отступ X={offset_x:.1f}")
        else:
            # Растягиваем по высоте
            offset_x = 0
            offset_y = offset
            Logger.debug(f"   Нормализация по МАКСИМУМУ (ВЫСОТА). Отступ Y={offset_y:.1f}")
        
        new_x0 = content_box.x0 - offset_x
        new_y0 = content_box.y0 - offset_y
        new_x1 = content_box.x1 + offset_x
        new_y1 = content_box.y1 + offset_y
        
        new_rect = fitz.Rect(new_x0, new_y0, new_x1, new_y1)
        
        # Финальная защита: intersect с виртуальным box гарантирует, 
        # что мы не выйдем за пределы безопасной зоны
        final_rect = new_rect.intersect(virtual_box)
        
        Logger.debug(f"media: {media}")
        Logger.debug(f"virtual_box: {virtual_box}")
        Logger.debug(f"content: {content_box}")
        Logger.debug(f"final_rect: {final_rect}")

        return final_rect


    def _normalize_page2(self, page, content_box):
        """
        Гибридная нормализация:
        - A3 (любой) и A4 Landscape: по МАКСИМУМУ (для заполнения).
        - A4 Portrait: по МИНИМУМУ (для сохранения пропорций и защиты от обрезки).
        """
        
        media = page.mediabox
        
        # Определяем ориентацию и формат
        width_mm = media.width * 0.352778
        height_mm = media.height * 0.352778
        is_landscape = media.width > media.height
        
        # Простая проверка на A4 (допуск 10 мм)
        is_a4_portrait = (not is_landscape) and (abs(width_mm - 210) < 10) and (abs(height_mm - 297) < 10)

        # --- НАСТРОЙКИ ОТСТУПОВ ---
        if is_landscape:
            # LANDSCAPE (A3/A4 гориз.)
            base_margin = 15
            bind_margin = 40  # Большой отступ сверху
            
            virtual_box = fitz.Rect(
                media.x0 + base_margin,
                media.y0 + bind_margin,
                media.x1 - base_margin,
                media.y1 - base_margin
            )
            normalize_by_max = True # Используем максимум для заполнения
            Logger.debug(f"   Ориентация: LANDSCAPE → Max Norm")
            
        elif is_a4_portrait:
            # A4 PORTRAIT (Вертикальный) - более щадящий режим
            base_margin = 10  # Уменьшаем базовый отступ
            bind_margin = 20  # Уменьшаем отступ под сшивку
            
            virtual_box = fitz.Rect(
                media.x0 + bind_margin,
                media.y0 + base_margin,
                media.x1 - base_margin,
                media.y1 - base_margin
            )
            normalize_by_max = False # Используем минимум для безопасности
            Logger.debug(f"   Ориентация: A4 PORTRAIT → Min Norm")
            
        else:
            # A3 PORTRAIT (Вертикальный) - как было отлично
            base_margin = 20
            bind_margin = 40
            
            virtual_box = fitz.Rect(
                media.x0 + bind_margin,
                media.y0 + base_margin,
                media.x1 - base_margin,
                media.y1 - base_margin
            )
            normalize_by_max = True
            Logger.debug(f"   Ориентация: A3 PORTRAIT → Max Norm")

        c_w = content_box.width
        c_h = content_box.height
        
        free_w = virtual_box.width - c_w
        free_h = virtual_box.height - c_h
        
        if normalize_by_max:
            # === НОРМАЛИЗАЦИЯ ПО МАКСИМУМУ ===
            max_free = max(free_w, free_h)
            total_padding = max(0, max_free)
            offset = total_padding / 2
            
            if free_w >= free_h:
                offset_x = offset
                offset_y = 0
                Logger.debug(f"   Max Norm: ШИРИНА. X={offset_x:.1f}")
            else:
                offset_x = 0
                offset_y = offset
                Logger.debug(f"   Max Norm: ВЫСОТА. Y={offset_y:.1f}")
                
        else:
            # === НОРМАЛИЗАЦИЯ ПО МИНИМУМУ (для A4 Portrait) ===
            min_free = min(free_w, free_h)
            total_padding = max(0, min_free)
            offset = total_padding / 2
            
            if free_w <= free_h:
                offset_x = offset
                offset_y = 0
                Logger.debug(f"   Min Norm: ШИРИНА. X={offset_x:.1f}")
            else:
                offset_x = 0
                offset_y = offset
                Logger.debug(f"   Min Norm: ВЫСОТА. Y={offset_y:.1f}")

        new_x0 = content_box.x0 - offset_x
        new_y0 = content_box.y0 - offset_y
        new_x1 = content_box.x1 + offset_x
        new_y1 = content_box.y1 + offset_y
        
        new_rect = fitz.Rect(new_x0, new_y0, new_x1, new_y1)
        
        # Финальная защита
        final_rect = new_rect.intersect(virtual_box)
        
        Logger.debug(f"media: {media}")
        Logger.debug(f"virtual_box: {virtual_box}")
        Logger.debug(f"content: {content_box}")
        Logger.debug(f"final_rect: {final_rect}")

        return final_rect




    def _find_content_bbox(self, page):
        """Находит bounding box всего содержимого страницы"""
        rects = []
        # Текст
        for word in page.get_text_words():
            rects.append(fitz.Rect(word[0], word[1], word[2], word[3]))
        # Изображения
        for img in page.get_images(full=True):
            rects.extend(page.get_image_rects(img[0]))
        # Графика
        try:
            for path in page.get_drawings():
                if path.get("rect"): rects.append(fitz.Rect(path["rect"]))
                if path.get("items"):
                    for item in path["items"]:
                        if not isinstance(item, tuple) or len(item) < 2: continue
                        cmd = item[0]
                        if cmd == "l" and len(item) >= 5:
                            rects.append(fitz.Rect(min(item[1],item[3]), min(item[2],item[4]), max(item[1],item[3]), max(item[2],item[4])))
                        elif cmd == "re" and len(item) >= 5:
                            rects.append(fitz.Rect(item[1], item[2], item[1]+item[3], item[2]+item[4]))
        except: pass
        
        if not rects: return None
        x0 = min(r.x0 for r in rects); y0 = min(r.y0 for r in rects)
        x1 = max(r.x1 for r in rects); y1 = max(r.y1 for r in rects)
        return fitz.Rect(x0, y0, x1, y1)

    def _auto_crop_by_pixels(self, page, padding=5, dpi=150, white_threshold=250):
        """Обрезает страницу на основе анализа пикселей (высокая точность)"""
        pix = page.get_pixmap(dpi=dpi, colorspace="gray")
        samples = pix.samples
        width = pix.width; height = pix.height
        
        min_x, min_y = width, height; max_x, max_y = 0, 0; found = False
        
        for y in range(0, height, 1): # Шаг 1 для максимальной точности
            for x in range(0, width, 1):
                idx = y * width + x
                if idx < len(samples) and samples[idx] < white_threshold:
                    found = True
                    if x < min_x: min_x = x
                    if x > max_x: max_x = x
                    if y < min_y: min_y = y
                    if y > max_y: max_y = y
        
        if not found: return None
        
        scale_x = page.rect.width / width; scale_y = page.rect.height / height
        x0 = min_x * scale_x; y0 = min_y * scale_y
        x1 = (max_x + 1) * scale_x; y1 = (max_y + 1) * scale_y
        
        content_bbox = fitz.Rect(x0, y0, x1, y1)
        
        # Применяем финальный отступ
        if padding > 0:
            content_bbox = fitz.Rect(
                max(0, content_bbox.x0 - padding), max(0, content_bbox.y0 - padding),
                min(page.rect.width, content_bbox.x1 + padding), min(page.rect.height, content_bbox.y1 + padding)
            )
        return content_bbox



    def smart_crop_pdf2(self, input_pdf, pages_config=None):
        """Умная обрезка PDF: пиксельный анализ только для А4, остальное — через нормализацию"""
        
        specification_dir = os.path.join(self.base_path, "Приложение. Спецификация/_latex/img")
        e3_dir = os.path.join(self.base_path, "Приложение. Схема Э3/_latex/img")
        e4_dir = os.path.join(self.base_path, "Приложение. Схема Э4.1/_latex/img")
        pn_dir = os.path.join(self.base_path, "Приложение. Перечень надписей/_latex/img")
        
        target_folders = [specification_dir, e3_dir, e4_dir]
        Logger.info("Очистка целевых папок...")
        for folder in target_folders:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith('.pdf'):
                        try: os.remove(os.path.join(folder, f))
                        except: pass
            else: os.makedirs(folder, exist_ok=True)
        
        doc = fitz.open(input_pdf)
        total_pages = len(doc)
        Logger.info(f"УМНАЯ ОБРЕЗКА PDF: {input_pdf} ({total_pages} стр.)")
        
        page_prefix_map = {}
        if pages_config:
            for prefix, page_nums in pages_config.items():
                for page_num in page_nums: page_prefix_map[page_num] = prefix

        for page_num in range(total_pages):
            page = doc[page_num]
            original_rotation = page.rotation
            media_box = page.mediabox
            
            width_mm = media_box.width * 0.352778
            height_mm = media_box.height * 0.352778
            
            # Сброс поворота для корректного анализа
            if original_rotation != 0: page.set_rotation(0)
            page.set_cropbox(media_box)
            
            # 1. Поиск границ через объекты
            content_bbox = self._find_content_bbox(page)
            final_bbox = None

            # Проверка на "полную страницу" (рамку/фон)
            is_full_page = False
            if content_bbox:
                is_full_page = (
                    abs(content_bbox.width - media_box.width) < 15 and 
                    abs(content_bbox.height - media_box.height) < 15
                )

            # ЛОГИКА ВЫБОРА МЕТОДА
            is_a4 = (abs(width_mm - 210) < 10 and abs(height_mm - 297) < 10) or \
                    (abs(width_mm - 297) < 10 and abs(height_mm - 210) < 10)
            
            # Для отладки можно временно включить is_a4 = True, чтобы проверить пиксели на всех листах
            is_a4 = True 

            if not is_full_page and is_a4:
                Logger.debug(f"⚠️ Стр. {page_num+1} (А4): Полный контент. Pixel Analysis...")
                
                # Pre-crop для удаления шума по краям
                pre_crop_val = 3
                pre_rect = fitz.Rect(
                    media_box.x0 + pre_crop_val, media_box.y0 + pre_crop_val,
                    media_box.x1 - pre_crop_val, media_box.y1 - pre_crop_val
                )
                page.set_cropbox(pre_rect)
                
                # Пиксельный анализ
                final_bbox = self._auto_crop_by_pixels(page, padding=5, dpi=150)
                
                # Возвращаем CropBox к исходному, так как final_bbox уже в абсолютных координатах
                page.set_cropbox(media_box)

            elif content_bbox:
                # === ИСПРАВЛЕНИЕ ЗДЕСЬ ===
                # Используем нормализацию вместо простого паддинга
                Logger.debug(f"Стр. {page_num+1}: Нормализация по объектам")
                final_bbox = self._normalize_page(page, content_bbox)
            
            if final_bbox:
                page.set_cropbox(final_bbox)
                page.set_trimbox(final_bbox)
                page.set_bleedbox(final_bbox)
                page.set_artbox(final_bbox)
            
            # Восстановление поворота
            if original_rotation != 0: page.set_rotation(original_rotation)
            
            # Сохранение
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            output_filename = f"СЭП_{page_num + 1}.pdf" 
            output_subfolder = e3_dir
            
            if pages_config and (page_num + 1) in page_prefix_map:
                prefix = page_prefix_map[page_num + 1]
                page_list = pages_config[prefix]
                index_in_list = page_list.index(page_num + 1) + 1
                
                if prefix == 'ПН': 
                    new_doc.close()
                    continue
                elif prefix == 'ПЭ': output_subfolder = specification_dir
                elif prefix == 'СЭП': output_subfolder = e3_dir
                elif prefix == 'СЭС': output_subfolder = e4_dir
                
                output_filename = f"{prefix}_{index_in_list}.pdf"

            output_path = os.path.join(output_subfolder, output_filename)
            new_doc.save(output_path)
            new_doc.close()
            Logger.info(f"Сохранено: {output_path}")

        doc.close()
        Logger.info("Обработка завершена!")







    def smart_crop_pdf(self, input_pdf, pages_config=None):
        """Умная обрезка PDF: пиксельный анализ только для А4, остальное — стандартно"""
        
        # ... (код инициализации папок и очистки остается без изменений) ...
        specification_dir = os.path.join(self.base_path, "Приложение. Спецификация/_latex/img")
        e3_dir = os.path.join(self.base_path, "Приложение. Схема Э3/_latex/img")
        e4_dir = os.path.join(self.base_path, "Приложение. Схема Э4.1/_latex/img")
        pn_dir = os.path.join(self.base_path, "Приложение. Перечень надписей/_latex/img")
        
        target_folders = [specification_dir, e3_dir, e4_dir]
        Logger.info("Очистка целевых папок...")
        for folder in target_folders:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith('.pdf'):
                        try: os.remove(os.path.join(folder, f))
                        except: pass
            else: os.makedirs(folder, exist_ok=True)
        
        doc = fitz.open(input_pdf)
        total_pages = len(doc)
        Logger.info(f"УМНАЯ ОБРЕЗКА PDF: {input_pdf} ({total_pages} стр.)")
        
        page_prefix_map = {}
        if pages_config:
            for prefix, page_nums in pages_config.items():
                for page_num in page_nums: page_prefix_map[page_num] = prefix

        for page_num in range(total_pages):
            page = doc[page_num]
            original_rotation = page.rotation
            media_box = page.mediabox
            
            # Определяем размер в мм для проверки формата
            width_mm = media_box.width * 0.352778
            height_mm = media_box.height * 0.352778
            
            # Сброс поворота для корректного анализа
            if original_rotation != 0: page.set_rotation(0)
            page.set_cropbox(media_box)
            
            # 1. Поиск границ через объекты
            content_bbox = self._find_content_bbox(page)

            #if content_bbox:
                # Применяем нормализацию
                #content_bbox = self._normalize_page(page, content_bbox)
                #page.set_cropbox(content_bbox)


            # Проверка на "полную страницу" (рамку/фон)
            is_full_page = False
            if content_bbox:
                is_full_page = (
                    abs(content_bbox.width - media_box.width) < 15 and 
                    abs(content_bbox.height - media_box.height) < 15
                )

            final_bbox = None

            # ЛОГИКА ВЫБОРА МЕТОДА: Только для А4 используем пиксели
            is_a4 = (abs(width_mm - 210) < 10 and abs(height_mm - 297) < 10) or \
                    (abs(width_mm - 297) < 10 and abs(height_mm - 210) < 10)


            Logger.debug(f"⚠️ Стр. {page_num+1} (А4): Полный контент. Pre-crop + Pixel Analysis...")
            
            # Шаг А: Pre-crop (срезаем 1pt шума)
            pre_crop_val = 3
            pre_rect = fitz.Rect(
                media_box.x0 + pre_crop_val, media_box.y0 + pre_crop_val,
                media_box.x1 - pre_crop_val, media_box.y1 - pre_crop_val
            )
            page.set_cropbox(pre_rect)
            
            # Шаг Б: Пиксельный анализ
            final_bbox = self._auto_crop_by_pixels(page, padding=5, dpi=150)

            final_bbox = self._normalize_page(page, final_bbox)

            # Возвращаем CropBox к исходному для корректных координат
            page.set_cropbox(media_box)



            if final_bbox:
                page.set_cropbox(final_bbox)
                page.set_trimbox(final_bbox)
                page.set_bleedbox(final_bbox)
                page.set_artbox(final_bbox)
            
            # Восстановление поворота
            if original_rotation != 0: page.set_rotation(original_rotation)
            
            # ... (ваша логика сохранения страниц с префиксами СЭП, ПЭ и т.д.) ...
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            output_filename = f"СЭП_{page_num + 1}.pdf" 
            output_subfolder = e3_dir
            
            if pages_config and (page_num + 1) in page_prefix_map:
                prefix = page_prefix_map[page_num + 1]
                page_list = pages_config[prefix]
                index_in_list = page_list.index(page_num + 1) + 1
                
                if prefix == 'ПН': new_doc.close(); continue
                elif prefix == 'ПЭ': output_subfolder = specification_dir
                elif prefix == 'СЭП': output_subfolder = e3_dir
                elif prefix == 'СЭС': output_subfolder = e4_dir
                
                output_filename = f"{prefix}_{index_in_list}.pdf"

            output_path = os.path.join(output_subfolder, output_filename)
            new_doc.save(output_path)
            new_doc.close()
            Logger.info(f"Сохранено: {output_path}")

        doc.close()
        Logger.info("Обработка завершена!")