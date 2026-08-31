import win32com.client

try:
    acad = win32com.client.Dispatch("AutoCAD.Application.23")
    print(f"✓ УСПЕШНО! Версия: {acad.Version}")
except Exception as e:
    print(f"✗ Ошибка: {e}")