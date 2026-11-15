// Central presentation policy for information BLOCKS, not data TABLES.
// RGB(230,230,250) is the user-specified border and separator colour.
module.exports = {
  "INFORMATION_BLOCK_STYLE": {
    "background": "#FFFFFF",
    "border_color": "#E6E6FA",
    "separator_color": "#E6E6FA",
    "border_left_pt": 1.0,
    "border_bottom_pt": 1.0,
    "padding_left_pt": 6.0,
    "padding_right_pt": 6.0,
    "padding_top_pt": 5.0,
    "padding_bottom_pt": 6.0,
    "gap_before_pt": 12.0,
    "gap_after_pt": 16.0,
    "line_gap_pt": 2.0,
    "label_column_ratio": 0.30,
    "value_wrap": true,
    "split_by_row": 1,
    "volume_table_alignment": "LEFT",
    "volume_row_geometry": {
      "top_padding_pt": 0.0,
      "bottom_padding_pt": 0.0,
      "first_row_top_padding_pt": 0.0,
      "last_row_bottom_padding_pt": 0.0,
      "line_gap_pt": 0.0,
      "horizontal_padding_pt": 0.0
    },
    "volume_typography": {
      "font_size_pt": 10.0,
      "leading_pt": 12.0,
      "font_regular": "Helvetica",
      "font_bold": "Helvetica-Bold",
      "space_before_pt": 0.0,
      "space_after_pt": 0.0,
      "label_bold": true,
      "heading_bold": true,
      "heading_uppercase": true
    }
  }
};
