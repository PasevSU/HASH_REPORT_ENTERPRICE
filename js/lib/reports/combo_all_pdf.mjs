/**
 * Report type module: combo_all_pdf.
 *
 * Recursive selection, the folder breakdown, and one chosen PDF included
 * unchanged - its pages in the document and the file itself as a byte-for-byte
 * attachment - with the full legal and checksum documentation.
 *
 * The module owns the ordered list of sections the type prints after its base
 * profile. Section ids resolve through js/lib/reports/sections.mjs, so every type
 * shows the same wording for the blocks it shares.
 */
export default Object.freeze({
  id: 'combo_all_pdf',
  title: 'ChronoSeal COMBO_ALL_PDF report',
  input_scope: 'recursive_folder',
  version: 1,
  sections: Object.freeze([
    'timestamp_record',
    'source_pdf_evidence',
    'volume_breakdown',
    'generation_note',
    'legal_documentation',
    'text_checksums',
  ]),
});
