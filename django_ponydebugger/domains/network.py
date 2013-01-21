import collections
import gzip
import StringIO
import threading
import time

from django.utils.http import urlencode

from django_ponydebugger.domains.base import *
from django_ponydebugger.exceptions import PonyError


class NetworkPonyDomain(BasePonyDomain):
    STATIC_FUNCS = dict(
        BasePonyDomain.STATIC_FUNCS,
        canClearBrowserCache=False,
        canClearBrowserCookies=False,
    )

    def __init__(self, client):
        super(NetworkPonyDomain, self).__init__(client)

        self._lock = threading.Lock()
        self._next_request_id = 0
        self._bodies = collections.deque(maxlen=15)

    @pony_func
    def getResponseBody(self, params):
        with self._lock:
            for req_id, body in self._bodies:
                if req_id == params['requestId']:
                    break
            else:
                raise PonyError('Request not found')
        return {'body': body, 'base64Encoded': False}

    def process_request(self, request):
        """Report the start of each HTTP request to PonyDebugger."""
        if not self.enabled:
            return

        with self._lock:
            request_id = str(self._next_request_id)
            self._next_request_id += 1

        request_headers = {}
        for name in request.META:
            if (name in ('CONTENT_LENGTH', 'CONTENT_TYPE') or
                    name.startswith('HTTP_')):
                value = request.META[name]
                if name.startswith('HTTP_'):
                    name = name[len('HTTP_'):]
                request_headers[name.replace('_', '-').title()] = value

        request_data = {
            'headers': request_headers,
            'method': request.method,
            'url': request.build_absolute_uri(),
        }

        if request.method != 'GET':
            if request.FILES:
                form_data = dict(request.POST.items())
                form_data['X-DjangoPony-Note'] = (
                    'Request included %d file(s), which have been removed; '
                    'the request has been reformatted' % len(request.FILES))
                for name, value in request.FILES.iteritems():
                    form_data[name] = '<file %s, %d bytes>' % (
                        value.name, value.size)
                request_data['postData'] = urlencode(form_data)
                request_headers.update({
                    'X-DjangoPony-Orig-Content-Type': request_headers['Content-Type'],
                    'Content-Type': 'application/x-www-form-urlencoded',
                })
            else:
                request_data['postData'] = request.body.decode('latin1')

        self.client.send_notification(
            'Network.requestWillBeSent',
            requestId=request_id,
            loaderId='',
            frameId='',
            documentURL=request.build_absolute_uri(),
            request=request_data,
            timestamp=time.time(),
            initiator={'type': 'other'},
        )

        request.pony_state = {
            'id': request_id,
            'request_headers': request_headers,
        }

    def process_response(self, request, response):
        """Report the end of each HTTP request to PonyDebugger."""
        if not self.enabled or not hasattr(request, 'pony_state'):
            return response

        request_id = request.pony_state['id']

        response_headers = dict(response.items())
        if getattr(request, 'user', None) and request.user.is_authenticated():
            response_headers.update({
                'X-DjangoPony-User-ID': str(request.user.pk),
                'X-DjangoPony-User-Username': request.user.username,
                'X-DjangoPony-User-Email': request.user.email,
            })

        body = response.content
        if response.get('content-encoding', '') == 'gzip':
            body = gzip.GzipFile(fileobj=StringIO.StringIO(body)).read()
        if ('utf-8' in response['content-type'] or
                response['content-type'].startswith('text/') or
                'json' in response['content-type']):
            body = body.decode('utf-8')
            with self._lock:
                self._bodies.append((request_id, body))

        self.client.send_notification(
            'Network.responseReceived',
            requestId=request_id,
            loaderId='',
            frameId='',
            timestamp=time.time(),
            type='Other',
            response={
                'connectionId': 0,
                'connectionReused': False,
                'headers': response_headers,
                'requestHeaders': request.pony_state['request_headers'],
                'mimeType': response['content-type'].split(';')[0],
                'status': response.status_code,
                'statusText': '',
                'url': request.build_absolute_uri(),
            },
        )
        self.client.send_notification(
            'Network.dataReceived',
            requestId=request_id,
            timestamp=time.time(),
            dataLength=len(response.content),
            encodedDataLength=len(body),
        )
        self.client.send_notification(
            'Network.loadingFinished',
            requestId=request_id,
            timestamp=time.time(),
        )
        #self.client.send_notification(
        #    'Timeline.eventRecorded',
        #    record={
        #        'startTime': time.time() - 10,
        #        'endTime': time.time(),
        #        'data': {
        #            'requestId': '0',
        #            'url': '///',
        #            'requestMethod': 'GET',
        #        },
        #        'type': 'ResourceSendRequest',
        #        #'children': [],
        #    },
        #)
