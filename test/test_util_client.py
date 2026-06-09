import threading
from unittest.mock import MagicMock, patch

import pytest

import util_client


class TestWaitInterval:
    def test_completes_full_duration(self, stop_event):
        with patch.object(util_client, "smart_sleep", return_value=False):
            assert util_client._wait_interval(6, stop_event) is False

    def test_interrupted_mid_step(self, stop_event):
        with patch.object(
            util_client, "smart_sleep", side_effect=[False, True]
        ):
            assert util_client._wait_interval(6, stop_event) is True

    def test_remainder_handled(self, stop_event):
        calls = []

        def _fake_sleep(dur, evt):
            calls.append(dur)
            return False

        with patch.object(util_client, "smart_sleep", side_effect=_fake_sleep):
            util_client._wait_interval(5, stop_event)
        assert calls[-1] == 1

    def test_zero_duration(self, stop_event):
        with patch.object(util_client, "smart_sleep", return_value=False):
            assert util_client._wait_interval(0, stop_event) is False

    def test_remainder_interrupted(self, stop_event):
        with patch.object(
            util_client, "smart_sleep",
            side_effect=[False, False, True],
        ):
            assert util_client._wait_interval(5, stop_event) is True


class TestClientTogglerLoop:
    @pytest.fixture
    def svc_mgr(self):
        mgr = MagicMock()
        mgr.get_service_status.return_value = "RUNNING"
        return mgr

    @pytest.fixture
    def diag_mgr(self):
        return MagicMock()

    def test_single_iteration_disables_and_reenables(
        self, stop_event, svc_mgr, diag_mgr
    ):
        call_count = 0

        def _fake_wait(dur, evt):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                stop_event.set()
                return True
            return False

        with patch.object(util_client, "_wait_interval", side_effect=_fake_wait):
            with patch.object(util_client, "random") as mock_rand:
                mock_rand.randint.return_value = 10
                util_client.client_toggler_loop(
                    stop_event,
                    service_name="stAgentSvc",
                    is_64bit=True,
                    enable_min=5,
                    enable_max=15,
                    disable_ratio=0.5,
                    service_mgr=svc_mgr,
                    diag_mgr=diag_mgr,
                )

        diag_mgr.enable_client_tracing.assert_any_call(False, True)

    def test_skips_toggle_when_service_not_running(
        self, stop_event, svc_mgr, diag_mgr
    ):
        svc_mgr.get_service_status.return_value = "STOPPED"
        call_count = 0

        def _fake_wait(dur, evt):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                stop_event.set()
                return True
            return False

        with patch.object(util_client, "_wait_interval", side_effect=_fake_wait):
            with patch.object(util_client, "random") as mock_rand:
                mock_rand.randint.return_value = 10
                util_client.client_toggler_loop(
                    stop_event,
                    service_name="stAgentSvc",
                    is_64bit=True,
                    enable_min=5,
                    enable_max=15,
                    disable_ratio=0.5,
                    service_mgr=svc_mgr,
                    diag_mgr=diag_mgr,
                )

        diag_mgr.enable_client_tracing.assert_not_called()

    def test_client_enabled_event_lifecycle(
        self, stop_event, svc_mgr, diag_mgr
    ):
        client_evt = threading.Event()
        call_count = 0

        def _fake_wait(dur, evt):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                stop_event.set()
                return True
            return False

        with patch.object(util_client, "_wait_interval", side_effect=_fake_wait):
            with patch.object(util_client, "random") as mock_rand:
                mock_rand.randint.return_value = 10
                util_client.client_toggler_loop(
                    stop_event,
                    service_name="stAgentSvc",
                    is_64bit=True,
                    enable_min=5,
                    enable_max=15,
                    disable_ratio=0.5,
                    client_enabled_event=client_evt,
                    service_mgr=svc_mgr,
                    diag_mgr=diag_mgr,
                )

        assert not client_evt.is_set()

    def test_no_service_mgr_still_toggles(
        self, stop_event, diag_mgr
    ):
        call_count = 0

        def _fake_wait(dur, evt):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                stop_event.set()
                return True
            return False

        with patch.object(util_client, "_wait_interval", side_effect=_fake_wait):
            with patch.object(util_client, "random") as mock_rand:
                mock_rand.randint.return_value = 10
                util_client.client_toggler_loop(
                    stop_event,
                    service_name="stAgentSvc",
                    is_64bit=True,
                    enable_min=5,
                    enable_max=15,
                    disable_ratio=0.5,
                    diag_mgr=diag_mgr,
                )

        diag_mgr.enable_client_tracing.assert_not_called()

    def test_min_disable_time_is_one(
        self, stop_event, svc_mgr, diag_mgr
    ):
        call_count = 0
        disable_dur = None

        def _fake_wait(dur, evt):
            nonlocal call_count, disable_dur
            call_count += 1
            if call_count == 2:
                disable_dur = dur
                stop_event.set()
                return True
            return False

        with patch.object(util_client, "_wait_interval", side_effect=_fake_wait):
            with patch.object(util_client, "random") as mock_rand:
                mock_rand.randint.return_value = 1
                util_client.client_toggler_loop(
                    stop_event,
                    service_name="stAgentSvc",
                    is_64bit=True,
                    enable_min=1,
                    enable_max=3,
                    disable_ratio=0.01,
                    service_mgr=svc_mgr,
                    diag_mgr=diag_mgr,
                )

        assert disable_dur is not None
        assert disable_dur >= 1
