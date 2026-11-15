/**
 * Report type module: file_information_report.
 *
 * Single file facts only; the legal documentation is not reprinted for a short report.
 *
 * The module owns the ordered list of sections the type prints after its base
 * profile. Section ids resolve through js/lib/reports/sections.mjs, so every type
 * shows the same wording for the blocks it shares.
 */
export default Object.freeze({
  id: 'file_information_report',
  title: 'ChronoSeal FILE INFORMATION report',
  input_scope: 'single_file',
  version: 1,
  sections: Object.freeze([
    'timestamp_record',
    'generation_note',
    'text_checksums',
  ]),
});