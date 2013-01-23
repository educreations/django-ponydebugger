import ast
import code
import codeop
import collections
import json
import logging

from django_ponydebugger.domains.base import *
from django_ponydebugger.exceptions import PonyError

log = logging.getLogger(__name__)


class RuntimePonyDomain(BasePonyDomain):
    def __init__(self, client):
        super(RuntimePonyDomain, self).__init__(client)

        self._locals = {}
        self._consoles = collections.defaultdict(
            lambda: PonyConsole(self.client.log, self._locals))
        self._remote_objects = {}
        self._remote_objects_by_group = {}

        # Pre-populate some entries in locals
        self._consoles[''].pony('')

    def clear(self):
        self._consoles.clear()

    @pony_func
    def evaluate(self, params):
        """Run an arbitrary line of Python code."""
        obj_group = params.get('objectGroup', '')
        console = self._consoles[obj_group]
        by_value = params.get('returnByValue', False)

        expr = params['expression']

        # Support looking up 'this' for auto-completions.
        if expr == 'this':
            return {
                'result': self._make_remote_object(
                    self._locals, by_value, obj_group),
                'wasThrown': False,
            }

        # Some multi-line Python code must be terminated by a blank line, and
        # the PonyDebugger console doesn't allow a blank line, so we treat a
        # single '.' as a blank line.
        if expr == '.':
            expr = ''

        results = console.pony(expr)
        if results['error']:
            return {
                'result': self._make_remote_object(
                    results['error'], False, obj_group),
                'wasThrown': True,
            }
        elif results['partial']:
            if console.partial_count == 1:
                self.client.log('... (use . for blank line if necessary)')
            else:
                self.client.log('...')
            return {}
        elif results['result'] is None:
            return {}
        else:
            return {
                'result': self._make_remote_object(
                    results['result'], by_value, obj_group),
                'wasThrown': False,
            }

    @pony_func
    def getProperties(self, params):
        """Lookup properties of an object from evaluate or getProperties."""
        obj, obj_group = self._remote_objects[int(params['objectId'])]
        props = []

        if isinstance(obj, (list, tuple, set, frozenset)):
            for i, value in enumerate(obj):
                props.append({
                    'configurable': True,
                    'enumerable': True,
                    'name': str(i),
                    'value': self._make_remote_object(value, False, obj_group),
                    'wasThrown': False,
                })

        if isinstance(obj, dict):
            for key, value in obj.iteritems():
                props.append({
                    'configurable': True,
                    'enumerable': True,
                    'name': str(key),
                    'value': self._make_remote_object(value, False, obj_group),
                    'wasThrown': False,
                })

        for name in dir(obj):
            if name.startswith('__') and name.endswith('__'):
                continue
            try:
                value = getattr(obj, name)
                was_thrown = False
            except AttributeError as exc:
                value = exc
                was_thrown = True
            props.append({
                'configurable': True,
                'enumerable': True,
                'name': name,
                'value': self._make_remote_object(value, False, obj_group),
                'wasThrown': was_thrown,
            })

        return {'result': props}

    @pony_func
    def releaseObjectGroup(self, params):
        obj_group = params.get('objectGroup', '')
        for obj_id in self._remote_objects_by_group.pop(obj_group, []):
            del self._remote_objects[obj_id]

    @pony_func
    def callFunctionOn(self, params):
        obj, obj_group = self._remote_objects[int(params['objectId'])]
        by_value = params.get('returnByValue', False)

        pre_args = params['functionDeclaration'].split('(')[0]
        if 'getCompletions' in pre_args:
            func = self._get_completions
        else:
            raise PonyError('Unsupported function')

        try:
            result = func(obj, params.get('arguments', []))
        except Exception as exc:
            return {
                'result': self._make_remote_object(exc, False, obj_group),
                'wasThrown': True,
            }
        else:
            return {
                'result': self._make_remote_object(result, by_value, obj_group),
                'wasThrown': False,
            }

    def _make_remote_object(self, value, by_value, obj_group):
        primitive_types = [
            (type(None), 'undefined'),
            (basestring, 'string'),
            ((int, long, float), 'number'),
            (bool, 'boolean'),
        ]
        for type_or_list, js_name in primitive_types:
            if isinstance(value, type_or_list):
                return {'type': js_name, 'value': value}

        if by_value:
            # Ensure that this is a JSON-serializable value
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                log.error('Object %r was not JSON serializable', value)
                raise PonyError(
                    'Requested return-by-value, but result was not JSON '
                    'serializable')
            else:
                return {'type': 'object', 'value': value}

        self._remote_objects[id(value)] = (value, obj_group)
        self._remote_objects_by_group.setdefault(
            obj_group, set()).add(id(value))
        result = {
            'objectId': str(id(value)),
            'type': 'object',
            'description': repr(value),
            'className': str(type(value)),
        }
        if len(result['description']) > 200:
            result['description'] = result['description'][:197] + '...'
        return result

    def _get_completions(self, obj, args):
        if args:
            if args[0] == 'string':
                obj = ''
            elif args[0] == 'number':
                obj = 0
            elif args[0] == 'boolean':
                obj = False
        result = {}
        if obj is self._locals:
            for name in obj:
                result[name] = True
            for name in obj['__builtins__']:
                result[name] = True
        else:
            for name in dir(obj):
                if name.startswith('__') and name.endswith('__'):
                    continue
                result[name] = True
        return result


class PonyConsole(code.InteractiveConsole):
    """Custom InteractiveConsole which can be remotely controlled.

    The main interface to this class is the pony() method.

    Normally in the interactive interpreter, any simple expression (not
    assignments, etc) outside of a function or class that evaluates to anything
    other than None gets printed to stdout. Obviously, we would prefer the
    value get returned to PonyDebugger. In order to accomplish this, we hook
    into the compilation step and wrap such expressions in a call to
    _pony_result, which we inject into the namespace.

    We also do something similar for the print statement to turn send the
    output to PonyDebugger.
    """

    def __init__(self, log, local):
        if not local:
            local.update({
                '__name__': '__console__',
                '__doc__': None,
            })
        code.InteractiveConsole.__init__(self, local)
        self.compile.compiler = PonyConsole.PonyCompiler()
        self.log = log
        self.partial_count = 0

    def _pony_result(self, result):
        self.result = result

    def _pony_print(self, dest, nl, *values):
        self.log(' '.join(str(obj) for obj in values))

    def write(self, data):
        self.errors.append(data)

    def pony(self, src):
        """Run a single line of Python code."""
        self.errors = []
        self.result = None
        self.locals.update({
            '_pony_print': self._pony_print,
            '_pony_result': self._pony_result,
        })
        partial = self.push(src)
        if partial:
            self.partial_count += 1
        return {
            'error': ''.join(self.errors),
            'result': self.result,
            'partial': partial,
        }

    class PonyCompiler(codeop.Compile):
        """Custom compiler which performs print and expr substitutions."""
        def __call__(self, source, filename, symbol):
            codeop.Compile.__call__(self, source, filename, symbol)
            tree = ast.parse(source, filename, symbol)
            PonyConsole.PrintTransformer().visit(tree)
            PonyConsole.ExprTransformer().visit(tree)
            return codeop.Compile.__call__(self, tree, filename, symbol)

    class NodeHelper(object):
        """Helper to remove excess code from *Transformer below."""

        def __init__(self, old_node):
            self.old_node = old_node

        def __getattr__(self, name):
            def wrapper(**kwargs):
                node_type = getattr(ast, name)
                if name == 'Name':
                    kwargs['ctx'] = ast.Load()
                new_node = node_type(**kwargs)
                return ast.copy_location(new_node, self.old_node)
            return wrapper

    class PrintTransformer(ast.NodeTransformer):
        def visit_Print(self, node):
            """Transform a print statement into a _pony_print call."""
            node = self.generic_visit(node)
            new = PonyConsole.NodeHelper(node)
            return new.Expr(
                value=new.Call(
                    func=new.Name(id='_pony_print'),
                    args=[
                        node.dest or new.Name(id='None'),
                        new.Name(id='True' if node.nl else 'False'),
                    ] + node.values,
                    keywords=[],
                ),
            )

    class ExprTransformer(ast.NodeTransformer):
        def visit_ClassDef(self, node):
            """Avoid recursing into classes."""
            return node

        def visit_FunctionDef(self, node):
            """Avoid recursing into functions."""
            return node

        def visit_Expr(self, node):
            """Transform an expression into a _pony_result call."""
            new = PonyConsole.NodeHelper(node)
            return new.Expr(
                value=new.Call(
                    func=new.Name(id='_pony_result'),
                    args=[node.value],
                    keywords=[],
                ),
            )
