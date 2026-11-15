# ChronoSeal: Volume in PDF and merge correction (RC / NOT QUALIFIED)

- The generator receives `CHRONOSEAL_VOLUME_JSON`; the `Volume:` section is inserted after `System Information (Beweissicherung)` content and before `User Information`, within the same PDF.
- `Volume` includes working path, directory, volume GUID when available, mount point, filesystem, serial, st_dev, st_ino, total/used/free capacity.
- The new report does not create an extra Volume PDF. Internal evidence JSON files remain in `ChronoSeal_Evidence` for verification; the requested *one file* applies to the published report.
- PDF assembly joins report + optional ERLAEUTERUNG into one document before stamping. PDF import remains opt-in. Signed input original remains unchanged.
- The RFC3161 output is now distinct from the unsigned working input (previous same-path hazard).
- Generated main report is deleted only after the final sealed PDF is published. Evidence intermediates are retained. A generator-created ERLAEUTERUNG sidecar may still remain; this is not yet guaranteed single-artifact output.
- Tests: new 3 regression tests PASS. Existing suite still has 2 stale/failing tests (preflight PDF auto mode expectation; non-atomic copy assertion); GUI and actual Windows RFC3161 tests NOT VERIFIED.
- RELEASE BLOCKED. Do not call this qualified.
