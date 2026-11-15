// Canonical semantic rules for the incremental migration.
module.exports = {
  "CENTRAL_LAYOUT": {
    "legal_qr": {"column_width_pt": 149, "image_horizontal_alignment": "CENTER", "image_width_pt": 135, "image_height_pt": 135, "box_alignment": "RIGHT", "panel_alignment": "LEFT"},
    "title": {"separator_height_pt": 2},
    "document_policy": {"file_size_unit": "bytes", "hash_display_case": "upper", "unicode_normalization": "NFC", "text_encoding": "UTF-8", "minimum_table_fragment_rows": 3, "minimum_widow_lines": 3, "minimum_orphan_lines": 3, "enforce_page_safe_area": true},
    "tables": {"default_padding_pt": 2.5, "header_bottom_padding_pt": 6, "explanatory_padding_pt": 3, "ots_padding_pt": 3}
  }
};
