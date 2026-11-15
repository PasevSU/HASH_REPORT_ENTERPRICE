# Storage identity addition (audit candidate)

- Read-only storage provenance before report generation: target path, resolved directory, st_dev, st_ino, capacity and free bytes.
- On Windows, attempts Volume GUID, mount point, filesystem name and volume serial using Win32 APIs. GUID may be unavailable for UNC paths.
- Saves `storage-identity.json` in each evidence case with input/evidence/output locations.
- No change to RFC3161 bridge, page composition or report generator.
- Tests: 3 new filesystem tests passed on Linux; Windows Win32 API and full pipeline still NOT VERIFIED.
- This does not address the other blocking regressions in the v5.5.3 segmented audit. NOT QUALIFIED.
