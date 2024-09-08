"Test w32.monitor_detector"

from jigsawwm.w32.monitor_detector import MonitorDetector, Rect


def test_full_rect(mocker):
    """Test the refresh_full_rect method"""
    md = MonitorDetector()
    md.monitors = [
        mocker.Mock(get_rect=lambda: Rect(0, 0, 1920, 1080)),
        mocker.Mock(get_rect=lambda: Rect(-800, -100, 0, 600)),
    ]
    assert md.refresh_full_rect() == Rect(-800, -100, 1920, 1080)
