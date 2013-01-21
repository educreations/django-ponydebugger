import base64
import getpass
import json
import logging
import os
import socket
import threading
import time

import websocket

from django_ponydebugger.exceptions import *
from django_ponydebugger.domains.console import ConsolePonyDomain
from django_ponydebugger.domains.network import NetworkPonyDomain
from django_ponydebugger.domains.runtime import RuntimePonyDomain

log = logging.getLogger(__name__)


class PonyClient(threading.Thread):
    """PonyDebugger client thread.

    Only one should be active at a time. To get the active PonyClient or
    create a new PonyClient if necessary, call PonyClient.get().
    """
    _instance_lock = threading.Lock()
    _instance = None

    @classmethod
    def get(cls):
        """Return the current (or newly created) PonyClient instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance.start()
            return cls._instance

    def __init__(self):
        super(PonyClient, self).__init__()
        self.daemon = True
        self._ws = None
        self._lock = threading.Lock()
        self._is_open = False

        self._callbacks = {}
        self._next_command_id = 0

        self._domains = {
            'Console': ConsolePonyDomain(self),
            'Network': NetworkPonyDomain(self),
            'Runtime': RuntimePonyDomain(self),
        }

    @log_on_exc
    def run(self):
        """Thread body which connects to PonyDebugger service."""
        while True:
            log.debug('Connecting Pony websocket')
            self._ws = websocket.WebSocketApp(
                'ws://127.0.0.1:9000/device',
                on_message=self.on_message,
                on_close=self.on_close,
                on_open=self.on_open)
            self._ws.run_forever()
            time.sleep(20)

    @log_on_exc
    def on_open(self, ws):
        log.info('Connected to Pony server')
        with self._lock:
            self._is_open = True

        icon_path = os.path.join(os.path.dirname(__file__), 'django-icon.png')
        self.send_notification(
            'Gateway.registerDevice',
            app_name='Django server',
            #app_version='app-version',
            #app_id='app-id',
            app_icon_base64=base64.b64encode(open(icon_path).read()),
            device_id='N/A',
            device_name=socket.gethostname(),
            device_model=getpass.getuser(),
        )

    @log_on_exc
    def on_message(self, ws, message):
        if not isinstance(message, unicode):
            assert isinstance(message, str), (message,)
            message = message.decode('utf-8')
        data = json.loads(message)
        log.debug('Received Pony message: %r', data)

        # Notification
        if 'id' not in data:
            assert 'method' in data, data
            self.handle_notification(data['method'], data.get('params', {}))

        # Function request
        elif 'method' in data:
            exc = None
            try:
                result = self.handle_command(
                    data['method'], data.get('params', {}))
            except PonyError as exc:
                result = None
            self._send_json({
                'id': data['id'],
                'result': result,
                'error': exc.args[0] if exc is not None else None,
            })

        # Function response
        elif 'result' in data:
            if data['id'] in self._callbacks:
                self._callbacks[data['id']](data['result'])

        else:
            raise ValueError('Unexpected message', data)

    @log_on_exc
    def on_close(self, ws):
        with self._lock:
            if self._is_open:
                log.error('Pony websocket closed')
            else:
                log.debug('Pony websocket never connected')
            self._is_open = False

    def _send_json(self, data):
        log.debug('Sending Pony data: %r', data)
        with self._lock:
            if self._is_open:
                self._ws.send(json.dumps(data))

    def send_notification(self, method, **params):
        self._send_json({'method': method, 'params': params})

    def get_domain(self, name):
        try:
            return self._domains[name]
        except KeyError:
            raise UnknownMethod()

    def _get_func(self, full_name):
        assert '.' in full_name, (full_name,)
        domain_name, method_name = full_name.split('.', 1)
        domain = self.get_domain(domain_name)
        if method_name in domain.STATIC_FUNCS:
            return lambda params: domain.STATIC_FUNCS[method_name]
        else:
            func = getattr(domain, method_name, None)
            if not getattr(func, 'is_pony_func', False):
                raise UnknownMethod()
            return func

    def handle_command(self, method, params):
        try:
            func = self._get_func(method)
        except UnknownMethod:
            log.info('Received unknown Pony command: %r %r', method, params)
            raise PonyError('Unsupported method')
        return func(params)

    def handle_notification(self, method, params):
        try:
            func = self._get_func(method)
        except UnknownMethod:
            log.info(
                'Received unknown Pony notification: %r %r', method, params)
        else:
            func(params)

    def log(self, message):
        self.send_notification(
            'Console.messageAdded',
            message={
                'level': 'log',
                'source': 'other',
                'text': message,
            })
