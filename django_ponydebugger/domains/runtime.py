import ast
import code
import codeop
import collections

from django_ponydebugger.domains.base import *


class RuntimePonyDomain(BasePonyDomain):
    def __init__(self, client):
        super(RuntimePonyDomain, self).__init__(client)

        self._consoles = collections.defaultdict(
            lambda: PonyConsole(self.client.log))
        self._remote_objects = {}

    def clear(self):
        self._consoles.clear()
        self._remote_objects.clear()

    @pony_func
    def evaluate(self, params):
        """Run an arbitrary line of Python code."""
        console = self._consoles[params.get('objectGroup', None)]

        expr = params['expression']
        # Some multi-line Python code must be terminated by a blank line, and
        # the PonyDebugger console doesn't allow a blank line, so we treat a
        # single '.' as a blank line.
        if expr == '.':
            expr = ''

        results = console.pony(expr)
        if results['error']:
            return {
                'result': self._make_remote_object(results['error']),
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
                'result': self._make_remote_object(results['result']),
                'wasThrown': False,
            }

    @pony_func
    def getProperties(self, params):
        """Lookup properties of an object from evaluate or getProperties."""
        obj = self._remote_objects[int(params['objectId'])]
        props = []

        if isinstance(obj, (list, tuple, set, frozenset)):
            for i, value in enumerate(obj):
                props.append({
                    'configurable': True,
                    'enumerable': True,
                    'name': str(i),
                    'value': self._make_remote_object(value),
                    'wasThrown': False,
                })

        elif isinstance(obj, dict):
            for key, value in obj.iteritems():
                props.append({
                    'configurable': True,
                    'enumerable': True,
                    'name': str(key),
                    'value': self._make_remote_object(value),
                    'wasThrown': False,
                })

        else:
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
                    'value': self._make_remote_object(value),
                    'wasThrown': was_thrown,
                })

        return {'result': props}

    def _make_remote_object(self, value):
        primitive_types = [
            (type(None), 'undefined'),
            (basestring, 'string'),
            ((int, long, float), 'number'),
            (bool, 'boolean'),
        ]
        for type_or_list, js_name in primitive_types:
            if isinstance(value, type_or_list):
                return {'type': js_name, 'value': value}

        self._remote_objects[id(value)] = value
        result = {
            'objectId': str(id(value)),
            'type': 'object',
            'description': repr(value),
            'className': str(type(value)),
        }
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

    def __init__(self, log):
        local = {
            '__name__': '__console__',
            '__doc__': None,
            '_pony_print': self._pony_print,
            '_pony_result': self._pony_result,
        }
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
