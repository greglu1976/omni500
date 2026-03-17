# Класс, представляющий полностью устройство

from core.FSU import FSU
from core.Modules import Modules
from core.HMI import HMI
from core.AuxFuncs import AuxFuncs

from logger.logger import Logger

class Device:
    def __init__(self, order_code, full_description, order_code_hmi='', fsu_type=''):
        self.order_code = order_code
        self.full_description =  full_description        
        self.order_code_hmi = order_code_hmi

        # вычисляем версию ФСУ , вида ДЗТ2-2.1 
        if fsu_type == '':
            parts = order_code.split('-')
            fsu_type = f"{parts[2]}-{parts[-1]}"
        self.fsu_type = fsu_type

        # Используем фиксированное имя базы данных
        db_path = "fbdata.db"

        self.fsu = FSU(db_path=db_path, fsu_type=self.fsu_type)
        self.modules = Modules(order_code=self.order_code)

        self.hmi = HMI(order_code=self.order_code_hmi)
        self.aux_funcs = AuxFuncs()


# Запуск
if __name__ == "__main__":

    from core.DeviceDataManager import DeviceDataManager

    device_data_manager = DeviceDataManager()
    device_data = device_data_manager.get_device_by_name_and_version(name = "ЮНИТ-М300-ДЗТ2", version="1.0")

    # создаем устройство
    order_code = device_data["order_code"]
    full_description = device_data["full_description"]
    order_code_hmi=device_data["order_code_hmi"]
    device = Device(order_code=order_code, full_description=full_description, order_code_hmi=order_code_hmi)

    # создаем бланк уставок
    from SettingBlanc import SettingBlanc

    setting_blanc = SettingBlanc(code=device_data["setting_blanc_code"])
    setting_blanc.get_blanc(device=device)
