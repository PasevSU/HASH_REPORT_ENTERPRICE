// Single source for the branded report header, legal panel and status colours.
// Every generator (SINGLE, COMBO, core, bridge) reads these through report_header.py.
module.exports = {
  "SECTION_HEADING": {
    "font_size_pt": 9.5,
    "leading_pt": 12,
    "color": "#18354D",
    "space_before_pt": 12,
    "space_after_pt": 4,
    "rule_pt": 0.6,
    "rule_color": "#B5C5D1",
    "rule_gap_pt": 2
  },
  "INFO_LINE": {
    "font_size_pt": 8.5,
    "leading_pt": 12,
    "label_color": "#18354D",
    "value_color": "#2B3A4A",
    "space_after_pt": 1
  },
  "REPORT_HEADER": {
    "eyebrow": "CRYPTO REPORT ENTERPRISE / TECHNISCHER PRÜFBERICHT",
    "title": "SHA-256 HASH REPORT",
    "subtitle": "Kryptographischer Existenznachweis",
    "title_color": "#18354D",
    "title_font_size_pt": 16,
    "title_leading_pt": 20,
    "title_alignment": 0,
    "header_text_color": "#18354D",
    "muted_color": "#60778A",
    "muted_font_size_pt": 8,
    "rule_height_pt": 2,
    "rule_color": "#18354D",
    "legal_text_color": "#34465A",
    "legal_background": "#F3F6F8",
    "legal_rule_pt": 0.6,
    "legal_rule_color": "#B5C5D1",
    "legal_text_right_padding_pt": 8,
    "legal_text_left_padding_pt": 0,
    "legal_text_vertical_padding_pt": 0,
    "qr_size_pt": 135,
    "qr_column_pt": 149,
    "qr_left_padding_pt": 4,
    "qr_file": "legal_full_text_qr.png",
    "qr_box_pt": 0.7,
    "qr_box_color": "#304255",
    "qr_divider_pt": 0.4,
    "qr_divider_color": "#AAB4BF",
    "qr_caption_background": "#F0F3F6",
    "qr_padding_pt": 5,
    "qr_caption_padding_pt": 4,
    "qr_caption": "<b>QR-Code</b> – Vollständige Rechtsgrundlagen<br/>und technische Referenzen",
    "legal_html": [
      "<b>Rechtliche und technische Hinweise für Deutschland</b>",
      "<b>Beweisrecht (§§ 286, 371, 371a, 130a ZPO):</b> Elektronische Dateien können als Beweismittel vorgelegt werden; das Gericht würdigt sie im Einzelfall. § 371a ZPO betrifft insbesondere qualifiziert elektronisch signierte private elektronische Dokumente; ein Zeitstempel allein erfüllt diese Voraussetzung nicht. Für Schriftsätze gelten außerdem die Form- und Übermittlungsanforderungen des § 130a ZPO.",
      "<b>eIDAS (Art. 25, 41, 42; EU 2024/1183):</b> Ein RFC-3161-Zeitstempel ist nicht automatisch qualifiziert und keine qualifizierte elektronische Signatur. Nur ein nachweislich qualifizierter elektronischer Zeitstempel genießt nach Art. 41 Abs. 2 die widerlegliche Vermutung für die Richtigkeit der angegebenen Zeit und die Integrität der gebundenen Daten. Er belegt für sich weder Urheberschaft noch Wahrheit des Inhalts und ersetzt weder eine erforderliche qualifizierte elektronische Signatur noch den sicheren Übermittlungsweg.",
      "<b>Technische Referenzen:</b> RFC 3161/5816; ETSI EN 319 421/422, 319 102-1, 319 122-1, 319 142-1; BSI TR-03125 und, soweit einschlägig, TR-03138. Die Nennung begründet keine Zertifizierung oder Konformität.",
      "<b>Prüfbarkeit und Grenzen:</b> Datei-Hashes, Aggregationsmethode, TSA-Token, ByteRange, CMS, Zertifikatskette, EKU, CRL/OCSP und DSS sind unabhängig zu prüfen. VERIFIED / FAILED / NOT VERIFIED bezeichnen den tatsächlichen Prüfstatus. Herkunft, Urheberschaft und inhaltliche Wahrheit werden nicht allein durch Hashwerte belegt. Dieser technische Bericht ist keine eidesstattliche Versicherung."
    ]
  },
  "BLOCK_TEXT": {
    "heading_font_size_pt": 10,
    "heading_leading_pt": 12,
    "heading_space_before_pt": 12,
    "heading_space_after_pt": 2,
    "heading_color": "#000000",
    "data_font_size_pt": 9,
    "data_leading_pt": 12,
    "data_color": "#000000"
  },
  "HASH_DISPLAY": {
    "uppercase": true
  },
  "STATUS_COLORS": {
    "ok": "#15803d",
    "error": "#8b0000",
    "warning": "#ea580c",
    "primary": "#2c3e50",
    "muted": "#888888"
  }
};
