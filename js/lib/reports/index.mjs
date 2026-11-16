/**
 * Registry of per-type report modules.
 *
 * Every report type the clone can produce has one module of its own: the module
 * declares the sections printed after the declarative base profile, so a type's
 * full content (system information, evidence table, timestamp record, generation
 * note, legal documentation, checksum appendix) is defined in one file instead
 * of being switched inside one shared renderer.
 */
import single from './single.mjs';
import singlePdf from './single_pdf.mjs';
import combo from './combo.mjs';
import comboAll from './combo_all.mjs';
import comboPdf from './combo_pdf.mjs';
import comboAllPdf from './combo_all_pdf.mjs';
import volume from './volume.mjs';
import fileInformation from './file_information_report.mjs';
import { getSection, sectionIds } from './sections.mjs';

const MODULES = [single, singlePdf, combo, comboAll, comboPdf, comboAllPdf, volume, fileInformation];

export const REPORT_MODULES = new Map(MODULES.map((module) => [module.id, module]));

/** Module for a profile id, or null when the profile has no dedicated module. */
export function loadReportModule(id) {
  return REPORT_MODULES.get(String(id || '')) || null;
}

export function reportModuleIds() {
  return [...REPORT_MODULES.keys()];
}

export function listReportModules() {
  return [...REPORT_MODULES.values()];
}

/**
 * Render a module's extra sections onto a layout.
 *
 * @returns {string[]} the section ids that were rendered, in order
 */
export function renderReportSections(module, layout, context) {
  const rendered = [];
  if (!module) return rendered;
  for (const id of module.sections || []) {
    getSection(id).build(layout, context);
    rendered.push(id);
  }
  return rendered;
}

export { sectionIds };