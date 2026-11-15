/**
 * Report type module: single_pdf.
 *
 * One PDF, embedded byte-for-byte, with the full legal and checksum documentation.
 *
 * The module owns the ordered list of sections the type prints after its base
 * profile. Section ids resolve through js/lib/reports/sections.mjs, so every type
 * shows the same wording for the blocks it shares.
 */
export default Object.freeze({
  id: 'single_pdf',
  title: 'ChronoSeal SINGLE_PDF report',
  input_scope: 'single_file',
  version: 1,
  sections: Object.freeze([
    'timestamp_record',
    'source_pdf_evidence',
    'generation_note',
    'legal_documentation',
    'text_checksums',
  ]),
});