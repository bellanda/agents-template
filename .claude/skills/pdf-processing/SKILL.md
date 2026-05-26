---
name: pdf-processing
description: PDF structural surgery with pikepdf (merge, split, encrypt, metadata) and rendering/extraction with pypdfium2. Use when manipulating PDFs, extracting text, rasterizing pages to images, or handling PDF metadata.
---

# PDF Processing — pikepdf + pypdfium2

Two libraries, two jobs: `pikepdf` for structural operations (merge/split/encrypt/repair/metadata) and `pypdfium2` for rendering pages and extracting text/layout. Pick the tool based on whether you're reshaping PDF bytes or reading their content.

## pikepdf — Structural Surgery (MPL-2.0, qpdf-based)

Use for: merge, split, encrypt, compress, repair, metadata.

```python
import pikepdf

# Open and save
pdf = pikepdf.open("input.pdf")
pdf.save("output.pdf")

# Merge PDFs
merged = pikepdf.Pdf.new()
for path in pdf_paths:
    src = pikepdf.open(path)
    merged.pages.extend(src.pages)
merged.save("merged.pdf")

# Split — extract pages
pdf = pikepdf.open("input.pdf")
for i, page in enumerate(pdf.pages):
    dst = pikepdf.Pdf.new()
    dst.pages.append(page)
    dst.save(f"page_{i + 1}.pdf")

# Encrypt with password
pdf = pikepdf.open("input.pdf")
pdf.save(
    "encrypted.pdf",
    encryption=pikepdf.Encryption(owner="owner_pass", user="user_pass", R=6),
)

# Repair corrupted PDF
pdf = pikepdf.open("corrupted.pdf", allow_overwriting_input=True)
pdf.save("repaired.pdf")

# Read/write metadata
with pikepdf.open("input.pdf") as pdf:
    meta = pdf.open_metadata()
    with meta as m:
        m["dc:title"] = "New Title"
    pdf.save("output.pdf")
```

## pypdfium2 — Rendering & Text Extraction (Apache-2.0, PDFium/Chrome)

Use for: PDF→image rendering (high quality), text/layout extraction.

```python
import pypdfium2 as pdfium

# Render PDF pages to images
pdf = pdfium.PdfDocument("input.pdf")
for i in range(len(pdf)):
    page = pdf[i]
    # scale=4 → 4x DPI (288 DPI from default 72)
    bitmap = page.render(scale=4)
    pil_image = bitmap.to_pil()
    pil_image.save(f"page_{i + 1}.png")

# Extract text
pdf = pdfium.PdfDocument("input.pdf")
for i in range(len(pdf)):
    page = pdf[i]
    textpage = page.get_textpage()
    text = textpage.get_text_range()
    print(f"Page {i + 1}: {text[:200]}...")

# Render specific page range
pdf = pdfium.PdfDocument("input.pdf")
renderer = pdf.render(
    pdfium.PdfBitmap.to_pil,
    page_indices=range(0, 5),  # First 5 pages
    scale=3,
)
for i, image in zip(range(5), renderer):
    image.save(f"page_{i + 1}.png")
```

## Integration Notes

- **pikepdf** for structure, **pypdfium2** for pixels/text — never the reverse.
- Both are sync libraries. In async FastAPI, wrap with `anyio.to_thread.run_sync`.
- Output images in AVIF format when serving to frontend.
