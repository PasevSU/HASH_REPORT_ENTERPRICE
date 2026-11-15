"""Extended trust anchor pin registry for bridge verification.

The original rfc3161_validation.py in v2.34 only pins DFN Community Root 2022.
This module extends the pin set for verification without modifying the
original file. Trust anchors are SELF-SIGNED ROOTS only. Intermediates are
not trust anchors, even if we know their fingerprints.

Source of pins: TRUST_ANCHORS_v3.7.0.txt plus the cross-sign path observed
in live DigiCert TSA responses (DigiCert Assured ID Root CA).
"""
from __future__ import annotations


# SHA-256 (lowercase) -> human-readable name
EXTENDED_TRUST_ANCHORS = {
    # ---- DFN ----
    "3cdc2c9e9e5a36cb5888fd1796cb912f846253b682c1b32057532033510c7bb6":
        "DFN-Verein Community Root CA 2022",

    # ---- DigiCert self-signed roots ----
    "552f7bdcf1a7af9e6ce672017f4f12abf77240c78e761ac203d1d9d20ac89988":
        "DigiCert Trusted Root G4",
    "3e9099b5015e8f486c00bcea9d111ee721faba355a89bcf1df69561e3dc6325c":
        "DigiCert Assured ID Root CA",

    # ---- T-TeleSec ----
    "91e2f5788d5810eba7ba58737de1548a8ecacd014598bc0b143e041b17052552":
        "T-TeleSec GlobalRoot Class 2",

    # ---- GlobalSign ----
    "2bcbbfd66282c680491c8cd7735fdbbab7a8079b127bec60c535976834399af7":
        "GlobalSign Timestamping Root R45",

    # ---- Sectigo ----
    "4941b001b8a97e961b7817c9d9e960ec4b056bfc915a8c1aabf6ef6b3ac046a5":
        "Sectigo Public Time Stamping Root R46",
    "e44ddb7952261f15005cd60c1d0c38c18cbfd17c273a31f8ed4c8f53e2685f32":
        "Sectigo Public Time Stamping Root E46",

    # ---- QuoVadis ----
    "8a866fd1b276b57e578e921c65828a2bed58e9f2f288054134b7f1f4bfc9cc74":
        "QuoVadis Root CA 1 G3",
}


def lookup(fingerprint_hex: str) -> str | None:
    """Return the human-readable name for a SHA-256 fingerprint, or None."""
    if not fingerprint_hex:
        return None
    return EXTENDED_TRUST_ANCHORS.get(fingerprint_hex.strip().lower())