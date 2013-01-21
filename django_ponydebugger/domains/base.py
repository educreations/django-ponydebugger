def pony_func(func):
    """Decorator to mark expose a method to a PonyDebugger caller."""
    func.is_pony_func = True
    return func


class BasePonyDomain(object):
    STATIC_FUNCS = {}

    def __init__(self, client):
        self.client = client
        self.enabled = False

    @pony_func
    def enable(self, params):
        self.enabled = True

    @pony_func
    def disable(self, params):
        self.enabled = False
