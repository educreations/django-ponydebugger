from setuptools import setup

setup(
    name='django-ponydebugger',
    version='0.0.1',
    description='PonyDebugger support for Django',
    packages=['django_ponydebugger'],
    install_requires=[
        'websocket-client',
    ],
)
