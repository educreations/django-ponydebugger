from os.path import join, dirname
from setuptools import setup

import django_ponydebugger


with open(join(dirname(__file__), 'README.rst')) as f:
    readme = f.read()

with open(join(dirname(__file__), 'LICENSE')) as f:
    license = f.read()

setup(
    name='django-ponydebugger',
    version=django_ponydebugger.__version__,
    description='PonyDebugger support for Django',
    long_description=readme,
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
    license=license,
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Debuggers',
    ],
)
