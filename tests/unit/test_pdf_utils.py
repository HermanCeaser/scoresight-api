import pytest
import fitz
import io
from app.core import pdf_utils

def test_split_pdf_to_pages(tmp_path):
    # Create a minimal PDF in memory
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    for _ in range(2):
        doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    # Test splitting
    pages = pdf_utils.split_pdf_to_pages(str(pdf_path))
    assert len(pages) == 2
    assert all(isinstance(p, bytes) for p in pages)

def test_encode_image_to_base64():
    # Create a dummy PNG bytes
    img_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    b64 = pdf_utils.encode_image_to_base64(img_bytes)
    assert isinstance(b64, str)
    assert len(b64) > 0

def test_get_question_numbers_from_json():
    entries = [
        {"questionNo": "45(a)"},
        {"questionNo": "46"},
        {"questionNo": "47(b)"},
    ]
    first, last = pdf_utils.get_question_numbers_from_json(entries)
    assert first == "46"
    assert last == "46"
