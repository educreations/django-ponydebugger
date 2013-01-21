import functools
import logging

log = logging.getLogger(__name__)

__all__ = ['PonyError', 'UnknownMethod', 'log_on_exc']


class PonyError(Exception):
    """An error to be returned to the PonyDebugger caller."""
    pass


class UnknownMethod(Exception):
    pass


def log_on_exc(func):
    """Decorator which logs errors on exceptions.

    The websocket and threading modules both can silently ignore errors in
    certain cases. This decorator ensures that exceptions raised by its
    decorated functions are logged.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            log.error(
                'Error in pony function %r args=%r kwargs=%r',
                func, args, kwargs, exc_info=True)
            raise

    return wrapper
