// Single source of presentation values for bridge PDF elements.
module.exports = {
  BRIDGE_LAYOUT: {
    legal_qr: {qr_size_mm: 26, qr_column_fraction: 0.19, qr_inner_column_fraction: 0.94,
      legal_font_pt: 8, legal_leading_pt: 10, caption_font_pt: 6, caption_leading_pt: 7.5,
      cell_right_padding_pt: 8},
    qr_fallback: {font_pt: 7, leading_pt: 9},
    header_identity: {font_pt: 11, leading_pt: 15, space_after_pt: 4, trailing_spacer_pt: 14},
    spacing: {
      legal_after_pt: 8,
      stop_details_after_pt: 8,
      processing_duration_after_pt: 14,
      attachments_intro_after_pt: 8,
      attachments_list_after_pt: 10
    },
    qr_cell_width_mm: 30,
    legal_table_widths_mm: [148, 32],
    qr_caption_text: "Gesetze-im-internet.de\n§ 371 ZPO\n§ 286 ZPO\nArt. 41 eIDAS",
    qr_target_url: "https://www.gesetze-im-internet.de/zpo/__371.html",
    paragraph_styles: {
      legal: {font_pt: 8, leading_pt: 10, color: "legal_text"},
      qr_caption: {font_pt: 6, leading_pt: 7.5, color: "qr_caption"},
      header_identity: {font_pt: 11, leading_pt: 15, space_after_pt: 4, color: "normal_text"},
      tsa_heading: {font_pt: 12, leading_pt: 16, space_before_pt: 6, space_after_pt: 4, color: "heading"},
      total_heading: {font_pt: 14, leading_pt: 18, space_before_pt: 14, space_after_pt: 10, color: "heading"},
      total_sub: {font_pt: 11, leading_pt: 15, space_before_pt: 8, space_after_pt: 5, color: "subheading"},
      attachments_heading: {font_pt: 12, leading_pt: 16, space_before_pt: 12, space_after_pt: 6, color: "heading"},
      attachment_item: {font_pt: 9, leading_pt: 12, space_after_pt: 2, color: "normal_text"},
      attachment_hash: {font_pt: 7, leading_pt: 9, space_after_pt: 8, left_indent_pt: 18, color: "hash_line", font: "Courier"},
      qr_fallback: {font_pt: 7, leading_pt: 9, color: "qr_fallback"}
    },
    colors: {legal_text: "#3a3a3a", normal_text: "#1a1a1a", heading: "#2c3e50", subheading: "#34495e", hash_line: "#444444", qr_caption: "#666666", qr_fallback: "#888888"}
  }
};
