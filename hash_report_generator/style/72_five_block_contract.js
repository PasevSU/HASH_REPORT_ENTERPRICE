// Single semantic entry point for the five reference designs; presentation only.
// Original source: user-provided standard.pdf and five reference screenshots.
module.exports = {
  "REPORT_BLOCK_CONTRACT": {
    "title": {"source": "TITLE_HIERARCHY", "header_source": "LAYOUT_OBJECTS.report_title", "underline_source": "PAGE_IDENTITY"},
    "information": {"source": "INFORMATION_BLOCK_STYLE", "separator_color": "#E6E6FA", "wrap_values": true},
    "legal_basis": {"source": "LEGAL_CONTAINER", "qr_source": "LAYOUT_OBJECTS.qr_code", "two_column": true},
    "footer": {"source": "PAGE_IDENTITY", "line_within_page_margins": true},
    "table": {"source": "GLOBAL_TABLE_PROFILE", "relief_source": "TABLE_RELIEF", "header_white": true, "repeat_header": true, "wrap_long_hashes": true}
  }
};
