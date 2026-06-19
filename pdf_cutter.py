import fitz  # PyMuPDF
import os

def crop_pages_force_normal(input_pdf, output_folder, margins_mm):
    """
    Принудительно убирает поворот и поворачивает содержимое на 90 градусов при обрезке
    """
    os.makedirs(output_folder, exist_ok=True)
    
    doc = fitz.open(input_pdf)
    total_pages = len(doc)
    
    mm_to_points = 2.83465
    top, right, bottom, left = [m * mm_to_points for m in margins_mm]
    
    for page_num in range(total_pages):
        page = doc[page_num]
        
        # Принудительно убираем поворот страницы
        page.set_rotation(0)
        
        # Обновляем прямоугольник после сброса поворота
        rect = page.rect
        
        # Создаем прямоугольник для обрезки
        crop_rect = fitz.Rect(
            rect.x0 + left,
            rect.y0 + top,
            rect.x1 - right,
            rect.y1 - bottom
        )
        
        # Создаем новый PDF с повернутой страницей
        new_doc = fitz.open()
        
        # Меняем ширину и высоту местами для поворота на 90 градусов
        new_page = new_doc.new_page(width=crop_rect.height, height=crop_rect.width)
        
        # Вставляем содержимое с поворотом на -90 градусов
        new_page.show_pdf_page(
            new_page.rect, 
            doc, 
            page_num, 
            clip=crop_rect,
            rotate=-90  # Поворот содержимого на -90 градусов
        )
        
        # Сохраняем
        output_path = os.path.join(output_folder, f"{page_num + 1}.pdf")
        new_doc.save(output_path)
        new_doc.close()
        
        print(f"Сохранена страница {page_num + 1} -> {output_path}")
    
    doc.close()
    print(f"\n✅ Готово! Сохранено {total_pages} страниц в папку '{output_folder}'")

# Использование
margins_mm = (6, 6, 21, 6)
crop_pages_force_normal('input.pdf', 'output_pages', margins_mm)