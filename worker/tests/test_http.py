import inspect
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.main import create_app
from vision import pipeline
from vision.types import Box, Detection, DetectionResult


def png(image: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def assert_error(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["message"]


@pytest.mark.parametrize(
    "content_type", [None, "text/plain", "image/gif", "image/png; charset=utf-8"]
)
def test_unsupported_content_type_is_rejected_without_reading_the_body(
    content_type: str | None, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unread_body(request: Request) -> AsyncIterator[bytes]:
        pytest.fail("An unsupported body must not be read")
        yield b""

    monkeypatch.setattr(Request, "stream", unread_body)
    headers = {"Content-Type": content_type} if content_type else {}

    assert_error(
        client.post("/v1/detect", content=b"unused", headers=headers), 415, "unsupported_media_type"
    )


def test_upload_stops_reading_at_the_first_chunk_over_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "4")
    client = TestClient(create_app())
    consumed = []

    async def chunks(request: Request) -> AsyncIterator[bytes]:
        consumed.append(1)
        yield b"1234"
        consumed.append(2)
        yield b"5"
        pytest.fail("The body must stop after the first chunk over the limit")

    monkeypatch.setattr(Request, "stream", chunks)
    response = client.post("/v1/detect", content=b"unused", headers={"Content-Type": "image/png"})

    assert_error(response, 413, "file_too_large")
    assert consumed == [1, 2]


def test_exact_upload_limit_is_accepted_and_configuration_is_not_reread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = png(np.full((1, 1, 3), 255, dtype=np.uint8))
    monkeypatch.setenv("MAX_UPLOAD_BYTES", str(len(data)))
    client = TestClient(create_app())
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1")

    assert (
        client.post("/v1/detect", content=data, headers={"Content-Type": "image/png"}).status_code
        == 200
    )


@pytest.mark.parametrize("data", [b"", b"corrupt", b"\x89PNG\r\n\x1a\n"])
def test_empty_corrupt_and_truncated_images_return_invalid_image(
    data: bytes, client: TestClient
) -> None:
    assert_error(
        client.post("/v1/detect", content=data, headers={"Content-Type": "image/png"}),
        422,
        "invalid_image",
    )


def test_twelve_thousand_pixel_side_returns_invalid_image(client: TestClient) -> None:
    data = png(np.full((1, 12000, 3), 255, dtype=np.uint8))
    assert_error(
        client.post("/v1/detect", content=data, headers={"Content-Type": "image/png"}),
        422,
        "invalid_image",
    )


def test_pixel_limit_is_enforced_independently_of_the_side_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_IMAGE_PIXELS", "100")
    client = TestClient(create_app())
    data = png(np.full((11, 10, 3), 255, dtype=np.uint8))

    assert_error(
        client.post("/v1/detect", content=data, headers={"Content-Type": "image/png"}),
        422,
        "invalid_image",
    )


@pytest.mark.parametrize("brightness, side", [(255, 80), (0, 80), (255, 1)])
def test_blank_black_and_single_pixel_images_return_empty_boxes(
    brightness: int, side: int, client: TestClient
) -> None:
    data = png(np.full((side, side, 3), brightness, dtype=np.uint8))
    response = client.post("/v1/detect", content=data, headers={"Content-Type": "image/png"})

    assert response.status_code == 200
    assert response.json()["boxes"] == []
    assert response.json()["image"] == {"width": side, "height": side}


@pytest.mark.parametrize("kind", ["bgr", "greyscale", "sixteen_bit", "transparent"])
def test_single_checkbox_is_detected_after_png_conversion(kind: str, client: TestClient) -> None:
    plane = np.full((80, 80), 255, dtype=np.uint8)
    cv2.rectangle(plane, (20, 20), (49, 49), 0, 1)
    if kind == "bgr":
        image = np.repeat(plane[:, :, None], 3, axis=2)
    elif kind == "greyscale":
        image = plane
    elif kind == "sixteen_bit":
        image = plane.astype(np.uint16) * 257
    else:
        image = np.zeros((80, 80, 4), dtype=np.uint8)
        image[:, :, 3] = np.where(plane == 0, 255, 0)

    response = client.post("/v1/detect", content=png(image), headers={"Content-Type": "image/png"})

    assert response.status_code == 200
    assert response.json()["boxes"] == [
        {"bbox": [20, 20, 50, 50], "is_checked": False, "fill_ratio": 0.0}
    ]


def test_unexpected_failure_returns_generic_error_and_logs_one_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(image: np.ndarray, params: object) -> DetectionResult:
        raise RuntimeError("private-worker-path")

    monkeypatch.setattr(pipeline, "detect", fail)
    client = TestClient(create_app())
    data = png(np.full((1, 1, 3), 255, dtype=np.uint8))
    response = client.post(
        "/v1/detect",
        content=data,
        headers={"Content-Type": "image/png", "X-Request-Id": "failure-1"},
    )

    assert_error(response, 500, "internal_error")
    assert "private-worker-path" not in response.text
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    events = [event for event in events if event["message"] == "detect request"]
    assert len(events) == 1
    assert events[0]["request_id"] == "failure-1"
    assert events[0]["status"] == 500
    assert "RuntimeError: private-worker-path" in events[0]["exception"]


def test_sample_jpeg_returns_exact_internal_response_shape(client: TestClient) -> None:
    data = (Path(__file__).resolve().parents[2] / "samples" / "sample2.jpg").read_bytes()
    response = client.post("/v1/detect", content=data, headers={"Content-Type": "image/jpeg"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert set(body) == {"image", "boxes", "timings_ms"}
    assert body["image"] == {"width": 1586, "height": 846}
    assert len(body["boxes"]) == 41
    coordinates = []
    for item in body["boxes"]:
        assert set(item) == {"bbox", "is_checked", "fill_ratio"}
        assert len(item["bbox"]) == 4
        assert all(type(value) is int for value in item["bbox"])
        x1, y1, x2, y2 = item["bbox"]
        assert 0 <= x1 < x2 <= 1586
        assert 0 <= y1 < y2 <= 846
        assert type(item["is_checked"]) is bool
        assert isinstance(item["fill_ratio"], float)
        assert 0 <= item["fill_ratio"] <= 1
        assert item["fill_ratio"] == round(item["fill_ratio"], 3)
        coordinates.append((y1, x1))
    assert coordinates == sorted(coordinates)
    assert set(body["timings_ms"]) == {"decode", "detect", "classify"}
    for value in body["timings_ms"].values():
        assert isinstance(value, float)
        assert value >= 0
        assert value == round(value, 1)


@pytest.mark.parametrize("filename", ["sample1.png", "sample2.jpg", "sample3.png", "sample4.png"])
def test_same_http_bytes_produce_byte_identical_boxes(filename: str, client: TestClient) -> None:
    data = (Path(__file__).resolve().parents[2] / "samples" / filename).read_bytes()
    content_type = "image/jpeg" if filename.endswith(".jpg") else "image/png"
    first = client.post("/v1/detect", content=data, headers={"Content-Type": content_type})
    second = client.post("/v1/detect", content=data, headers={"Content-Type": content_type})

    assert first.status_code == second.status_code == 200
    assert (
        first.content.split(b'"boxes":')[1].split(b',"timings_ms":')[0]
        == (second.content.split(b'"boxes":')[1].split(b',"timings_ms":')[0])
    )


def test_success_logs_one_request_with_sizes_counts_and_stage_timings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = TestClient(create_app())
    data = png(np.full((7, 9, 3), 255, dtype=np.uint8))
    response = client.post(
        "/v1/detect",
        content=data,
        headers={"Content-Type": "image/png", "X-Request-Id": "success-1"},
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    events = [event for event in events if event["message"] == "detect request"]

    assert len(events) == 1
    event = events[0]
    assert event["request_id"] == "success-1"
    assert event["status"] == 200
    assert event["bytes"] == len(data)
    assert (event["width"], event["height"], event["boxes"]) == (9, 7, 0)
    assert set(event["timings_ms"]) == {"decode", "ink", "candidates", "sizing", "classify"}
    assert event["duration_ms"] >= 0
    assert "exception" not in event


def test_detection_handler_is_synchronous(client: TestClient) -> None:
    route = next(route for route in client.app.routes if route.path == "/v1/detect")

    assert not inspect.iscoroutinefunction(route.endpoint)


def test_response_rounds_fill_ratio_and_aggregates_stage_timings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = DetectionResult(
        30,
        30,
        (Detection(Box(0, 0, 30, 30), True, 0.123456),),
        {"ink": 1.11, "candidates": 2.22, "sizing": 3.33, "classify": 4.44},
    )
    monkeypatch.setattr(pipeline, "detect", lambda image, params: result)
    client = TestClient(create_app())
    response = client.post(
        "/v1/detect",
        content=png(np.full((30, 30, 3), 255, dtype=np.uint8)),
        headers={"Content-Type": "image/png"},
    )

    assert response.status_code == 200
    assert response.json()["boxes"][0]["fill_ratio"] == 0.123
    assert response.json()["timings_ms"]["detect"] == 6.7
    assert response.json()["timings_ms"]["classify"] == 4.4
