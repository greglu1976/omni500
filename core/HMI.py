

class HMI:
    def __init__(self, order_code=''):
        self.order_code = order_code
        self.leds_module = ["ИЧМ",]
        self.fks_module = ["ИЧМ",]

        modules = order_code.split('-')[3:]
        count = 0
        for module in modules:
            count +=1
            if module == "С":
                self.leds_module.append(f"Модуль расширения {count} на 16 светодиодов")
            if module == "К":
                self.fks_module.append(f"Модуль расширения {count} на 16 функциональных кнопок")                



    def get_leds(self):
        return self.leds_module

    def get_fks(self):
        return self.fks_module