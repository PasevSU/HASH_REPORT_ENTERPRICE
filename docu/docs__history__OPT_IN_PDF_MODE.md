# PDF mode is explicitly opt-in (RC)

For a selected PDF, the GUI asks whether to enter the independent PDF embedding mode. YES: compose a new unsigned visual-page copy of the selected PDF (original signatures remain only in original), then apply new page identities and START/STOP. NO: run the existing SINGLE hash report generator against the PDF as a normal file, then apply the ordinary report workflow. Folder inputs retain COMBO behavior. ERLAEUTERUNG remains a separate yes/no question.

The PDF mode is never inferred from the .pdf extension alone. Existing preflight-only diagnostics assume ordinary SINGLE mode; the run-time preflight uses the user's answer.

NOT QUALIFIED: Windows end-to-end TSA verification and GUI regression are still required.
