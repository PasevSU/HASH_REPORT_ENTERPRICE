"""Rules for the closing verification-QR block shared by every ChronoSeal surface.

Every report carries the block; it is not an option. The generator needs the target
before it renders the page, so the run works in one direction only: the pipeline
builds the link from the configured base address plus a freshly generated code, the
generator prints it, and the same link is recorded in the evidence case. The code is
random on purpose - it names the upload slot on the document server, not the report.

The generators keep their own copy of the checks because ``hash_report_generator``
must stay a stand-alone script with no ChronoSeal imports, so both sides validate
independently on purpose.
"""

import os
import secrets
from urllib.parse import urlsplit

LANGUAGES = ("bg", "en")
ALLOWED_SCHEMES = ("http", "https")
MAX_URL_LENGTH = 2048
QR_POSITION = "document_end"
DEFAULT_BASE_URL = "https://pasev.asuscomm.com/static/"
# 37 hex digits split by four dashes: ten, three groups of four and a long tail.
# The code is never shorter than the one the document server already issues
# (571b3398f1-4e61-494d-8064-45c8417a3625148 - 37 digits, 41 characters).
CODE_GROUPS = (10, 4, 4, 4, 15)
BASE_URL_ENV = "CHRONOSEAL_EVIDENCE_BASE_URL"

MESSAGES = {
    "url_scheme": {
        "bg": "Базовият адрес трябва да започва с http:// или https://.",
        "en": "The base address must start with http:// or https://.",
    },
    "url_invalid": {
        "bg": "Базовият адрес не е пълен адрес с хост и не трябва да съдържа интервали.",
        "en": "The base address is not a complete address with a host and must not "
              "contain spaces.",
    },
    "url_too_long": {
        "bg": f"Адресът е по-дълъг от {MAX_URL_LENGTH} знака; QR кодът няма "
              "да е надеждно четим.",
        "en": f"The address is longer than {MAX_URL_LENGTH} characters, so the QR "
              "code would not stay reliably scannable.",
    },
    "not_applied": {
        "bg": "Отчетът е генериран, но не съдържа затварящия блок с QR код. "
              "Отчетът се отхвърля, за да не изглежда, че документът съдържа "
              "връзка към доказателствата.",
        "en": "The report was generated without the closing QR block. The report is "
              "rejected so it cannot look as if it carries a link to the evidence.",
    },
    "ots_missing": {
        "bg": "Придружаващият OTS документ липсва или не съответства на отчета.",
        "en": "The accompanying OTS proof is missing or does not match the report.",
    },
}

INFO_LABEL = {
    "bg": "QR код: задължителен за всеки отчет",
    "en": "QR code: mandatory in every report",
}


def _language(value):
    return value if value in LANGUAGES else "en"


class QrOptionError(ValueError):
    """Refusal phrased for the operator; ``code`` lets a window re-phrase it."""

    def __init__(self, code, language="en", detail=""):
        self.code = code
        self.language = _language(language)
        self.detail = detail
        text = MESSAGES[code][self.language]
        super().__init__(text + (": " + detail if detail else ""))


def normalise_url(value, language="en", required=False):
    """Return the usable address, or ``''`` when nothing was supplied.

    Empty input is legal unless ``required`` is set: the pipeline always supplies
    one, while the stand-alone generator may run without any base address.
    """
    text = "" if value is None else str(value).strip()
    if not text:
        if required:
            raise QrOptionError("url_invalid", language)
        return ""
    if len(text) > MAX_URL_LENGTH:
        raise QrOptionError("url_too_long", language)
    if any(character.isspace() for character in text):
        raise QrOptionError("url_invalid", language)
    parts = urlsplit(text)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise QrOptionError("url_scheme", language)
    if not parts.netloc:
        raise QrOptionError("url_invalid", language)
    return text


def code_groups(config=None):
    """Group sizes for a generated code, overridable in the run configuration."""
    section = (config or {}).get("verification") if isinstance(config, dict) else None
    groups = section.get("code_groups") if isinstance(section, dict) else None
    if not groups:
        return CODE_GROUPS
    try:
        numbers = tuple(int(item) for item in groups)
    except (TypeError, ValueError):
        raise QrOptionError("url_invalid", "en",
                            "verification.code_groups must hold integers")
    if not numbers or any(number < 1 for number in numbers) or sum(numbers) < 32:
        raise QrOptionError("url_invalid", "en",
                            "verification.code_groups must sum to at least 32 hex digits")
    return numbers


def new_code(groups=None):
    """Return a random code shaped like the ones the document server issues."""
    sizes = tuple(groups or CODE_GROUPS)
    return "-".join(secrets.token_hex((size + 1) // 2)[:size] for size in sizes)


def base_url(config=None, environ=None):
    """Resolve the address the generated codes hang under, with a trailing slash."""
    source = os.environ if environ is None else environ
    configured = ""
    if isinstance(config, dict):
        section = config.get("verification") or {}
        if isinstance(section, dict):
            configured = str(section.get("base_url") or "").strip()
    candidate = (str(source.get(BASE_URL_ENV) or "").strip()
                 or configured or DEFAULT_BASE_URL)
    text = normalise_url(candidate, required=True)
    return text if text.endswith("/") else text + "/"


def new_link(config=None, environ=None, override="", groups=None):
    """Return ``{'code', 'url'}`` for one report.

    ``override`` exists for tests and for installations that already know the slot
    they will publish into; anything else is generated here.
    """
    explicit = normalise_url(override)
    if explicit:
        return {"code": explicit.rstrip("/").rsplit("/", 1)[-1], "url": explicit}
    code = new_code(groups or code_groups(config))
    return {"code": code, "url": base_url(config, environ) + code}


def resolve(config=None, environ=None, override="", language="en"):
    """Return what the run will print into the closing block."""
    language = _language(language)
    link = new_link(config, environ, override, code_groups(config))
    return {"enabled": True,
            "code": link["code"],
            "url": normalise_url(link["url"], language, required=True),
            "position": QR_POSITION}


def summary_text(options, language="en"):
    """One line an operator can read without opening any dialog.

    The generated code is left out: it names the upload slot of one report, so it
    would only make the read-back line longer than the address it describes.
    """
    if not options or not options.get("url"):
        return INFO_LABEL[_language(language)]
    parts = urlsplit(options["url"])
    host = parts.netloc or options["url"]
    path = parts.path if parts.path not in ("", "/") else ""
    code = str(options.get("code") or "").strip()
    if code and path.rstrip("/").endswith("/" + code):
        path = path.rstrip("/")[: -len(code) - 1]
    path = path.rstrip("/")
    return f"QR · {host}{path}"
