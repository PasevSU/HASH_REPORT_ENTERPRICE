"""ChronoSeal Enterprise visual identity.

One module owns the brand: palette, typography stacks, module icons and the
product lockup strings.  Every GUI shell (the Tk workspace, the automation and
selection panels, and the web workspace under ``ui/``) reads these values, so a
rebrand is a single edit and can never drift between surfaces.

The PDF report palette is deliberately *not* defined here.  Report colours live
in ``hash_report_generator/style/10_palette.js`` and report fonts in
``hash_report_generator/style/25_font_families.js``; a GUI rebrand must not be
able to change a byte of a generated report.
"""
from __future__ import annotations

from types import MappingProxyType

VERSION = "5.7.0"

# --------------------------------------------------------------------- palette
# The five brand colours come straight from the brand sheet.  Everything else
# is a derived workspace shade of the same family, named by role so widget code
# never has to invent a hex value.
PALETTE = MappingProxyType({
    # brand sheet
    "primary": "#0B1F3B",
    "accent": "#1E64D6",
    "gold": "#D4AF37",
    "background": "#E6EEF7",
    "surface": "#FFFFFF",
    # derived: navigation rail
    "primary_hover": "#17365B",
    "rail_text": "#C7D6E8",
    "rail_text_strong": "#FFFFFF",
    "rail_rule": "#1E3E63",
    # derived: accents
    "accent_hover": "#1A56BC",
    "gold_hover": "#C39E2C",
    "gold_soft": "#F2E3B0",
    # derived: content
    "ink": "#0B1F3B",
    "body": "#1B3350",
    "muted": "#4E6480",
    "muted_soft": "#7A8EA6",
    "border": "#C9D7E7",
    "border_soft": "#DCE6F2",
    "surface_alt": "#F5F8FC",
    "status_bg": "#D8E4F2",
    "status_fg": "#23405F",
    "trough": "#D3DFEE",
    "disabled": "#A9B9CC",
    "on_accent": "#FFFFFF",
    # derived: console surfaces
    "console_bg": "#071A33",
    "console_fg": "#D6E4F5",
    "console_select": "#1E64D6",
    "console_border": "#1B3B60",
})

# The five roles the brand sheet names, kept for documentation and tests.
PALETTE_ROLES = MappingProxyType({
    "primary": "Основен",
    "accent": "Акцент",
    "gold": "Златен",
    "background": "Фон",
    "surface": "Бяло",
})

# ----------------------------------------------------------------- typography
# Resolved against the families the operating system actually has: Inter and
# Source Sans 3 are the brand faces, the rest are the documented fallbacks.
FONT_STACKS = MappingProxyType({
    "ui": ("Inter", "Inter Variable", "Segoe UI", "Arial"),
    "document": ("Source Sans 3", "Source Sans Pro", "Segoe UI", "Arial"),
    "mono": ("Cascadia Mono", "Consolas", "Courier New"),
})

FONT_SIZES = MappingProxyType({
    "micro": 9,
    "small": 9,
    "body": 10,
    "label": 10,
    "section": 11,
    "brand_mark": 13,
    "brand": 17,
    "page": 20,
    "workspace": 18,
})

# -------------------------------------------------------------------- product
PRODUCT = MappingProxyType({
    "vendor": "PasevSU®",
    "product": "ChronoSeal™",
    "badge": "Enterprise",
    "tagline": "DIGITAL EVIDENCE · TIME STAMP · PDF SEAL",
    "version_label": "v" + VERSION,
    "footer": "PasevSU® | Forensic Tools — Enterprise Solutions",
    "licence": "Created & licensed by Home Assistant Projects · PasevSU DEV",
    "campaign": "Part of the NO TRUST Cybersecurity volunteer campaign",
})

# ---------------------------------------------------------------- module icons
# The eight modules the brand sheet specifies, plus a funnel for the Selection
# workspace.  ``label`` is the Bulgarian brand name, ``page`` the workspace page
# that renders the icon (``None`` for a module without its own page yet).
MODULES = (
    MappingProxyType({"icon": "report", "label": "Отчет", "page": "run_tab"}),
    MappingProxyType({"icon": "hashes", "label": "Хешове", "page": None}),
    MappingProxyType({"icon": "timestamp", "label": "Времеви печат", "page": "automation_tab"}),
    MappingProxyType({"icon": "signature", "label": "Подпис", "page": None}),
    MappingProxyType({"icon": "verification", "label": "Проверка", "page": None}),
    MappingProxyType({"icon": "archive", "label": "Архив", "page": None}),
    MappingProxyType({"icon": "configuration", "label": "Конфигурация", "page": "set_tab"}),
    MappingProxyType({"icon": "journal", "label": "Журнал", "page": "diag_tab"}),
    MappingProxyType({"icon": "filter", "label": "Филтър", "page": "filter_tab"}),
)

PAGE_ICONS = MappingProxyType({
    "run_tab": "report",
    "report_files_tab": "journal",
    "automation_tab": "timestamp",
    "set_tab": "configuration",
    "diag_tab": "journal",
    "filter_tab": "filter",
})

# 16x16 masks.  '#' is a foreground pixel, '.' a hole that is made transparent
# in the rendered PhotoImage.
GLYPHS = MappingProxyType({
    "report": (
        "................",
        "................",
        "....########....",
        "....#......#....",
        "....#.####.#....",
        "....#......#....",
        "....#.####.#....",
        "....#......#....",
        "....#.####.#....",
        "....#......#....",
        "....#.###..#....",
        "....#......#....",
        "....########....",
        "................",
        "................",
        "................",
    ),
    "hashes": (
        "................",
        "................",
        ".....#....#.....",
        ".....#....#.....",
        "...##########...",
        "....#....#......",
        "....#....#......",
        "...##########...",
        "....#....#......",
        "....#....#......",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
    ),
    "timestamp": (
        "................",
        "......####......",
        "....##....##....",
        "...#........#...",
        "..#..........#..",
        "..#....#.....#..",
        ".#.....#.....#..",
        ".#.....###...#..",
        ".#...........#..",
        "..#..........#..",
        "..#..........#..",
        "...#........#...",
        "....##....##....",
        "......####......",
        "................",
        "................",
    ),
    "signature": (
        "................",
        "................",
        "..........###...",
        ".........#...#..",
        "........#.......",
        ".......#........",
        "......#.........",
        ".....#..........",
        "..#.#...........",
        "...#............",
        "..#.............",
        ".#....##........",
        "..####..........",
        "..############..",
        "................",
        "................",
    ),
    "verification": (
        "................",
        "....########....",
        "...#........#...",
        "..#..........#..",
        "..#..........#..",
        "..#..........#..",
        "..#.......#..#..",
        "..#..#...#...#..",
        "..#...#.#....#..",
        "..#....#.....#..",
        "..#..........#..",
        "...#........#...",
        "....#......#....",
        ".....#....#.....",
        "......#..#......",
        ".......##.......",
    ),
    "archive": (
        "................",
        "................",
        "..############..",
        "..#..........#..",
        "..############..",
        "..#..........#..",
        "..#..........#..",
        "..#...####...#..",
        "..#..........#..",
        "..#..........#..",
        "..#..........#..",
        "..#..........#..",
        "..############..",
        "................",
        "................",
        "................",
    ),
    "configuration": (
        "................",
        "....##....##....",
        "..############..",
        "..############..",
        ".###........###.",
        ".##..........##.",
        "##............##",
        "##....####....##",
        "##....####....##",
        "##............##",
        ".##..........##.",
        ".###........###.",
        "..############..",
        "..############..",
        "....##....##....",
        "................",
    ),
    "journal": (
        "................",
        "................",
        "................",
        "................",
        "............#...",
        "......#.....#...",
        "......#.....#...",
        "......#..#..#...",
        "...#..#..#..#...",
        "...#..#..#..#...",
        "...#..#..#..#...",
        "...#..#..#..#...",
        "..############..",
        "................",
        "................",
        "................",
    ),
    "filter": (
        "................",
        "................",
        "..############..",
        "..############..",
        "...##########...",
        "....########....",
        "....########....",
        ".....######.....",
        ".....######.....",
        "......####......",
        "......####......",
        ".......##.......",
        ".......##.......",
        ".......##.......",
        "................",
        "................",
    ),
})

GLYPH_SIZE = 16


# -------------------------------------------------------------------- helpers
def resolve_family(stack, available):
    """First family of *stack* that *available* contains, else the last entry.

    *available* is any iterable of installed font family names, so the rule is
    testable without a display.
    """
    installed = {}
    for family in available or ():
        installed.setdefault(str(family).casefold(), str(family))
    for candidate in stack:
        hit = installed.get(candidate.casefold())
        if hit:
            return hit
    return stack[-1]


def stack_for(role):
    try:
        return FONT_STACKS[role]
    except KeyError:
        raise ValueError("unknown font role %r" % (role,)) from None


class FontBook:
    """Resolve the brand font stacks to the families this machine has."""

    def __init__(self, widget=None, available=None):
        if available is None:
            import tkinter.font as tkfont

            available = tkfont.families(widget)
        self._available = tuple(available)
        self._resolved = {}

    @property
    def available(self):
        return self._available

    def family(self, role="ui"):
        if role not in self._resolved:
            self._resolved[role] = resolve_family(stack_for(role), self._available)
        return self._resolved[role]

    def font(self, size=None, weight=None, role="ui"):
        family = self.family(role)
        size = FONT_SIZES["body"] if size is None else size
        return (family, size, weight) if weight else (family, size)

    def brand_faces(self):
        """``{'ui': family, 'document': family, 'mono': family}``."""
        return {role: self.family(role) for role in FONT_STACKS}


_ICON_CACHE = {}


def icon(name, size=GLYPH_SIZE, fg=None, bg=None, master=None):
    """Render a brand glyph as a ``tk.PhotoImage``.

    Empty mask cells become transparent pixels, so one image works on the rail,
    on an accent-filled button and in the header.  ``bg`` is only the scratch
    fill before the transparent pixels are punched out.
    """
    if name not in GLYPHS:
        raise ValueError("unknown module icon %r" % (name,))
    if master is None:
        raise RuntimeError("icon() needs a Tk master (a widget or Tk root)")
    size = int(size)
    fg = fg or PALETTE["primary"]
    bg = bg or PALETTE["surface"]
    # The cache is per Tcl interpreter: image names restart at ``pyimage1`` for
    # every new root, so a cached image from a destroyed window must never be
    # handed to a fresh one (it would fail with "image does not exist").
    key = (id(master.tk), name, size, fg, bg)
    cached = _ICON_CACHE.get(key)
    if cached is not None and getattr(cached, "tk", None) is master.tk:
        return cached

    import tkinter as tk

    mask = GLYPHS[name]
    rows = len(mask)
    cols = len(mask[0])
    image = tk.PhotoImage(master=master, width=size, height=size)
    image.put(bg, to=(0, 0, size, size))
    for y in range(size):
        source = mask[min(rows - 1, y * rows // size)]
        for x in range(size):
            cell = source[min(cols - 1, x * cols // size)]
            if cell == ".":
                image.transparency_set(x, y, True)
            else:
                image.put(fg, to=(x, y))
    _ICON_CACHE[key] = image
    return image


def clear_icon_cache(master=None):
    """Drop cached icons; with *master*, only that Tcl interpreter's icons."""
    if master is None:
        _ICON_CACHE.clear()
        return
    interpreter = id(master.tk)
    for key in [k for k in _ICON_CACHE if k[0] == interpreter]:
        del _ICON_CACHE[key]
