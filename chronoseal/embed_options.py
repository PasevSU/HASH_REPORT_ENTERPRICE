"""Report-type and PDF-embedding rules shared by every ChronoSeal surface.

The pipeline decides what is actually written into the PDF; this module only
answers the questions the windows must answer before a run: which report type
the current selection produces, whether the requested PDF may be embedded and
whether its pages belong before or after the hash report. Keeping the rules in
one place keeps the desktop page, the legacy window and the Report-from-Files
page from drifting apart from ``Pipeline.run``.
"""

from pathlib import Path

EMBED_POSITIONS = ("before", "after")
DEFAULT_EMBED_POSITION = "after"
LANGUAGES = ("bg", "en")

MESSAGES = {
    "position": {
        "bg": "Позицията трябва да е „преди“ или „след“ хеш отчета.",
        "en": "The position must be before or after the hash report.",
    },
    "single_not_pdf": {
        "bg": "Вграждане на самия входен файл е възможно само за PDF. "
              "За друг файл изберете COMBO папка и отделен PDF за вграждане.",
        "en": "Only a PDF can be embedded as the single input file. "
              "For any other file choose a COMBO folder and a separate PDF to embed.",
    },
    "no_pdf": {
        "bg": "Изберете PDF файл за вграждане или изключете вграждането.",
        "en": "Choose a PDF to embed or turn embedding off.",
    },
    "pdf_invalid": {
        "bg": "Избраният за вграждане файл не е четим PDF",
        "en": "The file to embed is not a readable PDF",
    },
}

POSITION_LABELS = {
    "bg": {"before": "преди", "after": "след"},
    "en": {"before": "before", "after": "after"},
}

NO_EMBED_LABEL = {
    "bg": "PDF не се вгражда",
    "en": "no embedded PDF",
}


def _language(value):
    return value if value in LANGUAGES else "en"


class EmbedOptionError(ValueError):
    """Refusal phrased for the operator; ``code`` lets a window re-phrase it."""

    def __init__(self, code, language="en", detail=""):
        self.code = code
        self.language = _language(language)
        self.detail = detail
        text = MESSAGES[code][self.language]
        super().__init__(text + (": " + detail if detail else ""))


def normalise_position(value, language="en"):
    position = str(value or "").strip().lower() or DEFAULT_EMBED_POSITION
    if position not in EMBED_POSITIONS:
        raise EmbedOptionError("position", language)
    return position


def report_type_for(embedded_kind, recursive=False, single_target=False):
    """Map the run shape to the published report type."""
    if embedded_kind == "single":
        return "SINGLE_PDF"
    if embedded_kind == "combo":
        return "COMBO_ALL_PDF" if recursive else "COMBO_PDF"
    if single_target:
        return "SINGLE"
    return "COMBO_ALL" if recursive else "COMBO"


def resolve_embed_options(*, enabled, position=DEFAULT_EMBED_POSITION, path="",
                          target=None, file_list=False, recursive=False,
                          language="en"):
    """Return what the run will do, or raise :class:`EmbedOptionError`.

    ``file_list`` marks the Report-from-Files route: the target folder is only
    the evidence root and the report is a COMBO of the explicitly chosen files,
    so a folder holding one PDF must not turn it into a SINGLE run.
    """
    language = _language(language)
    resolved = normalise_position(position, language)
    target_path = Path(target).expanduser() if target else None
    single_target = (
        not file_list and target_path is not None and target_path.is_file()
    )
    options = {
        "enabled": bool(enabled),
        "position": resolved,
        "source_pdf": False,
        "pdf": None,
        "source": None,
        "kind": None,
        "report_type": report_type_for(None, recursive, single_target),
    }
    if not options["enabled"]:
        return options
    if single_target:
        if target_path.suffix.lower() != ".pdf":
            raise EmbedOptionError("single_not_pdf", language)
        options.update(source_pdf=True, source=target_path, kind="single",
                       report_type=report_type_for("single", recursive))
        return options
    chosen = str(path or "").strip()
    if not chosen:
        raise EmbedOptionError("no_pdf", language)
    pdf = Path(chosen).expanduser()
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise EmbedOptionError("pdf_invalid", language, chosen)
    options.update(pdf=pdf, source=pdf, kind="combo",
                   report_type=report_type_for("combo", recursive))
    return options


def summary_text(options, language="en"):
    """One line an operator can read without opening any dialog."""
    language = _language(language)
    report_type = options.get("report_type") or "COMBO"
    if not options.get("enabled"):
        return report_type + " · " + NO_EMBED_LABEL[language]
    source = options.get("source")
    name = source.name if source is not None else "PDF"
    label = POSITION_LABELS[language].get(options.get("position"),
                                          DEFAULT_EMBED_POSITION)
    return f"{report_type} · {label} · {name}"
