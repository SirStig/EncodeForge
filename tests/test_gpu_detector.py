"""
Mocked unit tests for utils.gpu_detector — OS backend matrix, Intel Linux DRM,
VAAPI device discovery, and removal of torch install helpers.
"""

from pathlib import Path as RealPath
from unittest.mock import patch

import pytest

import utils.gpu_detector as gpu_detector
from utils.gpu_detector import (
    GPUInfo,
    clear_gpu_cache,
    encoder_backend_matrix,
    find_vaapi_device,
    get_gpu_info,
    has_vaapi,
    supported_encoder_backends,
)


@pytest.fixture(autouse=True)
def _reset_gpu_cache():
    clear_gpu_cache()
    yield
    clear_gpu_cache()


def _path_redirect(root: RealPath, virtual: str):
    """Path factory that maps `virtual` to `root`, otherwise uses real Path."""

    def factory(arg, *args, **kwargs):
        if str(arg) == virtual:
            return root
        return RealPath(arg, *args, **kwargs)

    return factory


class TestEncoderBackendMatrix:
    def test_matrix_documents_os_backends(self):
        matrix = encoder_backend_matrix()
        assert matrix["windows"] == ["nvenc", "amf", "qsv"]
        assert matrix["linux"] == ["nvenc", "vaapi", "qsv"]
        assert matrix["darwin"] == ["nvenc", "videotoolbox"]
        # Mutations of the returned copy must not alter the module constant.
        matrix["linux"].append("amf")
        assert "amf" not in encoder_backend_matrix()["linux"]

    @pytest.mark.parametrize(
        "system,expected",
        [
            ("Windows", ["nvenc", "amf", "qsv"]),
            ("windows", ["nvenc", "amf", "qsv"]),
            ("Linux", ["nvenc", "vaapi", "qsv"]),
            ("linux", ["nvenc", "vaapi", "qsv"]),
            ("Darwin", ["nvenc", "videotoolbox"]),
            ("darwin", ["nvenc", "videotoolbox"]),
            ("macOS", ["nvenc", "videotoolbox"]),
        ],
    )
    def test_supported_encoder_backends_per_os(self, system, expected):
        assert supported_encoder_backends(system) == expected

    def test_amf_not_listed_for_linux(self):
        assert "amf" not in supported_encoder_backends("linux")

    def test_vaapi_not_listed_for_windows(self):
        assert "vaapi" not in supported_encoder_backends("windows")


class TestIntelLinuxDetection:
    def test_detect_intel_reads_drm_vendor(self, tmp_path):
        card0 = tmp_path / "card0"
        card0.mkdir()
        (card0 / "device").mkdir()
        (card0 / "device" / "vendor").write_text("0x8086\n")
        (card0 / "device" / "device").write_text("0x9a49\n")
        # Connector dirs must be ignored.
        connector = tmp_path / "card0-DP-1"
        connector.mkdir()
        (connector / "device").mkdir()
        (connector / "device" / "vendor").write_text("0x8086\n")

        with patch.object(gpu_detector.platform, "system", return_value="Linux"):
            with patch(
                "utils.gpu_detector.Path",
                side_effect=_path_redirect(tmp_path, "/sys/class/drm"),
            ):
                gpus = gpu_detector._detect_intel()

        assert len(gpus) == 1
        assert gpus[0].vendor == "intel"
        assert "0x9a49" in gpus[0].model

    def test_detect_intel_skips_non_intel_vendor(self, tmp_path):
        card0 = tmp_path / "card0"
        card0.mkdir()
        (card0 / "device").mkdir()
        (card0 / "device" / "vendor").write_text("0x1002\n")  # AMD
        (card0 / "device" / "device").write_text("0x73bf\n")

        with patch.object(gpu_detector.platform, "system", return_value="Linux"):
            with patch(
                "utils.gpu_detector.Path",
                side_effect=_path_redirect(tmp_path, "/sys/class/drm"),
            ):
                assert gpu_detector._detect_intel() == []

    def test_detect_amd_linux_drm_still_works(self, tmp_path):
        card0 = tmp_path / "card0"
        card0.mkdir()
        (card0 / "device").mkdir()
        (card0 / "device" / "vendor").write_text("0x1002\n")
        (card0 / "device" / "device").write_text("0x73bf\n")

        with patch.object(gpu_detector.platform, "system", return_value="Linux"):
            with patch("utils.gpu_detector.subprocess.run", side_effect=FileNotFoundError):
                with patch(
                    "utils.gpu_detector.Path",
                    side_effect=_path_redirect(tmp_path, "/sys/class/drm"),
                ):
                    gpus = gpu_detector._detect_amd()

        assert len(gpus) == 1
        assert gpus[0].vendor == "amd"


class TestVaapiDevice:
    def test_find_vaapi_device_none_on_windows(self):
        with patch.object(gpu_detector.platform, "system", return_value="Windows"):
            assert find_vaapi_device() is None
            assert has_vaapi() is False

    def test_find_vaapi_device_prefers_render_node(self, tmp_path):
        dri = tmp_path / "dri"
        dri.mkdir()
        (dri / "card0").touch()
        (dri / "renderD128").touch()
        (dri / "renderD129").touch()

        with patch.object(gpu_detector.platform, "system", return_value="Linux"):
            with patch(
                "utils.gpu_detector.Path",
                side_effect=_path_redirect(dri, "/dev/dri"),
            ):
                device = find_vaapi_device()
        assert device == str(dri / "renderD128")


class TestGetGpuInfoCaching:
    def test_cache_avoids_repeated_detection(self):
        fake = [GPUInfo(vendor="nvidia", model="Test GPU")]
        with patch.object(gpu_detector, "_detect_nvidia", return_value=fake) as nvidia:
            with patch.object(gpu_detector, "_detect_amd", return_value=[]):
                with patch.object(gpu_detector, "_detect_apple_silicon", return_value=None):
                    with patch.object(gpu_detector, "_detect_intel", return_value=[]):
                        first = get_gpu_info()
                        second = get_gpu_info()
        assert first == second == fake
        assert nvidia.call_count == 1


class TestNoTorchHelpers:
    def test_torch_helpers_removed(self):
        assert not hasattr(gpu_detector, "recommend_torch_variant")
        assert not hasattr(gpu_detector, "get_torch_install_command")
