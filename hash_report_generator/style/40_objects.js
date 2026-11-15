// ChronoSeal declarative JS rules; evaluated in restricted VM.
module.exports = {
  "OBJECTS": {
    "page": {
      "keep_footer_separate": true,
      "allow_overflow": false
    },
    "header": {
      "repeat": true,
      "align": "left"
    },
    "footer": {
      "repeat": true,
      "align": "right",
      "include_page_numbers": true
    },
    "title": {
      "keep_with_next": true
    },
    "heading": {
      "keep_with_next": true
    },
    "section_heading": {
      "uppercase": true,
      "bold": true,
      "keep_with_next": true,
      "preserve_colon": true
    },
    "paragraph": {
      "widows": 3,
      "orphans": 3
    },
    "legal_text": {
      "widows": 3,
      "orphans": 3,
      "container_background": "#f1f2f4",
      "padding_pt": 7
    },
    "table": {
      "repeat_header": true,
      "split_by_row": true
    },
    "table_header": {
      "white_text": true
    },
    "table_cell": {
      "wrap": true
    },
    "table_number": {
      "no_wrap": true
    },
    "table_filename": {
      "wrap": true
    },
    "table_type": {
      "wrap": true
    },
    "table_size": {
      "unit": "bytes",
      "unit_in_heading": true
    },
    "table_date": {
      "split_date_time_only": true
    },
    "hash": {
      "preserve_all_characters": true,
      "monospace": true
    },
    "timestamp": {
      "keep_label_value_together": true
    },
    "certificate": {
      "keep_label_value_together": true
    },
    "signature": {
      "never_rewrite_signed_pdf": true
    },
    "qr": {
      "keep_aspect_ratio": true
    },
    "image": {
      "keep_aspect_ratio": true
    },
    "link": {
      "allow_wrap": true
    },
    "list": {
      "keep_marker_with_text": true
    },
    "divider": {
      "width": "content"
    },
    "spacer": {
      "collapse_at_page_start": true
    },
    "page_break": {
      "only_explicit_sections": true
    },
    "attachment": {
      "never_modify_bytes": true
    },
    "volume": {
      "wrap_paths": true
    },
    "user_information": {
      "wrap": true
    },
    "system_information": {
      "wrap": true
    },
    "page_hashes": {
      "exclude_footer": true
    }
  }
};
