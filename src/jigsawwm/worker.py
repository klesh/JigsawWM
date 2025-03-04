"""This module contains the workers for the Jigsaw Window Manager."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from queue import SimpleQueue

logger = logging.getLogger(__name__)
QUEUE_MSG_CLOSE = 0
QUEUE_MSG_CALL = 1


class ThreadWorker:
    """A worker that runs tasks in a thread pool"""

    stopped = False
    executor: ThreadPoolExecutor = None
    queue: SimpleQueue = None

    def start_worker(self):
        """Start the worker thread"""
        self.queue = SimpleQueue()
        self.executor = ThreadPoolExecutor()
        self.executor.submit(self.consume_queue)

    def stop_worker(self):
        """Stop the worker thread"""
        if self.stopped:
            return
        self.queue.put((QUEUE_MSG_CLOSE, None))
        # self.executor.shutdown()

    def enqueue(self, fn: callable, *args, **kwargs):
        """Enqueue a function call"""
        self.queue.put_nowait((QUEUE_MSG_CALL, (fn, args, kwargs)))

    def consume_queue(self):
        """Consume the queue and call the corresponding function"""
        while True:
            msg_type, msg = self.queue.get()
            if msg_type == QUEUE_MSG_CLOSE:
                logger.info("closing system input handler")
                self.stopped = True
                break
            if msg_type == QUEUE_MSG_CALL:
                fn, args, kwargs = msg
                self.try_call(fn, *args, **kwargs)
            else:
                logger.error("unknown message type %s", msg_type)

    def try_call(self, fn, *args, **kwargs):
        """Call a function and log exception if any"""
        try:
            fn(*args, **kwargs)
        except Exception as err:  # pylint: disable=bare-except, broad-exception-caught
            logger.exception(
                "error calling %s %s", fn, args, exc_info=True, stack_info=True
            )
            self.on_consume_queue_error(fn, err)

    def on_consume_queue_error(self, fn: callable, err: Exception):
        """Handle an error in the consume queue"""

    def delay_call(self, delay: float, cb: callable, *args):
        """Call a function in the consume_queue thread with a delay"""

        def wrapped():
            time.sleep(delay)
            self.enqueue(cb, *args)

        self.executor.submit(wrapped)

    def periodic_call(self, interval: float, cb: callable, *args):
        """Call a function periodically in the consume_queue thread"""
        logger.info("periodic_call %s %s", interval, cb)

        def wrapped():
            while not self.stopped:
                time.sleep(interval)
                self.enqueue(cb, *args)

        self.executor.submit(wrapped)
