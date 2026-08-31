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


class CabDwgProcessor:
    def __init__(self):
        # Конфигурация отступов как атрибут класса
        self.margins_config = {
            'A4_portrait': (5, 5, 5, 20),    # верх, право, низ, лево
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
        
        print("Запуск конвертации DWG → DXF (через COM)...")
        print(f"Входной файл: {dwg_path}")
        print(f"Выходной файл: {dxf_path}")
        
        if not os.path.exists(dwg_path):
            print(f"\n❌ Ошибка: Входной файл не найден: {dwg_path}")
            return False
        
        try:
            # Создаём экземпляр AutoCAD
            acad = win32com.client.Dispatch("AutoCAD.Application")
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
                print(f"\n✅ DXF успешно создан!")
                print(f"📁 Путь: {dxf_path}")
                print(f"📏 Размер: {size} байт ({size/1024:.2f} KB)")
                return True
            else:
                print(f"\n❌ Ошибка: DXF файл не создан")
                return False
                
        except Exception as e:
            print(f"\n❌ Ошибка при конвертации: {e}")
            return False

    def create_dsd_from_dxf(self, dxf_path, dsd_path, output_pdf_path, pdf_printer="DWG To PDF.pc3"):
        """
        Создает DSD-файл на основе листов указанного DXF-чертежа.
        Листы записываются в порядке вкладок AutoCAD (TabOrder).
        """
        try:
            # 1. Подключаемся к AutoCAD для получения списка листов
            acad = win32com.client.Dispatch("AutoCAD.Application")
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
                
            print(f"DSD-файл успешно создан: {dsd_path}")
            print(f"Найдено листов: {len(layouts)}")
            print(f"Порядок вкладок: {layouts}")
            return True

        except Exception as e:
            print(f"Ошибка при создании DSD: {e}")
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
        print("="*30)
        print("ЭТАП 1: Работа со штампами")
        print("="*30)

        blocks_to_delete = []
        stamp_bboxes = []

        for entity in all_entities:
            if entity.dxftype() == 'INSERT' and entity.dxf.name in target_blocks:
                blocks_to_delete.append(entity)
                bbox = get_block_bbox(entity)
                if bbox:
                    stamp_bboxes.append(bbox)
                    print(f"  Найден штамп: {entity.dxf.name}")

        print(f"  Найдено штампов: {len(blocks_to_delete)}")

        # Добавляем сами штампы в список на удаление
        for b in blocks_to_delete:
            entities_to_remove.add(b)

        # Ищем объекты внутри штампов
        for entity in all_entities:
            if entity in entities_to_remove: continue
            if object_inside_stamp(entity, stamp_bboxes):
                entities_to_remove.add(entity)

        print(f"  Всего объектов к удалению после Этапа 1: {len(entities_to_remove)}")

        # ==========================================
        # ЭТАП 1.5: Удаление специальных блоков (форматок) БЕЗ содержимого
        # ==========================================
        print("\n" + "="*30)
        print("ЭТАП 1.5: Удаление форматок (только блоки)")
        print("="*30)

        special_blocks_count = 0
        for entity in all_entities:
            if entity in entities_to_remove: continue
            
            if entity.dxftype() == 'INSERT' and entity.dxf.name in target_blocks_special:
                entities_to_remove.add(entity)
                special_blocks_count += 1
                print(f"  Помечен на удаление блок: {entity.dxf.name} (содержимое останется)")

        print(f"  Найдено форматок для удаления: {special_blocks_count}")

        # ==========================================
        # ЭТАП 2: Удаление полилиний по площади
        # ==========================================
        print("\n" + "="*30)
        print("ЭТАП 2: Удаление рамок по площади")
        print("="*30)

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
                            print(f"  Найдена рамка по площади: {area:.1f} (цель: {target_area})")
                            break

        print(f"  Найдено дополнительных рамок по площади: {area_deleted_count}")

        # ==========================================
        # ЭТАП 2.5: Удаление MTEXT с конкретной строкой
        # ==========================================
        print("\n" + "="*30)
        print("ЭТАП 2.5: Удаление MTEXT по тексту")
        print("="*30)

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
                        print(f"  Найден MTEXT с целевой строкой (ID: {entity.dxf.handle})")
                except Exception as e:
                    print(f"  Ошибка при проверке MTEXT: {e}")

        print(f"  Найдено MTEXT для удаления: {mtext_deleted_count}")

        # ==========================================
        # ВЫПОЛНЕНИЕ УДАЛЕНИЯ
        # ==========================================
        print(f"\n✅ Итого будет удалено объектов: {len(entities_to_remove)}")

        deleted_count = 0
        for ent in entities_to_remove:
            try:
                msp.delete_entity(ent)
                deleted_count += 1
            except Exception as e:
                print(f"  Ошибка при удалении {ent.dxftype()}: {e}")

        print(f"✅ Фактически удалено: {deleted_count} объектов")

        try:
            doc.saveas("cleaned_dxf.dxf")
            print("💾 Файл сохранен как 'cleaned_dxf.dxf'")
        except Exception as e:
            print(f"❌ Ошибка при сохранении: {e}")

    def print_dxf_to_pdf(self, dxf_name, acadconsole_path, dsd_path, scr_path):

        """
        Создает SCR файл с динамическим путем к DSD
        """
        print("Запуск публикации...")
        
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
        
        print(f"📄 Создан SCR: {scr_path}")
        print(f"📄 Используется DSD: {dsd_path}")


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
            print("\n✅ PDF успешно создан!")
        else:
            pass
            #print("\n⚠️ Возможны ошибки. Проверьте лог выше.")

    def create_pages_json_from_pdf(self, input_pdf, output_json='pages.json'):
        """
        Анализирует PDF, ищет маркеры группировки и создает pages.json
        """
        if not os.path.exists(input_pdf):
            print(f"❌ Файл не найден: {input_pdf}")
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
            
            print(f"🔍 Анализ PDF: {input_pdf} ({total_pages} страниц)")

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
                    print(f"  Стр. {page_num + 1}: Найден маркер '{found_phrase}' -> Группа {new_group}")
                    
                    # Если группа сменилась или это первая страница группы
                    if current_group != new_group:
                        current_group = new_group
                        if current_group not in temp_groups:
                            temp_groups[current_group] = []
                
                # Если у нас есть активная группа, добавляем номер страницы
                if current_group:
                    temp_groups[current_group].append(page_num + 1)
                else:
                    print(f"  Стр. {page_num + 1}: Пропуск (группа еще не определена)")

            doc.close()

            # Сохраняем результат в JSON
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(temp_groups, f, ensure_ascii=False, indent=4)
                
            print(f"\n💾 Файл {output_json} успешно создан!")
            print(json.dumps(temp_groups, ensure_ascii=False, indent=4))

        except Exception as e:
            print(f"❌ Ошибка при обработке PDF: {e}")
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
            print(f"✅ Загружена конфигурация из {config_file}")
            return config
        except FileNotFoundError:
            print(f"⚠️  Файл конфигурации {config_file} не найден. Используется стандартное сохранение.")
            return None
        except json.JSONDecodeError as e:
            print(f"⚠️  Ошибка чтения JSON файла {config_file}: {e}")
            print("Используется стандартное сохранение.")
            return None

    def smart_crop_pdf(self, input_pdf, output_folder, pages_config=None):
        """
        Умная обрезка PDF с автоматическим определением формата и ориентации
        
        Args:
            input_pdf: путь к входному PDF файлу
            output_folder: папка для сохранения результатов
            margins_by_format: словарь отступов по форматам
            pages_config: словарь конфигурации страниц (если None, используется стандартное сохранение)
        """

        if os.path.exists(output_folder):
            shutil.rmtree(output_folder)
        os.makedirs(output_folder, exist_ok=True)
        
        doc = fitz.open(input_pdf)
        total_pages = len(doc)
        
       
        print(f"\n{'='*80}")
        print(f"УМНАЯ ОБРЕЗКА PDF: {input_pdf}")
        print(f"{'='*80}\n")
        
        # Если передана конфигурация страниц, создаем обратный маппинг page_num -> prefix
        page_prefix_map = {}
        if pages_config:
            for prefix, page_nums in pages_config.items():
                for page_num in page_nums:
                    page_prefix_map[page_num] = prefix
            
            print(f"Конфигурация страниц:")
            for prefix, page_nums in pages_config.items():
                print(f"  {prefix}: страницы {page_nums}")
            print()
        
        for page_num in range(total_pages):
            page = doc[page_num]
            
            original_rotation = page.rotation
            original_rect = page.rect
            original_width_mm = original_rect.width * 0.352778
            original_height_mm = original_rect.height * 0.352778
            
            print(f"\n{'─'*80}")
            print(f"Страница {page_num + 1}:")
            print(f"  ИСХОДНЫЙ размер: {original_width_mm:.1f} x {original_height_mm:.1f} мм")
            print(f"  ИСХОДНЫЙ поворот: {original_rotation}°")
            print(f"  ИСХОДНЫЙ rect: {original_rect}")
            
            # Определяем формат на основе ИСХОДНЫХ параметров
            format_key = self.detect_format(original_width_mm, original_height_mm, original_rotation)
            print(f"  Формат: {format_key}")
            
            # Получаем отступы
            if format_key in self.margins_config:
                top_mm, right_mm, bottom_mm, left_mm = self.margins_config[format_key]
            else:
                top_mm, right_mm, bottom_mm, left_mm = self.margins_config.get('default', (6, 6, 6, 6))
            
            print(f"  Отступы (мм): верх={top_mm}, право={right_mm}, низ={bottom_mm}, лево={left_mm}")
            
            # Конвертируем в points
            top = top_mm * self.mm_to_points
            right = right_mm * self.mm_to_points
            bottom = bottom_mm * self.mm_to_points
            left = left_mm * self.mm_to_points
            
            print(f"  Отступы (points): верх={top:.1f}, право={right:.1f}, низ={bottom:.1f}, лево={left:.1f}")
            
            # Если страница повернута, сначала сбрасываем поворот
            if original_rotation != 0:
                print(f"\n  → Сбрасываем поворот с {original_rotation}° на 0°...")
                page.set_rotation(0)
                current_rect = page.rect
                print(f"  Rect после сброса поворота: {current_rect}")
                print(f"  Размер после сброса: {current_rect.width * 0.352778:.1f} x {current_rect.height * 0.352778:.1f} мм")
            
            # Теперь применяем отступы к текущему rect (уже без поворота)
            current_rect = page.rect
            
            # Для страниц с поворотом применяем отступы по-другому
            if original_rotation == 90:
                # При повороте 90°: меняем местами отступы
                crop_rect = fitz.Rect(
                    current_rect.x0 + top,      # лево = бывший верх
                    current_rect.y0 + right,    # верх = бывшее право
                    current_rect.x1 - bottom,   # право = бывший низ
                    current_rect.y1 - left      # низ = бывшее лево
                )
            elif original_rotation == 270:
                # При повороте 270°: меняем местами отступы
                crop_rect = fitz.Rect(
                    current_rect.x0 + bottom,   # лево = бывший низ
                    current_rect.y0 + left,     # верх = бывшее лево
                    current_rect.x1 - top,      # право = бывший верх
                    current_rect.y1 - right     # низ = бывшее право
                )
            else:
                # Для страниц без поворота
                crop_rect = fitz.Rect(
                    current_rect.x0 + left,
                    current_rect.y0 + top,
                    current_rect.x1 - right,
                    current_rect.y1 - bottom
                )
            
            print(f"\n  Crop rect (после сброса поворота): ({crop_rect.x0:.1f}, {crop_rect.y0:.1f}, {crop_rect.x1:.1f}, {crop_rect.y1:.1f})")
            print(f"  Crop размер: {crop_rect.width:.1f} x {crop_rect.height:.1f} points")
            print(f"  Crop размер (мм): {crop_rect.width * 0.352778:.1f} x {crop_rect.height * 0.352778:.1f} мм")
            
            # Проверяем, что crop_rect не выходит за пределы current_rect
            if (crop_rect.x0 < current_rect.x0 or crop_rect.y0 < current_rect.y0 or
                crop_rect.x1 > current_rect.x1 or crop_rect.y1 > current_rect.y1):
                print(f"  ⚠️  Crop rect выходит за пределы MediaBox! Корректируем...")
                crop_rect = crop_rect.intersect(current_rect)
                print(f"  Скорректированный crop rect: ({crop_rect.x0:.1f}, {crop_rect.y0:.1f}, {crop_rect.x1:.1f}, {crop_rect.y1:.1f})")
            
            # Проверяем, есть ли реальная обрезка
            if (crop_rect.x0 > current_rect.x0 or crop_rect.y0 > current_rect.y0 or
                crop_rect.x1 < current_rect.x1 or crop_rect.y1 < current_rect.y1):
                print(f"  ⚠️  ПРИМЕНЯЕТСЯ ОБРЕЗКА!")
                page.set_cropbox(crop_rect)
                print(f"  Cropbox установлен")
            else:
                print(f"  ✓ Обрезка не применяется (все отступы = 0)")
            
            # Возвращаем оригинальный поворот
            if original_rotation != 0:
                print(f"\n  → Возвращаем поворот на {original_rotation}°")
                page.set_rotation(original_rotation)
                print(f"  Rect после возврата поворота: {page.rect}")
            
            # Сохраняем страницу
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            # Определяем имя файла
            if pages_config and (page_num + 1) in page_prefix_map:
                # Используем конфигурацию из JSON
                prefix = page_prefix_map[page_num + 1]
                # Находим индекс этой страницы в списке для данного префикса
                page_list = pages_config[prefix]
                index_in_list = page_list.index(page_num + 1) + 1
                output_filename = f"{prefix}_{index_in_list}.pdf"
                print(f"  📄 Имя файла (из config): {output_filename}")
            else:
                # Стандартное сохранение по номеру страницы
                output_filename = f"{page_num + 1}.pdf"
                print(f"  📄 Имя файла (стандартное): {output_filename}")
            
            output_path = os.path.join(output_folder, output_filename)
            new_doc.save(output_path)
            new_doc.close()
            
            print(f"  ✅ Сохранено: {output_path}")
        
        doc.close()
        print(f"\n{'='*80}")
        print(f"✅ Готово! Обработано {total_pages} страниц")
        print(f"{'='*80}\n")

    def del_files(self, files_list):

        """
        Простое удаление списка файлов
        
        Args:
            files_list: список путей к файлам для удаления
        """
        print("\n🧹 Удаление временных файлов...")
        print("-" * 50)
        
        deleted = 0
        for file_path in files_list:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"  ✅ Удален: {os.path.basename(file_path)}")
                    deleted += 1
                else:
                    print(f"  ℹ️  Файл не найден: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"  ⚠️  Не удалось удалить {os.path.basename(file_path)}: {e}")
        
        print("-" * 50)
        print(f"📊 Итог: удалено {deleted} из {len(files_list)} файлов")
        
        # Показываем оставшиеся файлы
        remaining = [f for f in files_list if os.path.exists(f)]
        if remaining:
            print(f"\n⚠️  Остались файлы: {', '.join([os.path.basename(f) for f in remaining])}")
            print("💡 Возможно, файлы используются другими программами (закройте AutoCAD)")
        else:
            print("\n✅ Все файлы успешно удалены!")



    def run(self):

        # Запуск

        current_dir = Path.cwd()
        dwg_file = current_dir/ "1.dwg"
        dxf_file = current_dir/ "temp.dxf"

        dsd_file = current_dir / "temp.dsd"
        pdf_file = current_dir / "temp.pdf"

        pdf_file2 = current_dir / "temp2.pdf"

        scr_path = current_dir/ "publish.scr" # Укажите имя вашего скрипта

        #acadconsole_path = r"D:\Program Files\Autodesk\AutoCAD 2021\accoreconsole.exe"
        acadconsole_path = r"C:\Program Files\Autodesk\AutoCAD 2026\accoreconsole.exe"

        dxf_file_clean = current_dir/ "cleaned_dxf.dxf"


        print("========================== ШАГ 1 ========================")
        a = CabDwgProcessor()
        a.convert_dwg_to_dxf_com(dwg_file, dxf_file)  
        print("\n⏳ Ожидание освобождения AutoCAD...")
        time.sleep(3)

        print("========================== ШАГ 2 ========================")
        a.create_dsd_from_dxf(dxf_file, dsd_file, pdf_file)
        print("\n⏳ Ожидание освобождения AutoCAD...")
        time.sleep(3)

        print("========================== ШАГ 3 - ОЧИСТКА DXF ========================")
        a.clean_dxf(dxf_file)
        print("\n⏳ Ожидание освобождения AutoCAD...")
        time.sleep(3)

        print("========================== ШАГ 4 - ПЕЧАТЬ PDF  ========================")
        a.print_dxf_to_pdf(dxf_file, acadconsole_path, dsd_file, scr_path)
        time.sleep(6)

        print("========================== ШАГ 5 - ИЩЕМ СТРАНИЦЫ  ========================")
        a.create_pages_json_from_pdf(pdf_file) # Должен быть установлен шрият ГОСТ тип А
        time.sleep(3)

        print("========================== ШАГ 6 - СОЗДАЕМ DSD ДЛЯ ПЕЧАТИ  ========================")
        a.create_dsd_from_dxf(dxf_file_clean, dsd_file, pdf_file2)

        print("========================== ШАГ 7 - ПЕЧАТЬ ЧИСТОГО PDF  ========================")
        a.print_dxf_to_pdf(dxf_file_clean, acadconsole_path, dsd_file, scr_path)
        time.sleep(3)

        print("========================== ШАГ 8 - НАРЕЗКА PDF  ========================")
        # Загружаем конфигурацию страниц
        pages_config = a.load_pages_config('pages.json')
        print("Входной файл: temp.pdf")
        print("Результат в папке: output_pages")
        a.smart_crop_pdf('temp2.pdf', 'output_pages', pages_config)

        print("========================== ШАГ 9 - УДАЛЯЕМ ВРЕМЕННЫЕ ФАЙЛЫ  ========================")

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

        a.del_files(files_to_delete)