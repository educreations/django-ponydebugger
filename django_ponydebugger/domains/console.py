from django_ponydebugger.domains.base import *


class ConsolePonyDomain(BasePonyDomain):
    @pony_func
    def clearMessages(self, params):
        self.client.get_domain('Runtime').clear()
