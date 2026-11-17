// Closing verification block: QR code plus the pointer to the electronic documents.
// Every value here is geometry or typography for that block only; the colours are
// resolved by name from COLORS so no second palette exists.
module.exports = {
  "VERIFICATION_QR": {
    "qr_size_mm": 30,
    "qr_column_width_pt": 104,
    "qr_cell_padding_pt": 8,
    "block_border_pt": 0.5,
    "block_padding_pt": 8,
    "space_before_pt": 14,
    "space_after_pt": 6,
    "heading_font_size_pt": 11,
    "heading_leading_pt": 14,
    "body_font_size_pt": 8,
    "body_leading_pt": 10.5,
    "caption_font_size_pt": 6.5,
    "caption_leading_pt": 8.5,
    "colors": {
      "heading": "accent",
      "body": "ink",
      "caption": "muted",
      "border": "grid",
      "background": "paper"
    }
  }
};
