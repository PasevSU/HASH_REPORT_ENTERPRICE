# Enterprise modular architecture — DEV v21

The declarative renderer loads recursive `style/**/*.js`, `modules/**/*.js`, and ordered `report_profiles/*.js` manifests. Shared style rules define page geometry, objects, typography, colors, columns, and pagination. The `file_information_report` profile composes a legal notice, report identity, and the reference-style FILE INFORMATION table. File hashes are streamed and a file change during hashing fails the render. The renderer rejects invalid fields, module IDs, and profile compositions.

See `docu/MODULAR_REPORTS.md` for the module contract, supported module types, authoring procedure, and limitations.

NOT IMPLEMENTED / NOT VERIFIED: migrating every legacy production report body to the declarative renderer; cryptographic RFC 3161 START/STOP, DSS, PKI, OTS, original PDF embedding, or digital signing in the modular renderer; layout regression on every legacy mode. Existing legacy generators and their cryptographic flows are preserved. Modular reports are unsigned/unsealed and are not production-equivalent. RELEASE BLOCKED.
