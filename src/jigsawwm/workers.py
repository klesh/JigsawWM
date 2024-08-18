"""This module contains the workers for the Jigsaw Window Manager."""
import logging
import time
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=100)
handle_exc: Optional[Callable[[Exception], None]] = None

def submit(func, *args, **kwargs):
    """Execute a function in a thread pool and print the exception if any

    :param func: the function to execute
    :param args: the arguments to pass to the function
    :param kwargs: the keyword arguments to pass to the function
    """

    def wrapped():
        logger.debug("executing %s", func)
        try:
            func()
        except Exception as e: # pylint: disable=broad-exception-caught
            logger.exception(e, exc_info=True)
            if handle_exc:
                handle_exc(e) # pylint: disable=not-callable

    return executor.submit(wrapped, *args, **kwargs)

def submit_with_delay(cb: callable, delay: float):
    """Submit a callback with a delay"""

    def wrapped():
        time.sleep(delay)
        cb()

    submit(wrapped)
