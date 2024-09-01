"""Test jigsawwm.worker module"""

import time
from jigsawwm.worker import ThreadWorker


class TestThreadWorker:
    """Test the ThreadWorker class"""

    worker: ThreadWorker

    def setup_method(self):
        """Setup the ThreadWorker class"""
        self.worker = ThreadWorker()
        self.worker.start_worker()

    def teardown_method(self):
        """Teardown the ThreadWorker class"""
        self.worker.stop_worker()

    def test_periodic_worker(self, mocker):
        """Test the ThreadWorker class periodic_call method"""
        cb = mocker.Mock()
        self.worker.periodic_call(0.1, cb, 1, 2)
        # show not call immediately
        assert cb.call_count == 0
        # first check
        time.sleep(0.2)
        assert cb.call_count > 0
        # second check
        time.sleep(0.2)
        assert cb.call_count > 1
        assert cb.call_args[0] == (1, 2)
        # should stop calling after stop_worker
        self.worker.stop_worker()
        time.sleep(0.1)
        call_count = cb.call_count
        time.sleep(0.2)
        assert cb.call_count == call_count
