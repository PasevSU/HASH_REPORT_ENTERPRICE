# Modular report authoring

The declarative renderer separates report content from shared PDF presentation:

- `hash_report_generator/modules/*.js` declares a reusable content block. Modules are data-only manifests; executable JavaScript, filesystem access, and report-specific layout code are not allowed.
- `hash_report_generator/report_profiles/*.js` selects and orders modules for a report.
- `hash_report_generator/style/*.js` is the single source for page geometry, fonts, colors, typography, object behavior, table layout, and pagination.
- `module_loader.py`, `style_loader.py`, and `modular_report.py` validate manifests, load the shared rules, and render the PDF. A new profile or content block must not introduce its own fonts, margins, table colors, or page geometry.

## Existing standard single-file profile

`file_information_report` composes the legal-notice, system-information, and file-information modules. Its legal block has the two-column text/QR arrangement from the reference report. Its file table follows the supplied reference: a dark `Property` / `Value` header followed by the name, size in KB to three decimal places, creation and modification times, SHA-256, hardware ID, and report ID. A report ID is created when the caller does not supply one.

The legal notice identifies the standards and laws cited by the reference report and explicitly avoids claiming certification, qualified timestamp status, or an affidavit. The cited references are not a declaration of conformance. Keep the wording factual and review legal text before changing it.

## Adding a report

1. Reuse existing module IDs wherever their meaning matches. Add a new `modules/<id>.js` only for a distinct content block, using one of the supported module types: `file_information`, `key_values`, `text`, or `hash_table`.
2. Add `report_profiles/<id>.js` with a unique ID, title, and ordered list of module IDs. The loader rejects unknown modules and invalid or duplicate fields.
3. Supply report-specific values through the renderer context (`system`, `files`, `source`, and `legal_text`). Keep visual changes in `style/*.js`, not in a module or profile.
4. Run `python -m unittest discover -s hash_report_generator/tests -p test_enterprise_modules.py`.

## Production boundary

The modular renderer currently produces unsigned/unsealed reports. It does not create or verify RFC 3161 START/STOP evidence, sign PDFs, embed TSA responses, or replace the legacy production generators. Those cryptographic flows remain unchanged; do not describe an output from `modular_report.render_report` as timestamped or signed.
