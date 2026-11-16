---
name: image-processing
description: OpenCV Headless image processing with AVIF output — decode, encode, resize, async thread pool integration. Use when handling image uploads, converting formats, resizing, or building any image pipeline in Python.
---

# Image Processing — OpenCV Headless + AVIF

Python image pipeline using OpenCV Headless for processing and AVIF for output. Covers format-agnostic decoding from bytes, AVIF encoding, resizing, and running sync OpenCV inside async handlers.

## Core Rules

- **Input:** Accept any format via `cv2.imdecode` from bytes (never file path), but through the fleet helper
  `decode_image_bytes` (`backend/config/uploads.py`, in all 7 repos): it calls `assert_pixel_budget(bytes)`
  FIRST, decodes with `IMREAD_UNCHANGED` (keeps the alpha channel: a transparent PNG logo became a black
  square with `IMREAD_COLOR`; decision 2026-11-13) and normalises 16-bit and grayscale to BGR/BGRA 8-bit.
- **Pixel budget:** `MAX_IMAGE_PIXELS = 50_000_000` (50 MP). `assert_pixel_budget` reads the declared
  dimensions from the header (PNG/JPEG) and rejects before allocating anything: a 40000x40000 file is a
  few KB on the wire and GBs in `imdecode` (worker OOM-killed). Formats the header parser does not cover
  (TIFF, GIF...) are bounded by `OPENCV_IO_MAX_IMAGE_PIXELS=50000000` in the backend `Dockerfile` `ENV`
  (all 7 have it). Never call `cv2.imdecode`/`Image.open` on user bytes without one of the two.
- **Alpha:** `decode_image_bytes` may return BGRA. Anything that cannot hold alpha (JPEG, PDF, OCR, a
  vision model) goes through `flatten_alpha(img)` first (white background by default). AVIF keeps alpha.
- **Output:** Always AVIF format (superior compression, wide browser support).
- **Async:** Wrap all sync OpenCV operations in `anyio.to_thread.run_sync(..., limiter=IMAGE_LIMITER)`.
  `IMAGE_LIMITER = anyio.CapacityLimiter(2)` (`config/uploads.py`) bounds concurrent decode/encode so a
  burst of uploads cannot hold N full-size bitmaps at once; `cv2.setNumThreads(1)` is set once in the same
  module (concurrency is the limiter's job, and OpenCV's own pool oversubscribes the CPU).

## Read by Content (Not Path)

```python
import cv2
import numpy as np

def decode_image_from_bytes(image_bytes: bytes) -> np.ndarray:
    """Decode image from raw bytes — works with any format."""
    np_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_UNCHANGED)  # in the fleet: use decode_image_bytes()
    if image is None:
        raise ValueError("Failed to decode image")
    return image
```

## Write by Extension (AVIF Default)

```python
AVIF_QUALITY = 50  # 0-100, lower = smaller file, 50 is good balance

def encode_image_to_avif(image: np.ndarray, quality: int = AVIF_QUALITY) -> bytes:
    """Encode image to AVIF bytes."""
    success, buffer = cv2.imencode(
        ".avif", image, [cv2.IMWRITE_AVIF_QUALITY, quality]
    )
    if not success:
        raise ValueError("Failed to encode image to AVIF")
    return buffer.tobytes()
```

## Common Operations

```python
# Resize maintaining aspect ratio
TARGET_MAX_DIMENSION = 1920

def resize_image_maintaining_aspect_ratio(
    image: np.ndarray,
    max_dimension: int = TARGET_MAX_DIMENSION,
) -> np.ndarray:
    height, width = image.shape[:2]
    if max(height, width) <= max_dimension:
        return image
    scale = max_dimension / max(height, width)
    new_width = int(width * scale)
    new_height = int(height * scale)
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

# Convert color space
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
```

## FastAPI Integration (Async)

```python
import anyio
from fastapi import UploadFile

async def process_uploaded_image(file: UploadFile) -> bytes:
    raw_bytes = await file.read()

    def _process() -> bytes:
        image = decode_image_from_bytes(raw_bytes)
        resized = resize_image_maintaining_aspect_ratio(image)
        return encode_image_to_avif(resized)

    return await anyio.to_thread.run_sync(_process, limiter=IMAGE_LIMITER)
```
