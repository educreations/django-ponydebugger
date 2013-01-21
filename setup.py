from setuptools import setup

setup(
    name='django-ponydebugger',
    version='0.0.1',
    description='PonyDebugger support for Django',
    packages=[
        'django_ponydebugger',
        'django_ponydebugger.domains',
    ],
    package_data={
        'django_ponydebugger': ['django-icon.png'],
    },
    install_requires=[
        'websocket-client',
    ],
    author='Matthew Eastman',
    author_email='matt@educreations.com',
    url='https://github.com/educreations/django-ponydebugger',
)
