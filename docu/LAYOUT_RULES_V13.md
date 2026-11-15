# Central PDF rules v13 — development status
- Legal font 8 pt vs body 9 pt; legal background/padding defined in pdf_object_rules.py.
- Exact file sizes in bytes for system information and COMBO table.
- System and user information rendered as two-column aligned labels/values.
- All rules are centralized; legacy generators still contain other local layout constants and require migration.
- RFC3161/PKI end-to-end and visual regression are NOT VERIFIED. RELEASE BLOCKED.
