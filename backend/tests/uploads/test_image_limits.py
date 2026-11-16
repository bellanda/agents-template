"""Image pipeline guard rails (audit 2026-11-13).

- skills-backend-08: a tiny file that DECLARES a huge canvas is rejected from the header,
  before OpenCV allocates anything.
- core-performance-12: at most ``IMAGE_LIMITER`` AVIF re-encodes run at the same time.
- drift-backend-04: a transparent PNG keeps its alpha channel through the AVIF re-encode.
"""

from __future__ import annotations

import io
import struct
import threading
import time
import uuid

import anyio
import cv2
import numpy as np
import pytest
from starlette.datastructures import Headers, UploadFile

from api.core.exceptions import BadRequestError
from config import uploads
from config.uploads import (
    IMAGE_LIMITER,
    MAX_IMAGE_PIXELS,
    assert_pixel_budget,
    decode_image_bytes,
    flatten_alpha,
    org_dir,
    process_image_sync,
    save_upload,
)

GIANT_SIDE = 40_000


def _upload(content: bytes, filename: str = "photo.png", mime: str = "image/png") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content), filename=filename, headers=Headers({"content-type": mime})
    )


def _encode(ext: str, img: np.ndarray, params: list[int] | None = None) -> bytes:
    ok, buf = cv2.imencode(ext, img, params or [])
    assert ok
    return buf.tobytes()


def _giant_png() -> bytes:
    """A real 8x8 PNG whose IHDR claims 40000x40000 (CRC is wrong; the header check runs first)."""
    data = bytearray(_encode(".png", np.zeros((8, 8, 3), np.uint8)))
    data[16:24] = struct.pack(">II", GIANT_SIDE, GIANT_SIDE)
    return bytes(data)


def _giant_jpeg() -> bytes:
    data = bytearray(_encode(".jpg", np.zeros((8, 8, 3), np.uint8)))
    sof = data.index(b"\xff\xc0")
    data[sof + 5 : sof + 9] = struct.pack(">HH", GIANT_SIDE, GIANT_SIDE)
    return bytes(data)


@pytest.mark.parametrize(
    ("ext", "params"),
    [
        (".png", None),
        (".jpg", None),
        (".bmp", None),
        (".webp", [cv2.IMWRITE_WEBP_QUALITY, 80]),  # lossy VP8
        (".webp", [cv2.IMWRITE_WEBP_QUALITY, 101]),  # lossless VP8L
        (".avif", None),
    ],
)
def test_header_dimensions_match_real_encodes(ext: str, params: list[int] | None):
    img = np.random.default_rng(0).integers(0, 255, (24, 40, 3), dtype=np.uint8)
    assert uploads._header_dimensions(_encode(ext, img, params)) == (40, 24)


def test_giant_declared_png_and_jpeg_are_rejected_before_decode(monkeypatch: pytest.MonkeyPatch):
    def _boom(*_a, **_k):
        raise AssertionError("cv2.imdecode must not run for an oversized canvas")

    monkeypatch.setattr(uploads.cv2, "imdecode", _boom)
    for content in (_giant_png(), _giant_jpeg()):
        with pytest.raises(BadRequestError):
            decode_image_bytes(content)
        with pytest.raises(BadRequestError):
            process_image_sync(content, "hd", 10 * 1024 * 1024)


async def test_save_upload_rejects_giant_png_with_400():
    with pytest.raises(BadRequestError) as exc:
        await save_upload(_upload(_giant_png()), *org_dir(uuid.uuid4()), "px", mode="image")
    assert exc.value.status_code == 400


def test_pixel_budget_allows_the_cap_and_truncated_headers():
    side = int(MAX_IMAGE_PIXELS**0.5)
    ok = bytearray(_encode(".png", np.zeros((8, 8, 3), np.uint8)))
    ok[16:24] = struct.pack(">II", side, side)
    assert_pixel_budget(bytes(ok))
    assert_pixel_budget(b"\x89PNG\r\n\x1a\n\x00\x00")  # truncated: unknown, not an error


def test_transparent_png_keeps_alpha_through_avif():
    rgba = np.zeros((32, 32, 4), np.uint8)
    rgba[8:24, 8:24] = (10, 120, 200, 255)  # opaque square, transparent border
    avif, width, height = process_image_sync(_encode(".png", rgba), "original", 5 * 1024 * 1024)
    assert (width, height) == (32, 32)
    out = cv2.imdecode(np.frombuffer(avif, np.uint8), cv2.IMREAD_UNCHANGED)
    assert out.shape[2] == 4
    assert out[0, 0, 3] == 0
    assert out[16, 16, 3] == 255


def test_flatten_alpha_composites_over_white_and_ignores_bgr():
    rgba = np.zeros((2, 2, 4), np.uint8)
    rgba[0, 0] = (0, 0, 0, 0)
    rgba[1, 1] = (10, 20, 30, 255)
    flat = flatten_alpha(rgba)
    assert flat.shape == (2, 2, 3)
    assert tuple(flat[0, 0]) == (255, 255, 255)
    assert tuple(flat[1, 1]) == (10, 20, 30)
    bgr = np.zeros((2, 2, 3), np.uint8)
    assert flatten_alpha(bgr) is bgr


async def test_concurrent_uploads_never_exceed_the_image_limiter(monkeypatch: pytest.MonkeyPatch):
    running = 0
    peak = 0
    lock = threading.Lock()

    def _slow(content: bytes, _profile: str, _max: int) -> tuple[bytes, int, int]:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)
        with lock:
            running -= 1
        return content, 1, 1

    monkeypatch.setattr(uploads, "process_image_sync", _slow)
    org = uuid.uuid4()

    async def _one() -> None:
        await save_upload(_upload(b"x"), *org_dir(org), "limiter", mode="image")

    async with anyio.create_task_group() as tg:
        for _ in range(10):
            tg.start_soon(_one)

    assert 1 <= peak <= IMAGE_LIMITER.total_tokens
