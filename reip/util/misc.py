

class MpValueProp:
    def __init__(self, name):
        self.name = name

    def __get__(self, instance, owner=None):
        return getattr(instance, self.name).value

    def __set__(self, instance, value):
        getattr(instance, self.name).value = value
