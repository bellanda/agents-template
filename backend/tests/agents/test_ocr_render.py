"""`core/agents/ocr.py` page triage on REAL PDFs (pypdfium2, no LLM).

Regression (emporion prod 2026-11-04): every PDF that contained an image crashed the menu text
extraction with `AttributeError: 'PdfImage' object has no attribute 'get_pos'` — pypdfium2 5.x
renamed it `get_bounds`. The suites faked `ocr_document`, so `render_document` never met a PDF
with an image object.
"""

import io

import cv2
import numpy as np
import pypdfium2 as pdfium

from api.core.agents.ocr import render_document

PAGE_WIDTH_PT = 600
PAGE_HEIGHT_PT = 800
PHOTO_SIDE_PX = 64


def pdf_with_image(image_width_pt: float, image_height_pt: float) -> bytes:
    """One blank page with a JPEG image object of the given size (no text layer)."""
    ok, jpeg = cv2.imencode(".jpg", np.full((PHOTO_SIDE_PX, PHOTO_SIDE_PX, 3), 128, np.uint8))
    assert ok
    document = pdfium.PdfDocument.new()
    page = document.new_page(PAGE_WIDTH_PT, PAGE_HEIGHT_PT)
    image = pdfium.PdfImage.new(document)
    image.load_jpeg(io.BytesIO(jpeg.tobytes()), inline=True)
    image.set_matrix(pdfium.PdfMatrix().scale(image_width_pt, image_height_pt))
    page.insert_obj(image)
    page.gen_content()
    buffer = io.BytesIO()
    document.save(buffer)
    page.close()
    document.close()
    return buffer.getvalue()


def test_pdf_with_a_full_page_image_is_rendered_for_ocr_instead_of_crashing():
    sources = render_document(pdf_with_image(PAGE_WIDTH_PT, PAGE_HEIGHT_PT), "application/pdf")
    assert len(sources) == 1
    assert sources[0].image_jpeg is not None and sources[0].image_jpeg[:2] == b"\xff\xd8"


def test_pdf_with_a_small_image_and_no_text_still_goes_to_ocr():
    sources = render_document(pdf_with_image(50, 50), "application/pdf")
    assert len(sources) == 1 and sources[0].image_jpeg is not None
