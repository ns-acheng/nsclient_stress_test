import threading
import time

from util_time import smart_sleep


class TestSmartSleep:
    def test_completes_full_duration(self, stop_event):
        start = time.time()
        result = smart_sleep(1.0, stop_event)
        elapsed = time.time() - start
        assert result is False
        assert elapsed >= 1.0

    def test_interrupted_by_stop_event(self, stop_event):
        def set_after_delay():
            time.sleep(0.3)
            stop_event.set()

        timer = threading.Thread(target=set_after_delay)
        timer.start()

        start = time.time()
        result = smart_sleep(5.0, stop_event)
        elapsed = time.time() - start

        assert result is True
        assert elapsed < 2.0
        timer.join()

    def test_zero_duration(self, stop_event):
        start = time.time()
        result = smart_sleep(0, stop_event)
        elapsed = time.time() - start
        assert result is False
        assert elapsed < 1.0

    def test_negative_duration(self, stop_event):
        start = time.time()
        result = smart_sleep(-1, stop_event)
        elapsed = time.time() - start
        assert result is False
        assert elapsed < 1.0

    def test_already_set_event_returns_immediately(self):
        event = threading.Event()
        event.set()
        start = time.time()
        result = smart_sleep(5.0, event)
        elapsed = time.time() - start
        assert result is True
        assert elapsed < 1.0
