import os
import subprocess
import sys
import textwrap

import pytest

from app.config import read_config
from app.main import create_app
from vision.types import ImageLimits


def test_default_config_matches_the_service_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PORT", "HOST", "MAX_UPLOAD_BYTES", "MAX_IMAGE_SIDE", "MAX_IMAGE_PIXELS"):
        monkeypatch.delenv(name, raising=False)

    config = read_config()

    assert config.port == 8000
    assert config.host == "0.0.0.0"
    assert config.max_upload_bytes == 20971520
    assert config.image_limits == ImageLimits(10000, 40000000)


def test_config_uses_explicit_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "PORT": "9000",
        "HOST": "127.0.0.1",
        "MAX_UPLOAD_BYTES": "1024",
        "MAX_IMAGE_SIDE": "100",
        "MAX_IMAGE_PIXELS": "10000",
    }.items():
        monkeypatch.setenv(name, value)

    config = read_config()

    assert (config.port, config.host, config.max_upload_bytes) == (9000, "127.0.0.1", 1024)
    assert config.image_limits == ImageLimits(100, 10000)
    assert os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] == "10000"


@pytest.mark.parametrize("name", ["PORT", "MAX_UPLOAD_BYTES", "MAX_IMAGE_SIDE", "MAX_IMAGE_PIXELS"])
@pytest.mark.parametrize("value", ["", "wrong", "0", "-1", "1.5"])
def test_invalid_integer_configuration_stops_startup_and_names_the_variable(
    name: str, value: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(SystemExit) as caught:
        create_app()

    assert caught.value.code == 1
    assert name in capsys.readouterr().out


@pytest.mark.parametrize("name, value", [("PORT", "65536"), ("HOST", ""), ("HOST", "   ")])
def test_invalid_host_or_port_stops_startup(
    name: str, value: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(SystemExit):
        create_app()

    assert name in capsys.readouterr().out


def test_fresh_service_configures_opencv_before_native_import() -> None:
    environment = os.environ.copy()
    environment.update(MAX_IMAGE_PIXELS="4", MAX_IMAGE_SIDE="100", MAX_UPLOAD_BYTES="1000")
    code = textwrap.dedent("""
        from app.main import app
        import cv2
        import numpy as np
        from vision.decode import decode, InvalidImageError
        from vision.types import ImageLimits

        success, encoded = cv2.imencode('.png', np.full((3, 3, 3), 255, dtype=np.uint8))
        assert success
        try:
            decode(encoded.tobytes(), ImageLimits(100, 100))
        except InvalidImageError as error:
            assert isinstance(error.__cause__, cv2.error)
            assert 'CV_IO_MAX_IMAGE_PIXELS' in str(error.__cause__)
        else:
            raise AssertionError('OpenCV did not apply its startup pixel limit')
    """)

    result = subprocess.run(
        [sys.executable, "-c", code], env=environment, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stdout + result.stderr
