# Общие вспомогательные функции

from logger.logger import Logger

def format_status(value):
    """Форматирование числового статуса в символьное представление
    
    Параметры:
        value (int/str): Входное значение статуса
        
    Возвращает:
        str: Символьное представление статуса:
            - '+' для значения 1
            - '-' для значения 0
            - '*' для значения 2
            - '⊕' для значения 3
            - '?' для всех остальных случаев
    """
    status_mapping = {
        '0': '-',
        '1': '+',
        '2': '*',
        '3': '-'  # Символ плюса в кружочке (U+2295)
    }
    if value is None:
        Logger.error('Пустое значение в столбцах статусов!')
        return '?'
    str_value = str(int(float(str(value).strip())))
    return status_mapping.get(str_value, '?')