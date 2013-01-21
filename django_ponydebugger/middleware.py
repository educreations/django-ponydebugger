from django_ponydebugger import client


class PonyMiddleware(object):
    def __init__(self):
        self.network = client.PonyClient.get().get_domain('Network')

    def process_request(self, request):
        self.network.process_request(request)
        return None

    def process_response(self, request, response):
        self.network.process_response(request, response)
        return response
