"""
OCR / document extraction for curriculum ingest.

PDF text is extracted with pypdf. Image OCR uses pytesseract only if the
Tesseract binary is installed — otherwise a clear error is returned.
"""

from io import BytesIO


def extract_from_bytes(data: bytes, filename: str = "", content_type: str = "") -> dict:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    is_pdf = name.endswith(".pdf") or "pdf" in ctype
    is_image = (
        name.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"))
        or ctype.startswith("image/")
    )
    is_text_plain = (
        name.endswith((".txt", ".md", ".csv"))
        or ctype.startswith("text/")
        or "text/plain" in ctype
        or "text/markdown" in ctype
    )

    if is_text_plain:
        text = data.decode("utf-8", errors="ignore").strip()
        if not text:
            return {
                "ok": False,
                "text": "",
                "engine": "text",
                "warning": "Uploaded text file was empty. Try a document with readable content.",
            }
        return {"ok": True, "text": clean_text(text), "engine": "text", "warning": None}

    if is_pdf:
        try:
            from pypdf import PdfReader
        except ImportError:
            return {
                "ok": False,
                "text": "",
                "engine": "none",
                "warning": "pypdf is not installed. Run: pip install pypdf",
            }
        try:
            reader = PdfReader(BytesIO(data))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            text = "\n\n".join(pages).strip()
            if not text:
                return {
                    "ok": False,
                    "text": "",
                    "engine": "pypdf",
                    "warning": "PDF had no extractable text. Try a scanned-page image with OCR, or a text PDF.",
                }
            return {"ok": True, "text": text, "engine": "pypdf", "warning": None}
        except Exception as exc:
            return {
                "ok": False,
                "text": "",
                "engine": "pypdf",
                "warning": f"PDF parsing failed ({exc.__class__.__name__}). Retry with another file.",
            }

    if is_image:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return {
                "ok": False,
                "text": "",
                "engine": "none",
                "warning": "Image OCR needs Pillow + pytesseract and a Tesseract install. Upload a text PDF instead.",
            }
        try:
            image = Image.open(BytesIO(data))
            text = pytesseract.image_to_string(image) or ""
            text = text.strip()
            if not text:
                return {
                    "ok": False,
                    "text": "",
                    "engine": "tesseract",
                    "warning": "OCR returned no text. Try a clearer image or a PDF.",
                }
            return {"ok": True, "text": text, "engine": "tesseract", "warning": None}
        except Exception as exc:
            return {
                "ok": False,
                "text": "",
                "engine": "tesseract",
                "warning": f"OCR failed ({exc.__class__.__name__}). Retry or upload a PDF.",
            }

    return {
        "ok": False,
        "text": "",
        "engine": "none",
        "warning": "Unsupported file type. Upload a PDF or an image (png/jpg).",
    }


def clean_text(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    keep = []
    for ln in lines:
        if not ln:
            if keep and keep[-1] != "":
                keep.append("")
            continue
        keep.append(ln)
    return "\n".join(keep).strip()


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        piece = words[i : i + chunk_size]
        chunks.append(" ".join(piece))
        i += max(chunk_size - overlap, 1)
    return chunks
