# v5.5.4 RC — Implementation / qualification

- SINGLE: generator report -> compose -> START/STOP -> `..._HASHREPORT_TYP_SINGLE.pdf`.
- COMBO: generator report -> compose -> START/STOP -> `..._HASHREPORT_TYP_COMBO.pdf`.
- SINGLE_PDF opt-in: generator SINGLE report -> optional ERLAEUTERUNG -> visual PDF pages + embedded unmodified original attachment -> START/STOP -> `..._HASHREPORT_TYP_SINGLE_PDF.pdf`.
- Preflight always checks generator, including PDF embed mode.
- The volume section implementation comes unchanged from v5.5.3 VOLUME_IN_REPORT_MERGE_FIX_RC.
- Intermediate files and JSON evidence remain in internal ChronoSeal_Evidence case. Exactly one final named PDF is published; this does NOT mean no other filesystem files are created.
- WARNING: Original PDF signature validity does not transfer to visual pages; original attached bytes remain separately verifiable.
- NOT QUALIFIED: no live TSA/Windows GUI qualification, no full generator regression, no visual rendering of representative PDFs.
