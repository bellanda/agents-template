"""`save_upload` size policy and streaming (2026-11-16: 500 MB per file, never held in RAM)."""

import io

import pytest
from starlette.datastructures import Headers, UploadFile

from api.core.exceptions import BadRequestError
from config import uploads
from config.api import api_config

MIB = 1024 * 1024


class ExplodingBody(io.BytesIO):
    def read(self, *args):
        raise AssertionError("body must not be read when the size is already over the limit")


class NoWholeReadBody(io.BytesIO):
    """Fails if anyone asks for the whole body at once (a streamed file is copied in chunks)."""

    def read(self, size=-1):
        if size is None or size < 0:
            raise AssertionError("a streamed file must not be read whole into memory")
        return super().read(size)


def make_file(content: io.BytesIO, name: str, mime: str) -> UploadFile:
    return UploadFile(file=content, filename=name, headers=Headers({"content-type": mime}))


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(api_config, "UPLOADS_DIR", tmp_path)
    return tmp_path


async def test_big_document_is_streamed_not_read_into_memory(uploads_dir):
    body = NoWholeReadBody(b"%PDF" + b"\0" * (17 * MIB))

    result = await uploads.save_upload(
        make_file(body, "laudo.pdf", "application/pdf"), "users", "1", mode="document"
    )

    stored = next(uploads_dir.rglob("*.pdf"))
    assert stored.stat().st_size == result.size_bytes == 4 + 17 * MIB


async def test_small_file_keeps_the_single_write_path(uploads_dir):
    result = await uploads.save_upload(
        make_file(io.BytesIO(b"abc"), "a.bin", "application/octet-stream"), "users", "1"
    )

    assert result.size_bytes == 3
    assert next(uploads_dir.rglob("*.bin")).read_bytes() == b"abc"


async def test_raw_default_cap_is_file_max_bytes_checked_before_reading(uploads_dir, monkeypatch):
    monkeypatch.setattr(api_config, "FILE_MAX_BYTES", 1024)
    body = ExplodingBody(b"x" * 2048)

    with pytest.raises(BadRequestError):
        await uploads.save_upload(make_file(body, "v.mp4", "video/mp4"), "users", "1")
