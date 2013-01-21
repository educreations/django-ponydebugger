****** django-ponydebugger ******
PonyDebugger is a remote debugging toolset that uses Chrome Developer Tools. It
consists of 2 parts: a server (ponyd) and an iOS client library so you can
debug your iOS apps. This project adds a Python client for debugging Django web
apps.

***** Features *****
    * Network Traffic Debugging
      View all requests received by Django, including request and response
      headers and bodies.

    * Console
      Interact with the running process with a fully functional console.

***** Installation / Setup / Usage *****
Install the django-ponydebugger package and its dependencies with the following
command:
    pip install django-ponydebugger

Update your Django settings module to add
django_ponydebugger.middleware.PonyMiddleware to MIDDLEWARE_CLASSES (preferably
near the beginning).

After receiving the first request, django-ponydebugger will connect to ponyd.
Connect to ponyd with your browser (probably http://127.0.0.1:9000/), and you
should see Django listed. After clicking on Django, django-ponydebugger will
report events to PonyDebugger / Chrome Developer Tools.

***** Known Issues *****
None

***** Future Work *****
    * Timeline support. It would be nice to report received HTTP requests as
      well as other events related to the request (like DB queries) to the
      Timeline.
