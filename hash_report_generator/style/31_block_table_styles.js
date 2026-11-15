// Exact legacy values migrated from pdf_object_rules.py; no visual redesign.
module.exports = {
  "CENTRAL_BLOCK_TABLE_STYLES": {
    "legal_panel": {
      "box_width_pt": 0.35,
      "padding_commands": [
        "LEFTPADDING",
        "RIGHTPADDING",
        "TOPPADDING",
        "BOTTOMPADDING"
      ]
    },
    "title_separator": {
      "padding_commands": [
        "LEFTPADDING",
        "RIGHTPADDING",
        "TOPPADDING",
        "BOTTOMPADDING"
      ],
      "padding_pt": {
        "LEFTPADDING": 0,
        "RIGHTPADDING": 0,
        "TOPPADDING": 0,
        "BOTTOMPADDING": 0
      }
    }
  }
};
