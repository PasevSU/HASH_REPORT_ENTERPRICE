// ChronoSeal declarative JS rules; evaluated in restricted VM.
module.exports = {
  "PAGINATION": {
    "paper": "A4",
    "minimum_margins_mm": {
      "left": 20,
      "right": 20,
      "top": 20,
      "bottom": 35
    },
    "footer_separation_mm": 15,
    "no_orphan_section_headings": true,
    "minimum_orphan_lines": 3,
    "minimum_widow_lines": 3,
    "short_tables_keep_together": true,
    "table_headers_repeat": true,
    "long_tables_split_between_rows": true,
    "stretch_tables_to_fill_page": false,
    "report_qa_requires_rendering": true,
    "short_table_max_rows": 8,
    "section_break_strategy": "measure_flowables",
    "heading_first_paragraph_keep_together": true
  }
};
