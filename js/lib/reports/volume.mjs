/**
 * Report type module: volume.
 *
 * Volume oriented report: where the bytes live, per folder, plus the full documentation.
 *
 * The module owns the ordered list of sections the type prints after its base
 * profile. Section ids resolve through js/lib/reports/sections.mjs, so every type
 * shows the same wording for the blocks it shares.
 */
export default Object.freeze({
  id: 'volume',
  title: 'ChronoSeal VOLUME report',
  input_scope: 'recursive_folder',
  version: 1,
  sections: Object.freeze([
    'volume_breakdown',
    'generation_note',
    'legal_documentation',
    'text_checksums',
  ]),
});