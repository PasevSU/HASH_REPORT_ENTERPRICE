# DEV v24 evidence runtime scope

- Adds deterministic SHA-256 commitment over the ordered process-module output hashes and sizes.
- Rejects unsafe module IDs and artifact paths, and checks symlinks at verification.
- Keeps all runs UNSEALED. The commitment is NOT a trusted timestamp, signature or cryptographic proof of when processing occurred.
- RFC3161 START/STOP, PKI, PDF combination and final Enterprise release remain BLOCKED.
- Does not implement OTS or blockchain verification.
