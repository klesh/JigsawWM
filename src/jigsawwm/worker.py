"""This module contains the workers for the Jigsaw Window Manager."""

import logging
import time
from queue import SimpleQueue
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)
QUEUE_MSG_CLOSE = 0
QUEUE_MSG_CALL = 1


class ThreadWorker:
    """A worker that runs tasks in a thread pool"""

    executor = ThreadPoolExecutor()
    queue: SimpleQueue = None

    def start_worker(self):
        """Start the worker thread"""
        if self.queue is not None:
            return
        self.queue = SimpleQueue()
        self.executor.submit(self.consume_queue)

    def stop_worker(self):
        """Stop the worker thread"""
        if self.queue is None:
            return
        self.queue.put((QUEUE_MSG_CLOSE, None))
        self.executor.shutdown()
        self.executor = None
        self.queue = None

    def enqueue(self, fn: callable, *args):
        """Enqueue a function call"""
        self.queue.put((QUEUE_MSG_CALL, (fn, *args)))

    def consume_queue(self):
        """Consume the queue and call the corresponding function"""
        while True:
            msg_type, msg_args = self.queue.get()
            if msg_type == QUEUE_MSG_CLOSE:
                logger.info("closing system input handler")
                break
            if msg_type == QUEUE_MSG_CALL:
                fn, args = msg_args[0], msg_args[1:]
                self.try_call(fn, *args)
            else:
                logger.error("unknown message type %s", msg_type)

    def try_call(self, fn, *args):
        """Call a function and log exception if any"""
        try:
            fn(*args)
        except Exception as err:  # pylint: disable=bare-except, broad-exception-caught
            logger.exception("error calling %s", fn, exc_info=True, stack_info=True)
            self.on_consume_queue_error(fn, err)

    def on_consume_queue_error(self, fn: callable, err: Exception):
        """Handle an error in the consume queue"""

    def delay_call(self, delay: float, cb: callable, *args):
        """Call a function in the consume_queue thread with a delay"""

        def wrapped():
            time.sleep(delay)
            self.enqueue(cb, *args)

        self.executor.submit(wrapped)
