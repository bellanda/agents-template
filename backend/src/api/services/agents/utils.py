import os
from typing import Optional

from markitdown import MarkItDown


def convert_file_to_text(file_path: str) -> Optional[str]:
    """
    Convert a file to text using Microsoft's MarkItDown.
    Returns the text content or None if conversion fails or library is missing.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    md = MarkItDown(enable_plugins=False)
    result = md.convert(file_path)
    return result.text_content
