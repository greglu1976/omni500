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
            'A4_portrait': (4, 4, 5, 19),    # верх, право, низ, лево
            'A4_landscape': (0, 0, 0, 0),
            'A3_portrait': (5, 5, 5, 5),
            'A3_landscape': (5, 5, 5, 20),   # верх, право, низ, лево
            'A2_portrait': (6, 6, 21, 6),
            'A2_landscape': (6, 21, 6, 6),
            'default': (6, 6, 6, 6),
        }
        self.mm_to_points = 2.83465

        # --- НОВОЕ ---
        # Включение/выключение обрезки по границам контента для каждого формата
        # True  = обрезать по автоматически найденным границам контента + запас
        # False = использовать фиксированные отступы из margins_config (старое поведение)
        self.crop_by_content_config = {
            'A4_portrait':  False,
            'A4_landscape': True,      # ← включено для А4 горизонтальный
            'A3_portrait':  False,
            'A3_landscape': True,      # ← включено для А3 горизонтальный
            'A2_portrait':  False,
            'A2_landscape': False,
            'unknown':      False,
            'default':      False,
        }

        # Запас (мм) при обрезке по границам контента: верх, право, низ, лево
        self.content_crop_padding = {
            'A4_portrait':  (3, 3, 3, 3),
            'A4_landscape': (3, 3, 3, 3),
            'A3_portrait':  (3, 3, 3, 3),
            'A3_landscape': (3, 3, 3, 3),
            'A2_portrait':  (3, 3, 3, 3),
            'A2_landscape': (3, 3, 3, 3),
            'unknown':      (3, 3, 3, 3),
            'default':      (3, 3, 3, 3),
        }

        # Параметры детекции границ контента
        # size_ratio:    элементы, чей размер > доля_от_страницы, считаются рамкой формата
        # edge_margin:   элементы ближе этого расстояния (points) к краю страницы — кандидат на рамку
        #                (применяется ТОЛЬКО вместе с size_ratio, не фильтрует мелкий контент у краёв)
        self.content_detect_size_ratio = 0.92
        self.content_detect_edge_margin = 10.0
        # --- КОНЕЦ НОВОГО ---

    # --- НОВОЕ ---
    def detect_content_bounds(self, page):
        """
        Определяет ограничивающий прямоугольник фактического контента на странице PDF.
        Автоматически фильтрует рамку формата (длинные линии у краёв страницы).

        Args:
            page: fitz.Page (страница ДО применения обрезки, в системе координат MediaBox)

        Returns:
            fitz.Rect — границы контента, или None если контент не обнаружен
        """
        page_rect = page.rect
        if not page_rect.is_valid:
            return None

        size_ratio = self.content_detect_size_ratio
        edge_margin = self.content_detect_edge_margin

        filtered_rects = []

        def is_frame_element(rect):
            """Считаем элемент рамкой формата, если он ОЧЕНЬ большой И касается края страницы."""
            if not rect.is_valid or rect.width < 1 or rect.height < 1:
                return True  # пропускаем вырожденные

            large_x = rect.width > page_rect.width * size_ratio
            large_y = rect.height > page_rect.height * size_ratio

            if not (large_x or large_y):
                return False  # мелкий/средний — точно не рамка

            near_edge = (rect.x0 <= page_rect.x0 + edge_margin or
                         rect.y0 <= page_rect.y0 + edge_margin or
                         rect.x1 >= page_rect.x1 - edge_margin or
                         rect.y1 >= page_rect.y1 - edge_margin)
            return near_edge

        # 1) Векторные примитивы (линии, полилинии, дуги из AutoCAD)
        try:
            for path in page.get_drawings():
                r = path.get("rect")
                if r:
                    rect = fitz.Rect(r)
                    if not is_frame_element(rect):
                        filtered_rects.append(rect)
        except Exception as e:
            Logger.warning(f"Ошибка получения векторов: {e}")

        # 2) Текстовые блоки
        try:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") == 0:
                    r = fitz.Rect(block["bbox"])
                    if r.is_valid and r.width > 1 and r.height > 1:
                        if not is_frame_element(r):
                            filtered_rects.append(r)
        except Exception as e:
            Logger.warning(f"Ошибка получения текста: {e}")

        # 3) Растровые изображения
        try:
            for img_info in page.get_image_info():
                r = fitz.Rect(img_info["bbox"])
                if r.is_valid and r.width > 1 and r.height > 1:
                    if not is_frame_element(r):
                        filtered_rects.append(r)
        except Exception as e:
            Logger.warning(f"Ошибка получения изображений: {e}")

        if not filtered_rects:
            return None

        # Объединяем все прямоугольники
        result = fitz.Rect(filtered_rects[0])
        for r in filtered_rects[1:]:
            result |= r

        # Защита от мусорной детекции
        if result.get_area() < 100:
            return None

        return result
    # --- КОНЕЦ НОВОГО ---

    def convert_dwg_to_dxf_com(self, dwg_path, dxf_path):
        """Конвертация DWG в DXF через COM-автоматизацию"""
        
        Logger.info("Запуск конвертации DWG → DXF (через COM)...")
        Logger.info(f"Входной файл: {dwg_path}")
        Logger.info(f"Выходной файл: {dxf_path}")
        
        if not os.path.exists(dwg_path):
            Logger.error(f"\n❌ Ошибка: Входной файл не найден: {dwg_path}")
            return False
        
        try:
            acad = win32com.client.Dispatch(ACAD)
            acad.Visible = False
            
            doc = acad.Documents.Open(dwg_path)
            doc.SaveAs(dxf_path, 61) 
            doc.Close(False)
            acad.Quit()
            del acad
            
            if os.path.exists(dxf_path):
                size = os.path.getsize(dxf_path)
                Logger.info("DXF успешно создан!")
                return True
            else:
                Logger.error("Ошибка: DXF файл не создан")
                return False
                
        except Exception as e:
            Logger.error(f"Ошибка при конвертации: {e}")
            return False

    def create_dsd_from_dxf(self, dxf_path, dsd_path, output_pdf_path, pdf_printer="DWG To PDF.pc3"):
        try:
            acad = win32com.client.Dispatch(ACAD)
            doc = acad.Documents.Open(dxf_path)
            
            layouts_with_order = []
            for layout in doc.Layouts:
                if layout.Name != "Model":
                    layouts_with_order.append((layout.TabOrder, layout.Name))
                    
            doc.Close(False)
            
            layouts_with_order.sort(key=lambda x: x[0])
            layouts = [name for _, name in layouts_with_order]
            
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
                
            Logger.info(f"DSD-файл успешно создан: {dsd_path}")
            Logger.info(f"Найдено листов: {len(layouts)}")
            Logger.info(f"Порядок вкладок: {layouts}")
            return True

        except Exception as e:
            Logger.error(f"Ошибка при создании DSD: {e}")
            return False

    def clean_dxf(self, dxf_file):

        target_blocks = [
            "Штамп большой нижний", 
            "Штамп большой нижний текстовый", 
            "Штамп левый верхний", 
            "Штамп левый нижний", 
            "Штамп малый нижний", 
            "Штамп угловой верхний"
        ]

        target_blocks_special = ["Формат_А4", "Формат_А3"]

        target_areas = [124740, 111520]
        area_tolerance = 10.0

        doc = ezdxf.readfile(dxf_file)
        msp = doc.modelspace()

        def get_polyline_area(entity):
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

        entities_to_remove = set()
        all_entities = list(msp)

        Logger.info("ЭТАП 1: Работа со штампами")

        blocks_to_delete = []
        stamp_bboxes = []

        for entity in all_entities:
            if entity.dxftype() == 'INSERT' and entity.dxf.name in target_blocks:
                blocks_to_delete.append(entity)
                bbox = get_block_bbox(entity)
                if bbox:
                    stamp_bboxes.append(bbox)
                    Logger.info(f"  Найден штамп: {entity.dxf.name}")

        for b in blocks_to_delete:
            entities_to_remove.add(b)

        for entity in all_entities:
            if entity in entities_to_remove: continue
            if object_inside_stamp(entity, stamp_bboxes):
                entities_to_remove.add(entity)

        Logger.info("ЭТАП 1.5: Удаление форматок (только блоки)")

        special_blocks_count = 0
        for entity in all_entities:
            if entity in entities_to_remove: continue
            
            if entity.dxftype() == 'INSERT' and entity.dxf.name in target_blocks_special:
                entities_to_remove.add(entity)
                special_blocks_count += 1

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
                            break

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
                except Exception as e:
                    Logger.error(f"  Ошибка при проверке MTEXT: {e}")

        Logger.info(f"  Найдено MTEXT для удаления: {mtext_deleted_count}")

        Logger.info(f"Итого будет удалено объектов: {len(entities_to_remove)}")

        deleted_count = 0
        for ent in entities_to_remove:
            try:
                msp.delete_entity(ent)
                deleted_count += 1
            except Exception as e:
                Logger.error(f"  Ошибка при удалении {ent.dxftype()}: {e}")

        Logger.info(f"Фактически удалено: {deleted_count} объектов")

        try:
            doc.saveas("cleaned_dxf.dxf")
            Logger.info("Файл сохранен как 'cleaned_dxf.dxf'")
        except Exception as e:
            Logger.error(f"Ошибка при сохранении: {e}")

    def print_dxf_to_pdf(self, dxf_name, acadconsole_path, dsd_path, scr_path):

        Logger.info("Запуск публикации...")
        
        script_content = textwrap.dedent(f"""\
            _.-PUBLISH
            {dsd_path}
            Y
            _.QUIT
        """)

        with open(scr_path, 'w', encoding='cp1251') as f:
            f.write(script_content)
        
        Logger.info(f"Создан SCR: {scr_path}")
        Logger.info(f"Используется DSD: {dsd_path}")

        result = subprocess.run(
            [acadconsole_path, "/i", str(dxf_name), "/s", str(scr_path)],
            capture_output=True,
            text=True,
            encoding='cp866'
        )

        if "Нет ошибок или предупреждений" in result.stdout or "no errors or warnings" in result.stdout.lower():
            Logger.info("PDF успешно создан!")
        else:
            pass

    def create_pages_json_from_pdf(self, input_pdf, output_json='pages.json'):
        if not os.path.exists(input_pdf):
            Logger.error(f"Файл не найден: {input_pdf}")
            return

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
            temp_groups = {} 

            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                
                found_phrase = None
                for phrase in search_phrases:
                    if phrase in text:
                        found_phrase = phrase
                        break
                
                if found_phrase:
                    new_group = markers[found_phrase]
                    Logger.info(f"Стр. {page_num + 1}: Найден маркер '{found_phrase}' -> Группа {new_group}")
                    
                    if current_group != new_group:
                        current_group = new_group
                        if current_group not in temp_groups:
                            temp_groups[current_group] = []
                
                if current_group:
                    temp_groups[current_group].append(page_num + 1)
                else:
                    Logger.info(f"  Стр. {page_num + 1}: Пропуск (группа еще не определена)")

            doc.close()

            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(temp_groups, f, ensure_ascii=False, indent=4)
                
            Logger.info(f"Файл {output_json} успешно создан!")
            Logger.info(f"Структура страниц: {json.dumps(temp_groups, ensure_ascii=False)}")

        except Exception as e:
            Logger.error(f"Ошибка при обработке PDF: {e}")
            import traceback
            traceback.print_exc()

    def detect_format(self, width_mm, height_mm, rotation):
        tolerance = 10
        
        if rotation in [90, 270]:
            physical_width = height_mm
            physical_height = width_mm
        else:
            physical_width = width_mm
            physical_height = height_mm
        
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
            if abs(width_mm - 420) < tolerance and abs(height_mm - 297) < tolerance:
                return 'A3_landscape'
            elif abs(width_mm - 297) < tolerance and abs(height_mm - 420) < tolerance:
                return 'A3_portrait'
            else:
                return 'unknown'

    def load_pages_config(self, config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            Logger.info(f"Загружена конфигурация из {config_file}")
            return config
        except FileNotFoundError:
            # --- ИЗМЕНЕНО: исправлен опечаток warningf -> warning ---
            Logger.warning(f"Файл конфигурации {config_file} не найден. Используется стандартное сохранение.")
            return None
        except json.JSONDecodeError as e:
            Logger.error(f"Ошибка чтения JSON файла {config_file}: {e}")
            Logger.info("Используется стандартное сохранение.")
            return None

    # --- ИЗМЕНЕНО: полностью переписана логика обрезки с добавлением детекции контента ---
    def smart_crop_pdf(self, input_pdf, pages_config=None):
        """
        Умная обрезка PDF с автоматическим определением формата и ориентации.
        
        Для каждого формата можно выбрать режим обрезки:
          - По границам контента (crop_by_content_config[формат] = True):
            автоматически находятся границы рисунка/текста, обрезка с заданным запасом.
          - По фиксированным отступам (crop_by_content_config[формат] = False):
            старое поведение — отступы из margins_config.
        
        Args:
            input_pdf: путь к входному PDF файлу
            pages_config: словарь конфигурации страниц (если None, используется стандартное сохранение)
        """
        
        specification_dir = os.path.join(self.base_path, "Приложение. Спецификация/_latex/img")
        e3_dir = os.path.join(self.base_path, "Приложение. Схема Э3/_latex/img")
        e4_dir = os.path.join(self.base_path, "Приложение. Схема Э4.1/_latex/img")
        pn_dir = os.path.join(self.base_path, "Приложение. Перечень надписей/_latex/img")

        doc = fitz.open(input_pdf)
        total_pages = len(doc)
        
        Logger.info(f"УМНАЯ ОБРЕЗКА PDF: {input_pdf}")
        
        page_prefix_map = {}
        if pages_config:
            for prefix, page_nums in pages_config.items():
                for page_num in page_nums:
                    page_prefix_map[page_num] = prefix
            
            Logger.info(f"Конфигурация страниц:")
            for prefix, page_nums in pages_config.items():
                Logger.info(f"  {prefix}: страницы {page_nums}")

            folders_to_create = [specification_dir, e3_dir, e4_dir]
            for folder_path in folders_to_create:
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)

        for page_num in range(total_pages):
            page = doc[page_num]
            
            original_rotation = page.rotation
            original_rect = page.rect
            original_width_mm = original_rect.width * 0.352778
            original_height_mm = original_rect.height * 0.352778

            Logger.info(f"\n--- Страница {page_num + 1}/{total_pages} ---")
            Logger.info(f"  Размер: {original_width_mm:.1f} x {original_height_mm:.1f} мм, поворот: {original_rotation}°")

            # Определяем формат листа
            format_key = self.detect_format(original_width_mm, original_height_mm, original_rotation)
            Logger.info(f"  Формат: {format_key}")

            # --- НОВОЕ: определяем режим обрезки ---
            use_content_crop = self.crop_by_content_config.get(
                format_key, self.crop_by_content_config.get('default', False)
            )

            # Сбрасываем поворот для работы в единой системе координат MediaBox
            if original_rotation != 0:
                page.set_rotation(0)

            current_rect = page.rect
            crop_rect = None

            # ===== РЕЖИМ 1: ОБРЕЗКА ПО ГРАНИЦАМ КОНТЕНТА =====
            if use_content_crop:
                Logger.info(f"  Режим обрезки: ПО ГРАНИЦАМ КОНТЕНТА")
                content_rect = self.detect_content_bounds(page)

                if content_rect and content_rect.is_valid:
                    padding_mm = self.content_crop_padding.get(
                        format_key, self.content_crop_padding.get('default', (3, 3, 3, 3))
                    )
                    top_pad, right_pad, bottom_pad, left_pad = [
                        p * self.mm_to_points for p in padding_mm
                    ]

                    crop_rect = fitz.Rect(
                        content_rect.x0 - left_pad,
                        content_rect.y0 - top_pad,
                        content_rect.x1 + right_pad,
                        content_rect.y1 + bottom_pad
                    )
                    # Ограничиваем рамками страницы
                    crop_rect = crop_rect.intersect(current_rect)

                    Logger.info(f"  Границы контента (pt): ({content_rect.x0:.1f}, {content_rect.y0:.1f}) — ({content_rect.x1:.1f}, {content_rect.y1:.1f})")
                    Logger.info(f"  Размер контента (мм): {content_rect.width * 0.352778:.1f} x {content_rect.height * 0.352778:.1f}")
                    Logger.info(f"  Запас (мм): верх={padding_mm[0]}, право={padding_mm[1]}, низ={padding_mm[2]}, лево={padding_mm[3]}")
                    Logger.info(f"  Crop rect (pt): ({crop_rect.x0:.1f}, {crop_rect.y0:.1f}) — ({crop_rect.x1:.1f}, {crop_rect.y1:.1f})")
                    Logger.info(f"  Crop размер (мм): {crop_rect.width * 0.352778:.1f} x {crop_rect.height * 0.352778:.1f}")
                else:
                    Logger.warning(f"  ⚠ Контент не обнаружен! Переход к фиксированным отступам.")
                    use_content_crop = False

            # ===== РЕЖИМ 2: ФИКСИРОВАННЫЕ ОТСТУПЫ =====
            if not use_content_crop:
                Logger.info(f"  Режим обрезки: ФИКСИРОВАННЫЕ ОТСТУПЫ")

                if format_key in self.margins_config:
                    top_mm, right_mm, bottom_mm, left_mm = self.margins_config[format_key]
                else:
                    top_mm, right_mm, bottom_mm, left_mm = self.margins_config.get('default', (6, 6, 6, 6))

                top = top_mm * self.mm_to_points
                right = right_mm * self.mm_to_points
                bottom = bottom_mm * self.mm_to_points
                left = left_mm * self.mm_to_points

                Logger.info(f"  Отступы (мм): верх={top_mm}, право={right_mm}, низ={bottom_mm}, лево={left_mm}")

                if original_rotation == 90:
                    crop_rect = fitz.Rect(
                        current_rect.x0 + top,
                        current_rect.y0 + right,
                        current_rect.x1 - bottom,
                        current_rect.y1 - left
                    )
                elif original_rotation == 270:
                    crop_rect = fitz.Rect(
                        current_rect.x0 + bottom,
                        current_rect.y0 + left,
                        current_rect.x1 - top,
                        current_rect.y1 - right
                    )
                else:
                    crop_rect = fitz.Rect(
                        current_rect.x0 + left,
                        current_rect.y0 + top,
                        current_rect.x1 - right,
                        current_rect.y1 - bottom
                    )

                crop_rect = crop_rect.intersect(current_rect)

            # Применяем обрезку
            if (crop_rect and crop_rect.is_valid and
                (crop_rect.x0 > current_rect.x0 or crop_rect.y0 > current_rect.y0 or
                 crop_rect.x1 < current_rect.x1 or crop_rect.y1 < current_rect.y1)):
                page.set_cropbox(crop_rect)
                Logger.info(f"  ✅ Обрезка применена")
            else:
                Logger.info(f"  ✅ Обрезка не требуется (отступы = 0 или пустой crop)")

            # Возвращаем оригинальный поворот
            if original_rotation != 0:
                page.set_rotation(original_rotation)

            # Сохраняем страницу в отдельный файл
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            if pages_config and (page_num + 1) in page_prefix_map:
                prefix = page_prefix_map[page_num + 1]
                page_list = pages_config[prefix]
                index_in_list = page_list.index(page_num + 1) + 1
                
                if prefix == 'ПН':
                    output_subfolder = pn_dir
                    output_filename = f"{prefix}_{index_in_list}.pdf"
                    Logger.info(f"  Префикс: {prefix} (Перечень надписей)")
                    Logger.info(f"  СОХРАНЕНИЕ ПРОПУЩЕНО (ПН - зарезервировано)")
                    new_doc.close()
                    continue
                        
                elif prefix == 'ПЭ':
                    output_subfolder = specification_dir
                    output_filename = f"{prefix}_{index_in_list}.pdf"
                    Logger.info(f"  Префикс: {prefix} → Спецификация")
                    
                elif prefix == 'СЭП':
                    output_subfolder = e3_dir
                    output_filename = f"{prefix}_{index_in_list}.pdf"
                    Logger.info(f"  Префикс: {prefix} → Схема Э3")
                    
                elif prefix == 'СЭС':
                    output_subfolder = e4_dir
                    output_filename = f"{prefix}_{index_in_list}.pdf"
                    Logger.info(f"  Префикс: {prefix} → Схема Э4.1")
                    
                else:
                    output_subfolder = self.base_path
                    output_filename = f"{prefix}_{index_in_list}.pdf"
                    Logger.info(f"  Префикс: {prefix} (стандартное сохранение)")
                
                output_path = os.path.join(output_subfolder, output_filename)
                
            else:
                output_filename = f"{page_num + 1}.pdf"
                output_subfolder = self.base_path
                output_path = os.path.join(output_subfolder, output_filename)
            
            new_doc.save(output_path)
            new_doc.close()
            Logger.info(f"  💾 Сохранено: {output_path}")
        
        doc.close()
        Logger.info(f"\nГотово! Обработано {total_pages} страниц")

    def del_files(self, files_list):
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
        
        remaining = [f for f in files_list if os.path.exists(f)]
        if remaining:
            Logger.warning(f"Остались файлы: {', '.join([os.path.basename(f) for f in remaining])}")
            Logger.info("Возможно, файлы используются другими программами (закройте AutoCAD)")
        else:
            Logger.info("Все файлы успешно удалены!")

    def run(self, device_data):

        self.base_path = device_data["path_to_latex_desc"]
        doc_dir = os.path.join(self.base_path, "Документация")

        pdf_files = [f for f in os.listdir(doc_dir) if f.lower().endswith('.dwg')]
        
        if len(pdf_files) > 1:
            Logger.error("Предупреждение: найдено больше одного DWG файла")
            return None
            
        if len(pdf_files) == 0:
            Logger.error("Предупреждение:DWG файлы не найдены")
            return None

        path = os.path.join(doc_dir, pdf_files[0])

        Logger.info(f"Найден путь к исходному dwg {path}")

        dwg_file = path
        current_dir = Path.cwd()
        dxf_file = current_dir / "temp.dxf"
        dsd_file = current_dir / "temp.dsd"
        pdf_file = current_dir / "temp.pdf"
        pdf_file2 = current_dir / "temp2.pdf"
        scr_path = current_dir / "publish.scr"
        acadconsole_path = ACONSOLE
        dxf_file_clean = current_dir / "cleaned_dxf.dxf"

        Logger.info("========================== ШАГ 1 ========================")
        self.convert_dwg_to_dxf_com(dwg_file, dxf_file)  
        Logger.info("Ожидание освобождения AutoCAD...")
        time.sleep(3)

        Logger.info("========================== ШАГ 2 ========================")
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
        self.create_pages_json_from_pdf(pdf_file)
        time.sleep(3)

        Logger.info("========================== ШАГ 6 - СОЗДАЕМ DSD ДЛЯ ПЕЧАТИ  ========================")
        self.create_dsd_from_dxf(dxf_file_clean, dsd_file, pdf_file2)

        Logger.info("========================== ШАГ 7 - ПЕЧАТЬ ЧИСТОГО PDF  ========================")
        self.print_dxf_to_pdf(dxf_file_clean, acadconsole_path, dsd_file, scr_path)
        time.sleep(3)

        Logger.info("========================== ШАГ 8 - НАРЕЗКА PDF  ========================")
        pages_config = self.load_pages_config('pages.json')
        Logger.info("Входной файл: temp2.pdf")
        self.smart_crop_pdf('temp2.pdf', pages_config)

        Logger.info("========================== ШАГ 9 - УДАЛЯЕМ ВРЕМЕННЫЕ ФАЙЛЫ  ========================")
        files_to_delete = [
            dxf_file,
            dsd_file,
            scr_path,
            dxf_file_clean,
            pdf_file,
            pdf_file2,
            current_dir / "pages.json",
            current_dir / "plot.log"
        ]
        self.del_files(files_to_delete)

        Logger.info("========================== ПРИЛОЖЕНИЯ ОБНОВЛЕНЫ  ========================")