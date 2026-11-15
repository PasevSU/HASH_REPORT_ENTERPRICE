/**
 * JavaScript port of chronoseal/unified_report_profile.py - the shared, versioned
 * visual policy that the audit enforces for manual and automation reports.
 */
export const PROFILE_FIELDS = Object.freeze([
  'name', 'version', 'page_width_mm', 'page_height_mm', 'left_mm', 'right_mm',
  'top_mm', 'bottom_mm', 'footer_band_mm', 'appendix_top_mm', 'min_body_words',
]);

export const DEFAULT_PROFILE = Object.freeze({
  name: 'ChronoSeal Unified A4',
  version: '1.0-dev',
  page_width_mm: 210,
  page_height_mm: 297,
  left_mm: 20,
  right_mm: 20,
  top_mm: 20,
  bottom_mm: 20,
  footer_band_mm: 23,
  appendix_top_mm: 10,
  min_body_words: 12,
});

const NUMERIC_FIELDS = Object.freeze(PROFILE_FIELDS.filter((field) => field.endsWith('_mm') || field === 'min_body_words'));

/**
 * Python cannot construct a partial dataclass, so a malformed profile object has
 * no reference behaviour; rejecting it loudly is the only safe port.
 */
export function assertProfile(profile) {
  if (!profile || typeof profile !== 'object') throw new TypeError('Report profile must be an object');
  const missing = PROFILE_FIELDS.filter((field) => !Object.hasOwn(profile, field));
  if (missing.length) throw new TypeError('Report profile is missing: ' + missing.join(', '));
  for (const field of ['name', 'version']) {
    if (typeof profile[field] !== 'string') throw new TypeError('Report profile field must be a string: ' + field);
  }
  for (const field of NUMERIC_FIELDS) {
    if (typeof profile[field] !== 'number' || !Number.isFinite(profile[field])) {
      throw new TypeError('Report profile field must be a number: ' + field);
    }
  }
  return profile;
}

function profileOf(profile) {
  return profile === undefined ? DEFAULT_PROFILE : assertProfile(profile);
}

/** Audit thresholds derived from a profile (body floor, not the footer reserve). */
export function auditOptions(profile = DEFAULT_PROFILE) {
  const value = profileOf(profile);
  return {
    left_mm: value.left_mm,
    right_mm: value.right_mm,
    top_mm: value.top_mm,
    bottom_mm: value.bottom_mm,
    footer_band_mm: value.footer_band_mm,
    appendix_top_mm: value.appendix_top_mm,
    minimum_body_words: value.min_body_words,
  };
}

/** dataclasses.asdict() equivalent: declaration order, a fresh deep copy. */
export function toDict(profile = DEFAULT_PROFILE) {
  const value = profileOf(profile);
  const out = {};
  for (const field of PROFILE_FIELDS) out[field] = value[field];
  return out;
}

export const audit_options = auditOptions;
export const assert_profile = assertProfile;
export const to_dict = toDict;