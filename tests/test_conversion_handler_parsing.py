from types import SimpleNamespace

from core.handlers.conversion_handler import ConversionHandler
from core.handlers.models import ConversionSettings


def _handler():
    return ConversionHandler(ConversionSettings(), SimpleNamespace())


def test_format_time():
    h = _handler()
    assert h._format_time(45) == "45s"
    assert h._format_time(90) == "1m 30s"
    assert h._format_time(3665) == "1h 1m"


def test_is_hardware_encoder_error():
    h = _handler()
    assert h._is_hardware_encoder_error("NVENC not available") is True
    assert h._is_hardware_encoder_error("generic failure") is False


def test_parse_ffmpeg_progress_out_time_us():
    h = _handler()
    h._total_duration = 10.0
    line = "foo out_time_us=5000000 bar"
    out = h._parse_ffmpeg_progress(line)
    assert out is not None
    assert out["time"] == 5.0
    assert out["progress"] == 50


def test_parse_ffmpeg_progress_stats_line():
    h = _handler()
    h._total_duration = 100.0
    line = (
        "frame=  100 fps= 25 q=28.0 size=    1024kB "
        "time=00:00:05.00 bitrate=1638.4kbits/s speed=2.0x"
    )
    out = h._parse_ffmpeg_progress(line)
    assert out is not None
    assert out["frame"] == 100
    assert out["fps"] == 25.0
    assert abs(out["time"] - 5.0) < 0.01
    assert out["progress"] == 5
