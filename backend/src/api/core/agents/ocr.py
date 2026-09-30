"""Document OCR via GLM 5.3 Flash — scanned PDFs and photos of documents into Markdown.

Why it exists: MarkItDown reads a PDF's TEXT LAYER. A scanned PDF (or a photo of a paper)
has none, so MarkItDown returns "" and the agent answers "I can't read the file". GLM 5.3 Flash
does not take PDFs inline (`supports_pdf_input=False`), but it reads images — so each page is
rendered to a JPEG and transcribed, one parallel request per page. No dedicated OCR provider
(decision 2026-09-30: the stack is OpenRouter GLM only). Generalized from optimuslar's
`services/documents/{ocr_service,page_render_service}.py`.

Decisions carried over:

* **Native text short-circuits the network — only on a page that is ACTUALLY digital.** Signed
  envelopes (e-notariado, ONR) stamp a real text layer (header, validation link) on top of a
  scan. Trusting `len(text) > N` alone returns the letterhead and silently drops the scan; a
  page must also be free of a large raster image to skip OCR.
* **JPEG, not PNG.** An A4 at 200 DPI is 2-4 MB as PNG; a fan-out of 8 pages would hold ~40 MB
  of base64 strings. JPEG q90 is ~10x smaller and loses nothing an OCR model can see.
* **Greedy decoding, reasoning off.** Transcription needs no thinking (it only adds latency and
  cost per page). At temperature 0 the failure mode is a degenerate LOOP, not hallucination —
  `_page_warnings` catches it and the page is retried once (a shared serverless endpoint
  batches requests, so even temperature 0 is not bit-reproducible).
* **One page failing never kills the document.** Each page catches its own errors; a task
  group cancels all siblings on one raise.
"""

import base64
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Final

import anyio
import cv2
import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from api.core.agents.custom_providers import init_model
from api.core.agents.llm import UsageContext
from api.core.agents.models import Models
from api.core.logging import get_logger

log = get_logger(__name__)

OCR_MODEL: Final = Models.OpenRouter.GLM_5_3_FLASH
OCR_PROMPT: Final = (
    "Transcribe this document page to markdown, verbatim, in reading order. "
    "Keep tables as markdown tables and preserve every number, symbol and accent exactly "
    "(e.g. `nº`, CPF/CNPJ, amounts, dates). Ignore margin noise, stamps and page furniture "
    "that is not body text. Do not translate, summarize or comment. Output only the "
    "transcription."
)
OCR_TEMPERATURE: Final = 0.0
# ~3k words of Markdown: far more than one dense page.
OCR_MAX_TOKENS: Final = 4096
OCR_CONCURRENCY_LIMIT: Final = 8
OCR_PAGE_TIMEOUT_SECONDS: Final = 60.0
OCR_TOTAL_TIMEOUT_SECONDS: Final = 180.0
OCR_PAGE_RETRIES: Final = 1
OCR_MAX_PAGES: Final = 20

RENDER_DPI: Final = 200
JPEG_QUALITY: Final = 90
# A phone photo (3000x4000) carries no more legible detail than this; matches the pixel height
# of an A4 rendered at 200 DPI.
MAX_IMAGE_SIDE_PIXELS: Final = 2400
# Below this the "text layer" is a watermark or a page number, not content.
NATIVE_TEXT_MIN_CHARS: Final = 200
# Fraction of the page covered by one raster image above which the page is a SCAN whatever its
# text layer says. Measured on a real signed registry: scanned bodies cover 0.48-0.54, a truly
# digital page peaks at 0.08 (seals/logos). 0.25 sits in the middle of the gap.
SCANNED_IMAGE_COVERAGE: Final = 0.25

PDF_MIME: Final = "application/pdf"
FINISH_REASON_LENGTH: Final = "length"
DEGENERATE_NGRAM_SIZE: Final = 5
DEGENERATE_NGRAM_MAX_REPEATS: Final = 3

WARNING_EMPTY: Final = "empty_output"
WARNING_TRUNCATED: Final = "hit_max_tokens"
WARNING_DEGENERATE_LOOP: Final = "degenerate_loop"
WARNING_PAGE_FAILED: Final = "page_failed"

# Chat models wrap a transcription in a ```markdown fence even when told not to.
CODE_FENCE_PATTERN: Final = re.compile(r"^```\w*\s*\n|\n```\s*$")
BLANK_LINES_PATTERN: Final = re.compile(r"\n{3,}")


@dataclass(slots=True)
class PageSource:
    """One page, resolved to either its native text OR a JPEG awaiting OCR."""

    index: int
    native_text: str = ""
    image_jpeg: bytes | None = None


@dataclass(slots=True)
class DocumentText:
    """Ordered Markdown of the whole document plus whatever went wrong reading it."""

    markdown: str
    page_count: int
    ocr_page_count: int
    warnings: list[str] = field(default_factory=list)


# ── Rendering (sync, CPU-bound: always called through anyio.to_thread) ────────────────────


def _encode_jpeg(image: np.ndarray) -> bytes:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest > MAX_IMAGE_SIDE_PIXELS:
        ratio = MAX_IMAGE_SIDE_PIXELS / longest
        image = cv2.resize(
            image, (int(width * ratio), int(height * ratio)), interpolation=cv2.INTER_AREA
        )
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise ValueError("could not encode page as JPEG")
    return buffer.tobytes()


def _max_image_coverage(page: pdfium.PdfPage) -> float:
    width, height = page.get_size()
    page_area = width * height
    if page_area <= 0:
        return 0.0
    coverage = 0.0
    for image_object in page.get_objects(filter=[pdfium_raw.FPDF_PAGEOBJ_IMAGE]):
        left, bottom, right, top = image_object.get_pos()
        coverage = max(coverage, abs((right - left) * (top - bottom)) / page_area)
    return coverage


def _render_pdf(raw: bytes) -> list[PageSource]:
    sources: list[PageSource] = []
    try:
        document = pdfium.PdfDocument(raw)
    except pdfium.PdfiumError as error:
        raise ValueError(f"invalid or password-protected PDF: {error}") from error
    try:
        page_count = len(document)
        if page_count > OCR_MAX_PAGES:
            log.warning("ocr_pages_truncated", total_pages=page_count)
        for index in range(min(page_count, OCR_MAX_PAGES)):
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    native_text = textpage.get_text_range().strip()
                finally:
                    textpage.close()
                is_scan = _max_image_coverage(page) >= SCANNED_IMAGE_COVERAGE
                if not is_scan and len(native_text) >= NATIVE_TEXT_MIN_CHARS:
                    sources.append(PageSource(index=index, native_text=native_text))
                    continue
                # pypdfium2 renders at 72 DPI * scale; RGB numpy (BGR for OpenCV) reuses
                # _encode_jpeg, which also enforces MAX_IMAGE_SIDE_PIXELS.
                bitmap = page.render(scale=RENDER_DPI / 72, rev_byteorder=False)
                sources.append(PageSource(index=index, image_jpeg=_encode_jpeg(bitmap.to_numpy())))
            finally:
                page.close()
    finally:
        document.close()
    return sources


def render_document(raw: bytes, mime_type: str) -> list[PageSource]:
    """PDF → one source per page; image → a single normalized JPEG page. Raises ValueError."""
    bare = mime_type.split(";")[0].strip().lower()
    if bare == PDF_MIME:
        return _render_pdf(raw)
    if bare.startswith("image/"):
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("could not decode image")
        return [PageSource(index=0, image_jpeg=_encode_jpeg(image))]
    raise ValueError(f"unsupported mime type for OCR: {mime_type}")


# ── OCR ───────────────────────────────────────────────────────────────────────────────────


def _normalize_markdown(text: str) -> str:
    """Strip a wrapping fence and compose accents. NFC, not NFKC: compatibility folding
    rewrites `nº 830` as `no 830`, and the text is shown back to the user."""
    unfenced = CODE_FENCE_PATTERN.sub("", text.strip())
    return BLANK_LINES_PATTERN.sub("\n\n", unicodedata.normalize("NFC", unfenced)).strip()


def _has_degenerate_loop(text: str) -> bool:
    """A 5-token n-gram repeated more than 3x is the greedy fixed-point signature. A low
    unique/total ratio is NOT used: legal/registry text is repetitive by nature."""
    tokens = text.split()
    if len(tokens) < DEGENERATE_NGRAM_SIZE * (DEGENERATE_NGRAM_MAX_REPEATS + 1):
        return False
    ngrams = Counter(
        tuple(tokens[i : i + DEGENERATE_NGRAM_SIZE])
        for i in range(len(tokens) - DEGENERATE_NGRAM_SIZE + 1)
    )
    return ngrams.most_common(1)[0][1] > DEGENERATE_NGRAM_MAX_REPEATS


def _page_warnings(markdown: str, finish_reason: str | None) -> list[str]:
    warnings: list[str] = []
    if not markdown:
        warnings.append(WARNING_EMPTY)
    if finish_reason == FINISH_REASON_LENGTH:
        warnings.append(WARNING_TRUNCATED)
    if _has_degenerate_loop(markdown):
        warnings.append(WARNING_DEGENERATE_LOOP)
    return warnings


async def _ocr_page(
    model: BaseChatModel,
    limiter: anyio.CapacityLimiter,
    source: PageSource,
    config: dict,
    prompt: str = OCR_PROMPT,
) -> tuple[str, list[str]]:
    encoded = base64.b64encode(source.image_jpeg or b"").decode("ascii")
    message = HumanMessage(
        content=[
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
            {"type": "text", "text": prompt},
        ]
    )
    markdown, finish_reason = "", None
    async with limiter:
        for attempt in range(OCR_PAGE_RETRIES + 1):
            try:
                with anyio.fail_after(OCR_PAGE_TIMEOUT_SECONDS):
                    reply = await model.ainvoke([message], config=config)
            except Exception as error:
                log.warning(
                    "ocr_page_failed", page=source.index, attempt=attempt, error=repr(error)
                )
                continue
            markdown = _normalize_markdown(reply.text or "")
            finish_reason = reply.response_metadata.get("finish_reason")
            if not _page_warnings(markdown, finish_reason):
                break
    if not markdown:
        return "", [WARNING_PAGE_FAILED]
    return markdown, _page_warnings(markdown, finish_reason)


async def ocr_document(
    raw: bytes,
    *,
    mime_type: str,
    usage: UsageContext | None,
    extra_instructions: str | None = None,
) -> DocumentText:
    """Render, OCR the non-digital pages in parallel, join back in reading order.

    `extra_instructions` is appended to the canonical `OCR_PROMPT` (never replacing it).
    WHY: apps add domain vocabulary (e.g. registry terms) without forking the prompt, so the
    module stays byte-identical to the template.

    Raises ValueError for unreadable/unsupported input; page-level failures become
    `warnings` (`page_N:<reason>`) instead. Each page is one billed call — pass `usage`.
    """
    sources = await anyio.to_thread.run_sync(render_document, raw, mime_type)
    extra = (extra_instructions or "").strip()
    prompt = f"{OCR_PROMPT} {extra}" if extra else OCR_PROMPT
    to_ocr = [source for source in sources if source.image_jpeg is not None]
    results: dict[int, tuple[str, list[str]]] = {}

    if to_ocr:
        model = init_model(
            OCR_MODEL,
            streaming=False,
            reasoning=False,
            reasoning_effort=None,
            temperature=OCR_TEMPERATURE,
            max_tokens=OCR_MAX_TOKENS,
        )
        limiter = anyio.CapacityLimiter(OCR_CONCURRENCY_LIMIT)
        config = usage.runnable_config() if usage else {}

        async def run(source: PageSource) -> None:
            results[source.index] = await _ocr_page(model, limiter, source, config, prompt)

        with anyio.move_on_after(OCR_TOTAL_TIMEOUT_SECONDS) as scope:
            async with anyio.create_task_group() as task_group:
                for source in to_ocr:
                    task_group.start_soon(run, source)
        if scope.cancel_called:
            log.warning("ocr_document_timeout", page_count=len(to_ocr))

    chunks: list[str] = []
    warnings: list[str] = []
    for source in sources:
        if source.image_jpeg is None:
            text, page_warnings = source.native_text, []
        else:
            text, page_warnings = results.get(source.index, ("", [WARNING_PAGE_FAILED]))
        warnings.extend(f"page_{source.index + 1}:{warning}" for warning in page_warnings)
        if text:
            chunks.append(f"## Página {source.index + 1}\n\n{text}")

    log.info(
        "ocr_document_done",
        page_count=len(sources),
        ocr_page_count=len(to_ocr),
        warning_count=len(warnings),
    )
    return DocumentText(
        markdown="\n\n".join(chunks),
        page_count=len(sources),
        ocr_page_count=len(to_ocr),
        warnings=warnings,
    )
