from setuptools import setup

import django_ponydebugger

setup(
    name='django-ponydebugger',
    version=django_ponydebugger.__version__,
    description='PonyDebugger support for Django',
    long_description=open('README.rst').read(),
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
    license='MIT',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Debuggers',
    ],
)
