"""Presentation-only document policies. No changes to cryptographic bytes."""
import re
import unicodedata
from .style_runtime import layout_rule

def format_file_size(value):
    if layout_rule("document_policy", "file_size_unit") != "bytes":
        raise ValueError("Unsupported file size presentation unit")
    number = int(value)
    if number < 0:
        raise ValueError("Negative byte count")
    return f"{number:,} bytes".replace(",", " ")

def format_digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]+", value):
        raise ValueError("Digest must be a hexadecimal string")
    if layout_rule("document_policy", "hash_display_case") != "upper":
        raise ValueError("Unsupported hash presentation case")
    return value.upper()

def normalize_text(value):
    form = layout_rule("document_policy", "unicode_normalization")
    if form != "NFC" or layout_rule("document_policy", "text_encoding") != "UTF-8":
        raise ValueError("Unsupported text policy")
    return unicodedata.normalize(form, str(value))

def assert_table_fragment(row_count):
    required = int(layout_rule("document_policy", "minimum_table_fragment_rows"))
    if row_count < required:
        raise ValueError(f"Table fragment has {row_count} rows; minimum is {required}")
    return True
