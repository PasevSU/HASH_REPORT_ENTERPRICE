/**
 * Report type module: combo_all.
 *
 * Recursive selection with the folder breakdown, the full legal and checksum documentation.
 *
 * The module owns the ordered list of sections the type prints after its base
 * profile. Section ids resolve through js/lib/reports/sections.mjs, so every type
 * shows the same wording for the blocks it shares.
 */
export default Object.freeze({
  id: 'combo_all',
  title: 'ChronoSeal COMBO_ALL report',
  input_scope: 'recursive_folder',
  version: 1,
  sections: Object.freeze([
    'timestamp_record',
    'volume_breakdown',
    'generation_note',
    'legal_documentation',
    'text_checksums',
  ]),
});