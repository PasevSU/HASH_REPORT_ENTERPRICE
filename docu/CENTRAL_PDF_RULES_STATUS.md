# Central PDF rules — DEV v11

Canonical source: `hash_report_generator/pdf_object_rules.py`.

Defines page, fonts, leading, colors, table columns, padding, object policies for page/header/footer/title/headings/paragraph/legal text/tables/cells/hashes/timestamps/certificates/QR/images/links/lists/dividers/spacers/page breaks/attachments/volume/user/system/page hashes.

Wiring: `hash_report_core.ReportConstants` gets central presentation overrides, all generators inheriting it receive them; `chronoseal.unified_theme` is a compatibility facade; CSS generated from canonical source.

LIMITATIONS: legacy direct literals in generator bodies, canvas footers and non-core automation templates are not yet completely migrated. Not independently PDF-rendered and not TSA/PKI qualified. RELEASE BLOCKED.
