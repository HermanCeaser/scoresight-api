import base64
import os
from typing import List, Tuple
import fitz  # PyMuPDF
from PIL import Image
import io


def split_pdf_to_pages(pdf_path: str, start_page: int = 1, stop_page: int = None) -> List[bytes]:
    """
    Split a PDF file into a list of page images (PNG bytes) from start_page to stop_page (1-based, inclusive).
    """
    doc = fitz.open(pdf_path)
    pages = []
    start_idx = start_page - 1
    stop_idx = stop_page if stop_page else len(doc)
    for page_num in range(start_idx, stop_idx):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        pages.append(pix.tobytes("png"))
    doc.close()
    return pages


def encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Encode image bytes to a base64 string.
    """
    return base64.b64encode(image_bytes).decode("utf-8")


def save_image(base64_image: str, output_dir: str, filename: str) -> None:
    """
    Save a base64 encoded image to a file.
    """
    os.makedirs(output_dir, exist_ok=True)
    image_path = os.path.join(output_dir, filename)
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(base64_image))


def save_page_image(
    base64_image: str, original_file_name: str, page_number: int, report_directory: str
) -> str:
    """
    Save the page image to a 'page_pictures' subdirectory within the report directory.
    Returns the path to the saved image.
    """
    output_folder = os.path.join(report_directory, "page_pictures")
    os.makedirs(output_folder, exist_ok=True)
    image_filename = f"{original_file_name}_page{page_number}.png"
    save_path = os.path.join(output_folder, image_filename)
    image_data = base64.b64decode(base64_image)
    image = Image.open(io.BytesIO(image_data))
    image.save(save_path)
    return save_path


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Return the number of pages in a PDF.
    """
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def get_question_numbers_from_json(entries: List[dict]) -> Tuple[str, str]:
    """
    Given a list of dicts with 'questionNo', return the first and last fully numeric question numbers.
    """
    import re
    first_question_number = "N/A"
    last_question_number = "N/A"
    question_numbers = []
    for item in entries:
        q_number = item.get("questionNo", "")
        q_number_cleaned = re.sub(r"\\(.*?\\)", "", q_number).strip()
        question_numbers.append(q_number_cleaned)
    numeric_question_numbers = [num for num in question_numbers if num.isdigit()]
    if numeric_question_numbers:
        first_question_number = numeric_question_numbers[0]
        last_question_number = numeric_question_numbers[-1]
    return first_question_number, last_question_number
