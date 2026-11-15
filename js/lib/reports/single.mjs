/**
 * Report type module: single.
 *
 * One file, hashed and documented, with the full legal and checksum documentation.
 *
 * The module owns the ordered list of sections the type prints after its base
 * profile. Section ids resolve through js/lib/reports/sections.mjs, so every type
 * shows the same wording for the blocks it shares.
 */
export default Object.freeze({
  id: 'single',
  title: 'ChronoSeal SINGLE report',
  input_scope: 'single_file',
  version: 1,
  sections: Object.freeze([
    'timestamp_record',
    'generation_note',
    'legal_documentation',
    'text_checksums',
  ]),
});