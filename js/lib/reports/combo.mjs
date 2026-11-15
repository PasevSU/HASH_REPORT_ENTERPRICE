/**
 * Report type module: combo.
 *
 * Every selected file of one folder, with the full legal and checksum documentation.
 *
 * The module owns the ordered list of sections the type prints after its base
 * profile. Section ids resolve through js/lib/reports/sections.mjs, so every type
 * shows the same wording for the blocks it shares.
 */
export default Object.freeze({
  id: 'combo',
  title: 'ChronoSeal COMBO report',
  input_scope: 'current_folder',
  version: 1,
  sections: Object.freeze([
    'timestamp_record',
    'generation_note',
    'legal_documentation',
    'text_checksums',
  ]),
});