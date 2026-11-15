// ChronoSeal declarative JS rules; evaluated in restricted VM.
module.exports = {
  "TABLE_PRESENTATION_VARIANTS": {
    "aligned_fields": {
      "vertical_alignment": "TOP",
      "left_padding_pt": 0,
      "right_padding_pt": 5,
      "top_padding_pt": 0,
      "bottom_padding_pt": 1
    },
    "combined": {
      "header_background": "#293e50",
      "header_text_color": "#ffffff",
      "vertical_alignment": "TOP",
      "header_alignment": "CENTER",
      "first_column_alignment": "CENTER",
      "body_backgrounds": ["#ffffff", "#f3f6f9"],
      "row_line_width_pt": 0.35,
      "row_line_color": "#d4dce4",
      "cell_padding_pt": 2.5,
      "header_bottom_padding_pt": 6
    }
  },
  "LEGAL_QR_TABLE_LAYOUT": {
    "qr_inner": {
      "vertical_alignment": "TOP",
      "horizontal_alignment": "CENTER",
      "padding_pt": 0
    },
    "outer": {
      "vertical_alignment": "TOP",
      "padding_pt": 0,
      "legal_text_right_padding_source": "BRIDGE_LAYOUT.legal_qr.cell_right_padding_pt"
    }
  },
  "GLOBAL_TABLE_PROFILE": {
    "reference": "FILE INFORMATION",
    "header_background": "#293F50",
    "header_text_color": "#FFFFFF",
    "stripe_background": "#F1F4F6",
    "body_background": "#FFFFFF",
    "body_text_color": "#1A2733",
    "cell_padding_pt": 2.5,
    "compact_padding_pt": 2.2,
    "compact_vertical_padding_pt": 1.6,
    "row_rule_pt": 0.25,
    "header_repeat_rows": 1,
    "hash_chunk_chars": 48,
    "shadow_clearance_pt": 8,
    "body_valign": "TOP",
    "body_align": "LEFT",
    "header_align": "CENTER",
    "header_font_role": "bold",
    "body_row_start": 1,
    "hash_wrap_mode": "character",
    "table_split_by_row": 1,
    "timestamp_valign": "TOP",
    "timestamp_compact_row_separator": true
  },
  "TABLE_RELIEF": {
    "frame_pt": 0.5,
    "edge_color": "#B4BAC1",
    "row_rule_color": "#D4DAE0",
    "shadow_color": "#000000",
    "shadow_offset_x_pt": 0.5,
    "shadow_offset_y_pt": -2.0,
    "shadow_blur_pt": 5.0,
    "shadow_layers": 10,
    "shadow_opacity": 0.55
  },
  "KEY_VALUE_BLOCK": {
    "padding_pt": 3.0,
    "compact_padding_pt": 2.2,
    "vertical_padding_pt": 1.6,
    "rule_pt": 0.2,
    "rule_color": "#d7dde5",
    "stripe_color": "#f8fafc"
  },
  "TABLE_COLUMN_ALIGNMENTS": {
    "combined": {"0": "CENTER", "3": "RIGHT", "4": "CENTER"}
  },
  "CHECKSUM_APPENDIX_TABLE": {
    "columns_source": "COLUMNS.hashes",
    "available_height_pt": 680
  },
  "TABLE": {
    "padding_pt": 2.5,
    "header_bottom_padding_pt": 6,
    "repeat_header": true,
    "split_by_row": true,
    "valign": "TOP",
    "alternate_rows": true,
    "header_contrast": true
  },
  "COLUMNS": {
    "combined": {
      "number": 0.045,
      "name": 0.245,
      "type": 0.095,
      "size": 0.09,
      "created": 0.145,
      "modified": 0.145,
      "hash": 0.235
    },
    "info": {
      "property": 0.3,
      "value": 0.7
    },
    "legal": {
      "law": 0.32,
      "meaning": 0.68
    },
    "technical": {
      "element": 0.28,
      "meaning": 0.72
    },
    "summary": {
      "proof": 0.3,
      "check": 0.35,
      "legal": 0.35
    },
    "certificate": {
      "property": 0.3,
      "value": 0.7
    },
    "timestamp": {
      "label": 0.31,
      "value": 0.69
    },
    "ots": {
      "file": 0.26,
      "size": 0.08,
      "type": 0.1,
      "modified": 0.22,
      "details": 0.34
    },
    "hashes": {
      "algorithm": 0.2,
      "digest": 0.8
    }
  },
  "KEY_VALUE": {
    "label_ratio": 0.29,
    "label_bold": true,
    "value_alignment": "LEFT",
    "preserve_colon": true
  },
  "SIZE_UNIT": "bytes"
};
