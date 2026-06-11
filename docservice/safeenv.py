from markupsafe import Markup
from jinja2 import Undefined, Environment

PLACEHOLDER = "{{ WARNING: param not found }}"

class SilentUndefined(Undefined):
    def __str__(self):
        return PLACEHOLDER

    def __html__(self):
        return Markup(PLACEHOLDER)

    def __getattr__(self, name):
        return self

    __getitem__ = __getattr__
    __repr__ = __str__
    __bool__ = lambda self: False


class SafeEnvironment(Environment):
    def getattr(self, obj, attribute):
        if obj is None or isinstance(obj, Undefined):
            return self.undefined(name=str(attribute))
        return super().getattr(obj, attribute)

    def getitem(self, obj, argument):
        if obj is None or isinstance(obj, Undefined):
            return self.undefined(name=str(argument))
        return super().getitem(obj, argument)


env = SafeEnvironment(undefined=SilentUndefined)