"""Verify the ChronoSeal Enterprise brand identity and the surfaces that use it.

The brand sheet defines five roles, two typefaces and eight module icons.  All of
them live in ``chronoseal/branding.py``; every GUI reads that module, so these
tests fail whenever a surface drifts back to a local colour literal.
"""
import ast
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chronoseal import branding  # noqa: E402

BRAND_SHEET = {
    "primary": "#0B1F3B",
    "accent": "#1E64D6",
    "gold": "#D4AF37",
    "background": "#E6EEF7",
    "surface": "#FFFFFF",
}
HEX = re.compile(r"^#[0-9A-F]{6}$")
HEX_LITERAL = re.compile(r"#[0-9a-fA-F]{6}\b")
GUI_SURFACES = (
    "ChronoSeal_GUI.pyw",
    "ChronoSeal_Original_Legacy.py",
    "automation/Start_Automation.py",
    "automation/File_Filter_Panel.py",
)


def _nav_pages():
    """The workspace pages, read from the AST so no Tk window is created."""
    tree = ast.parse((ROOT / "ChronoSeal_GUI.pyw").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        targets = getattr(node, "targets", [])
        if any(getattr(t, "id", None) == "NAV_ITEMS" for t in targets):
            return [item.elts[0].value for item in node.value.elts]
    raise AssertionError("NAV_ITEMS not found in ChronoSeal_GUI.pyw")


# ------------------------------------------------------------------ palette
def test_brand_sheet_roles_are_exact():
    for role, value in BRAND_SHEET.items():
        assert branding.PALETTE[role] == value, role


def test_every_brand_sheet_role_is_documented():
    assert set(BRAND_SHEET) == set(branding.PALETTE_ROLES)


def test_palette_values_are_uppercase_hex():
    for role, value in branding.PALETTE.items():
        assert HEX.match(value), f"{role} is not #RRGGBB: {value!r}"


def test_palette_covers_the_derived_roles_the_guis_use():
    for role in ("primary_hover", "rail_text", "accent_hover", "console_bg",
                 "console_fg", "on_accent", "ink", "body", "muted", "border",
                 "trough", "surface_alt"):
        assert role in branding.PALETTE, role


# -------------------------------------------------------------------- icons
def test_glyphs_are_sixteen_by_sixteen():
    assert len(branding.GLYPHS) == 9
    for name, mask in branding.GLYPHS.items():
        assert len(mask) == branding.GLYPH_SIZE, name
        for row in mask:
            assert len(row) == branding.GLYPH_SIZE, name
            assert set(row) <= {".", "#"}, name
        assert "#" in "".join(mask), name


def test_every_nav_page_has_an_icon():
    pages = _nav_pages()
    assert sorted(pages) == sorted(branding.PAGE_ICONS), pages
    for page, glyph in branding.PAGE_ICONS.items():
        assert glyph in branding.GLYPHS, page


def test_module_catalog_uses_known_glyphs():
    assert len(branding.MODULES) == 9
    labels = {module["label"] for module in branding.MODULES}
    assert {"Отчет", "Хешове", "Времеви печат", "Подпис", "Проверка",
            "Архив", "Конфигурация", "Журнал"} <= labels
    for module in branding.MODULES:
        assert module["icon"] in branding.GLYPHS, module
        if module["page"] is not None:
            assert module["page"] in _nav_pages(), module


# --------------------------------------------------------------- typography
def test_resolve_family_prefers_the_brand_face():
    stack = branding.stack_for("ui")
    assert branding.resolve_family(stack, ["Arial", "Inter"]) == "Inter"


def test_resolve_family_is_case_insensitive():
    assert branding.resolve_family(("Inter", "Arial"), ["inter"]) == "inter"


def test_resolve_family_falls_back_to_the_last_entry():
    assert branding.resolve_family(branding.stack_for("ui"), []) == "Arial"
    assert branding.resolve_family(branding.stack_for("mono"), ["Segoe UI"]) == "Courier New"


def test_fontbook_resolves_each_role_without_a_display():
    book = branding.FontBook(available=["Arial", "Segoe UI", "Consolas"])
    assert book.brand_faces() == {"ui": "Segoe UI", "document": "Segoe UI", "mono": "Consolas"}
    assert book.font(10) == ("Segoe UI", 10)
    assert book.font(11, "bold") == ("Segoe UI", 11, "bold")
    assert book.font(role="mono") == ("Consolas", branding.FONT_SIZES["body"])


def test_fontbook_prefers_brand_faces_when_installed():
    book = branding.FontBook(available=["Inter", "Source Sans 3", "Cascadia Mono"])
    assert book.family("ui") == "Inter"
    assert book.family("document") == "Source Sans 3"
    assert book.family("mono") == "Cascadia Mono"


def test_unknown_font_role_is_rejected():
    with pytest.raises(ValueError):
        branding.stack_for("display")


# ------------------------------------------------------------------ product
def test_version_matches_the_package_manifest():
    manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert branding.VERSION == manifest["version"]
    assert branding.PRODUCT["version_label"] == "v" + branding.VERSION


def test_lockup_strings_are_the_brand_sheet_ones():
    assert branding.PRODUCT["vendor"] == "PasevSU®"
    assert branding.PRODUCT["product"] == "ChronoSeal™"
    assert branding.PRODUCT["badge"] == "Enterprise"
    assert branding.PRODUCT["tagline"] == "DIGITAL EVIDENCE · TIME STAMP · PDF SEAL"
    assert branding.PRODUCT["footer"] == "PasevSU® | Forensic Tools — Enterprise Solutions"


# ------------------------------------------------------------------ surfaces
def test_gui_surfaces_have_no_local_colour_literals():
    for name in GUI_SURFACES:
        text = (ROOT / name).read_text(encoding="utf-8")
        found = HEX_LITERAL.findall(text)
        assert not found, f"{name} still hardcodes colours: {sorted(set(found))}"


def test_gui_surfaces_import_the_brand_module():
    for name in GUI_SURFACES:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "from chronoseal import branding" in text or \
               "from chronoseal import branding, i18n" in text, name


def test_web_workspace_reads_the_same_tokens():
    css = (ROOT / "ui" / "style.css").read_text(encoding="utf-8")
    for role, value in BRAND_SHEET.items():
        assert value in css, f"ui/style.css is missing {role} {value}"
    assert "Inter" in css and "Source Sans 3" in css
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert branding.PRODUCT["tagline"] in html
    assert branding.PRODUCT["version_label"] in html
    assert "ENTERPRISE" in html


# ------------------------------------------------------------------ rendering
def test_icon_renders_a_transparent_photoimage():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # no display available
        pytest.skip(f"no display: {exc}")
    try:
        root.withdraw()
        branding.clear_icon_cache()
        image = branding.icon("verification", size=20, master=root)
        assert image.width() == 20 and image.height() == 20
        assert branding.icon("verification", size=20, master=root) is image
        for glyph in branding.GLYPHS:
            assert branding.icon(glyph, size=16, master=root).width() == 16
        with pytest.raises(ValueError):
            branding.icon("no-such-glyph", master=root)
        with pytest.raises(RuntimeError):
            branding.icon("report")
    finally:
        branding.clear_icon_cache()
        root.destroy()
