"""Single ChronoSeal enterprise workspace."""
from pathlib import Path
import sys
import importlib.util
import importlib.machinery
from tkinter import messagebox, ttk
import tkinter as tk
from datetime import datetime

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "automation"))

from chronoseal import branding, i18n
i18n.install()

automation_loader = importlib.machinery.SourceFileLoader(
    "chronoseal_automation_ui", str(BASE / "automation" / "Start_Automation.py")
)
automation_spec = importlib.util.spec_from_loader(automation_loader.name, automation_loader)
automation_module = importlib.util.module_from_spec(automation_spec)
automation_loader.exec_module(automation_module)
AutomationPanel = automation_module.App

# v5.5.0: additive Selection workspace (folder scope + chainable file filters).
# Loaded exactly like the Automation panel so the legacy window is untouched.
filter_loader = importlib.machinery.SourceFileLoader(
    "chronoseal_filter_ui", str(BASE / "automation" / "File_Filter_Panel.py")
)
filter_spec = importlib.util.spec_from_loader(filter_loader.name, filter_loader)
filter_module = importlib.util.module_from_spec(filter_spec)
filter_loader.exec_module(filter_module)
FilterPanel = filter_module.App
file_filters = filter_module.file_filters

# v5.5.2: additive Report-from-Files workspace. It builds one COMBO report from
# an explicit list of files instead of scanning a folder. Loaded the same way as
# the other panels so the legacy window keeps working unchanged.
report_files_loader = importlib.machinery.SourceFileLoader(
    "chronoseal_report_files_ui", str(BASE / "automation" / "Report_From_Files_Panel.py")
)
report_files_spec = importlib.util.spec_from_loader(
    report_files_loader.name, report_files_loader
)
report_files_module = importlib.util.module_from_spec(report_files_spec)
report_files_loader.exec_module(report_files_module)
ReportFilesPanel = report_files_module.App

loader = importlib.machinery.SourceFileLoader(
    "chronoseal_original_ui", str(BASE / "ChronoSeal_Original_Legacy.py")
)
spec = importlib.util.spec_from_loader(loader.name, loader)
original = importlib.util.module_from_spec(spec)
loader.exec_module(original)


class ChronoSealDesktop(original.App):
    # The page-based shell is English, so the shared option dialogs follow it.
    embed_language = "en"
    NAV_ITEMS = (
        ("run_tab", "01", "Report & TSA", "Generate, seal and verify"),
        ("report_files_tab", "02", "Report from Files", "One combo report from chosen files"),
        ("automation_tab", "03", "Automation", "Plan recurring reports"),
        ("set_tab", "04", "Settings & Trust", "Tools and TSA profiles"),
        ("diag_tab", "05", "Diagnostics", "Preflight and evidence logs"),
        ("filter_tab", "06", "Selection", "Filter evidence by file type"),
    )

    def __init__(self, *, auto_bootstrap=True):
        super().__init__(auto_bootstrap=auto_bootstrap)
        self.title("ChronoSeal | Evidence Workspace")
        self.geometry("1440x940")
        self.minsize(1000, 680)
        self._live_clock()
        self._refresh_filter_indicator()
        for index, (page, *_rest) in enumerate(self.NAV_ITEMS, start=1):
            self.bind(f"<Control-Key-{index}>", lambda _event, name=page: self._select_page(name))

    def _configure_enterprise_theme(self):
        super()._configure_enterprise_theme()
        style = ttk.Style(self)
        palette = branding.PALETTE
        fonts = self._fonts()
        bg = palette["background"]
        navy = palette["primary"]
        panel = palette["surface"]
        border = palette["border"]
        muted = palette["muted"]
        accent = palette["accent"]
        body = palette["body"]
        self.configure(background=bg)
        style.configure(".", font=fonts.font(branding.FONT_SIZES["body"]))
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=body)
        style.configure("Workspace.TFrame", background=navy)
        style.configure("Header.TFrame", background=panel)
        style.configure("BrandMark.TLabel", background=navy, padding=(9, 7))
        style.configure("BrandTitle.TLabel", background=panel, foreground=navy,
                        font=fonts.font(branding.FONT_SIZES["brand"], "bold"))
        style.configure("BrandBadge.TLabel", background=palette["gold"], foreground=navy,
                        padding=(8, 2),
                        font=fonts.font(branding.FONT_SIZES["micro"], "bold"))
        style.configure("BrandSub.TLabel", background=panel, foreground=muted,
                        font=fonts.font(branding.FONT_SIZES["small"]))
        style.configure("WorkspaceTitle.TLabel", background=navy,
                        foreground=palette["rail_text_strong"],
                        font=fonts.font(branding.FONT_SIZES["workspace"], "bold"))
        style.configure("WorkspaceSub.TLabel", background=navy,
                        foreground=palette["rail_text"],
                        font=fonts.font(branding.FONT_SIZES["small"]))
        style.configure("Eyebrow.TLabel", background=bg, foreground=accent,
                        font=fonts.font(branding.FONT_SIZES["small"], "bold"))
        style.configure("PageTitle.TLabel", background=bg, foreground=navy,
                        font=fonts.font(branding.FONT_SIZES["page"], "bold"))
        style.configure("PageSub.TLabel", background=bg, foreground=muted,
                        font=fonts.font(branding.FONT_SIZES["body"], role="document"))
        style.configure("Section.TLabel", background=panel, foreground=navy,
                        font=fonts.font(branding.FONT_SIZES["section"], "bold"))
        style.configure("Muted.TLabel", background=bg, foreground=muted,
                        font=fonts.font(branding.FONT_SIZES["small"]))
        style.configure("Workspace.TNotebook", background=bg, borderwidth=0, tabmargins=0)
        style.layout("Workspace.TNotebook.Tab", [])
        style.configure("Nav.TButton", background=navy, foreground=palette["rail_text"],
                        anchor="w", justify="left", padding=(13, 11), borderwidth=0,
                        font=fonts.font(branding.FONT_SIZES["body"]))
        style.map("Nav.TButton", background=[("active", palette["primary_hover"])],
                  foreground=[("active", palette["rail_text_strong"])])
        style.configure("NavSelected.TButton", background=accent,
                        foreground=palette["on_accent"], anchor="w", justify="left",
                        padding=(13, 11), borderwidth=0,
                        font=fonts.font(branding.FONT_SIZES["body"], "bold"))
        style.map("NavSelected.TButton", background=[("active", palette["accent_hover"])])
        style.configure("Panel.TLabelframe", background=panel, bordercolor=border,
                        relief="solid", padding=14)
        style.configure("Panel.TLabelframe.Label", background=panel, foreground=navy,
                        font=fonts.font(branding.FONT_SIZES["label"], "bold"))
        style.configure("Accent.TButton", background=accent,
                        foreground=palette["on_accent"],
                        font=fonts.font(branding.FONT_SIZES["body"], "bold"),
                        padding=(16, 11), borderwidth=0)
        style.map("Accent.TButton", background=[("active", palette["accent_hover"]),
                                                ("disabled", palette["disabled"])])
        style.configure("TButton", padding=(10, 7))
        style.configure("TEntry", padding=8, fieldbackground=panel, foreground=body)
        style.configure("TCombobox", padding=7, fieldbackground=panel, foreground=body)
        style.map("TCombobox", fieldbackground=[("readonly", panel)],
                  foreground=[("readonly", body)])
        style.configure("TCheckbutton", background=panel, foreground=body)
        style.map("TCheckbutton", background=[("active", panel)])
        # v5.11.0: ttk.Radiobutton is used by the embed-position control but was
        # never configured, so it kept clam's default grey inside white panels.
        # Mirror TCheckbutton so every toggle row shares one surface colour.
        style.configure("TRadiobutton", background=panel, foreground=body)
        style.map("TRadiobutton", background=[("active", panel)],
                  foreground=[("active", body), ("disabled", palette["disabled"])])
        # v5.11.0: state the tree surface explicitly instead of inheriting clam.
        style.configure("Treeview", background=panel, fieldbackground=panel,
                        foreground=body)
        style.map("Treeview", background=[("selected", accent)],
                  foreground=[("selected", palette["on_accent"])])
        style.configure("Status.TLabel", background=palette["status_bg"],
                        foreground=palette["status_fg"], padding=(10, 7),
                        font=fonts.font(branding.FONT_SIZES["small"]))
        style.configure("Horizontal.TProgressbar", thickness=9,
                        troughcolor=palette["trough"], background=accent)
        style.configure("TScrollbar", background=palette["border_soft"], troughcolor=bg,
                        arrowcolor=palette["muted_soft"])

    def _fonts(self):
        book = getattr(self, "_font_book", None)
        if book is None:
            book = branding.FontBook(self)
            self._font_book = book
        return book

    def _ui(self):
        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 14))
        header.pack(fill="x")
        self._brand_icon = branding.icon(
            "verification", size=30, fg=branding.PALETTE["gold"], master=self
        )
        ttk.Label(header, image=self._brand_icon, style="BrandMark.TLabel").pack(side="left")
        brand = ttk.Frame(header, style="Header.TFrame")
        brand.pack(side="left", padx=(14, 0))
        lockup = ttk.Frame(brand, style="Header.TFrame")
        lockup.pack(anchor="w")
        ttk.Label(lockup, text=branding.PRODUCT["product"],
                  style="BrandTitle.TLabel").pack(side="left")
        ttk.Label(lockup, text=branding.PRODUCT["badge"].upper(),
                  style="BrandBadge.TLabel").pack(side="left", padx=(10, 0), pady=(3, 0))
        ttk.Label(brand, text=f"{branding.PRODUCT['vendor']}  ·  {branding.PRODUCT['tagline']}",
                  style="BrandSub.TLabel").pack(anchor="w", pady=(2, 0))
        tk.Frame(self, height=3, background=branding.PALETTE["gold"]).pack(fill="x")
        self._clock_text = tk.StringVar(value="")
        i18n.add_language_selector(
            header, self, style="Header.TFrame", label_style="BrandSub.TLabel",
            side="right", padx=(14, 0))
        ttk.Label(header, textvariable=self.status, style="Status.TLabel").pack(
            side="right", padx=(8, 0)
        )
        ttk.Label(header, textvariable=self._clock_text, style="BrandSub.TLabel").pack(
            side="right", padx=(8, 0)
        )

        body = ttk.Frame(self, padding=0)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        rail = ttk.Frame(body, style="Workspace.TFrame", padding=(10, 18))
        rail.grid(row=0, column=0, sticky="nsew")
        rail.configure(width=238)
        rail.grid_propagate(False)
        ttk.Label(rail, text="WORKSPACE", style="WorkspaceSub.TLabel").pack(
            anchor="w", padx=10, pady=(2, 12)
        )

        content = ttk.Frame(body, padding=(24, 20, 24, 14))
        content.grid(row=0, column=1, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        self.nb = ttk.Notebook(content, style="Workspace.TNotebook")
        self.nb.grid(row=0, column=0, sticky="nsew")

        self.run_tab = ttk.Frame(self.nb, padding=0)
        self.report_files_tab = ttk.Frame(self.nb, padding=0)
        self.automation_tab = ttk.Frame(self.nb, padding=0)
        self.set_tab = ttk.Frame(self.nb, padding=0)
        self.diag_tab = ttk.Frame(self.nb, padding=0)
        self.filter_tab = ttk.Frame(self.nb, padding=0)
        for page, title in (
            (self.run_tab, "Report & TSA"),
            (self.report_files_tab, "Report from Files"),
            (self.automation_tab, "Automatic Reports"),
            (self.set_tab, "Settings & Trust"),
            (self.diag_tab, "Diagnostics & Logs"),
            (self.filter_tab, "Selection & Filters"),
        ):
            self.nb.add(page, text=title)

        self._nav_buttons = {}
        self._nav_icons = {}
        for page, number, title, subtitle in self.NAV_ITEMS:
            module_icon = branding.PAGE_ICONS.get(page, "report")
            icons = {
                "idle": branding.icon(module_icon, size=20,
                                      fg=branding.PALETTE["rail_text"],
                                      bg=branding.PALETTE["primary"], master=self),
                "selected": branding.icon(module_icon, size=20,
                                          fg=branding.PALETTE["on_accent"],
                                          bg=branding.PALETTE["accent"], master=self),
            }
            self._nav_icons[page] = icons
            button = ttk.Button(
                rail, text=self._nav_text(number, title, subtitle),
                image=icons["idle"], compound="left", style="Nav.TButton",
                command=lambda name=page: self._select_page(name)
            )
            button.pack(fill="x", pady=3)
            self._nav_buttons[page] = button
        i18n.on_change(self._refresh_nav_text)
        ttk.Frame(rail, style="Workspace.TFrame").pack(fill="both", expand=True)
        ttk.Label(rail, text="Evidence-first workflow\nCtrl+1–6  ·  Navigate",
                  style="WorkspaceSub.TLabel", justify="left").pack(
            anchor="w", padx=10, pady=(10, 4)
        )

        self._build_run_page()
        self._build_settings_page()
        self._build_diagnostics_page()
        self.report_files_panel = ReportFilesPanel(self, parent=self.report_files_tab)
        self.automation_panel = AutomationPanel(self, parent=self.automation_tab)
        self.filter_panel = FilterPanel(self, parent=self.filter_tab)
        self.nb.bind("<<NotebookTabChanged>>", self._on_page_changed, add="+")
        self.nb.select(self.run_tab)
        self._on_page_changed()
        self._build_footer()

    def _page_heading(self, parent, eyebrow, title, subtitle):
        ttk.Label(parent, text=eyebrow.upper(), style="Eyebrow.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(parent, text=title, style="PageTitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(3, 2)
        )
        ttk.Label(parent, text=subtitle, style="PageSub.TLabel").grid(
            row=2, column=0, sticky="w", pady=(0, 16)
        )

    def _build_run_page(self):
        # Declared here because the run page is built during the base __init__.
        self.file_filters = []
        page = self.run_tab
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, weight=1)
        self._page_heading(
            page, "Evidence pipeline", "Create and verify a report",
            "Select a file or folder. ChronoSeal generates the report, applies configured "
            "timestamps and preserves verification evidence."
        )

        source = ttk.LabelFrame(page, text="  1  ·  Input source  ", style="Panel.TLabelframe")
        source.grid(row=1, column=0, sticky="ew")
        source.columnconfigure(0, weight=1)
        path_row = ttk.Frame(source)
        path_row.grid(row=0, column=0, sticky="ew")
        path_row.columnconfigure(0, weight=1)
        ttk.Entry(path_row, textvariable=self.target).grid(row=0, column=0, sticky="ew")
        ttk.Button(path_row, text="Choose file", command=self.file).grid(
            row=0, column=1, padx=(8, 0)
        )
        ttk.Button(path_row, text="Choose folder", command=self.folder).grid(
            row=0, column=2, padx=(6, 0)
        )
        source_options = ttk.Frame(source)
        source_options.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.mode_label = ttk.Label(
            source_options, text="Report type is detected from the selected input.",
            style="Muted.TLabel"
        )
        self.mode_label.pack(side="left")
        self.rec_check = ttk.Checkbutton(
            source_options, text="Include subfolders", variable=self.rec
        )
        self.rec_check.pack(side="right")

        # The Selection panel owns the filter list; this row only reports it, so a
        # filtered run can never look like a complete one.
        filter_row = ttk.Frame(source)
        filter_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(filter_row, text="File type filter:", style="Muted.TLabel").pack(side="left")
        self.filter_summary = tk.StringVar(value="none - every file in the folder is evidence")
        ttk.Label(filter_row, textvariable=self.filter_summary, style="Muted.TLabel").pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(filter_row, text="Clear", command=self._clear_filter_indicator).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(
            filter_row, text="Edit in Selection",
            command=lambda: self._select_page("filter_tab"),
        ).pack(side="left", padx=(6, 0))

        # Only the options used on every run stay on the panel; each dialog owns
        # one subject so neither window has to scroll to be understood.
        embed = ttk.LabelFrame(page, text="  2  ·  PDF embedding  ", style="Panel.TLabelframe")
        embed.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        embed.columnconfigure(2, weight=1)
        state = self._embed_vars()
        ttk.Checkbutton(
            embed, text="Embed a PDF in the report", variable=state["enabled"]
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            embed, text="Before report", value="before", variable=state["position"]
        ).grid(row=0, column=1, padx=(14, 0), sticky="w")
        ttk.Radiobutton(
            embed, text="After report", value="after", variable=state["position"]
        ).grid(row=0, column=2, padx=(10, 0), sticky="w")
        ttk.Button(
            embed, text="PDF embedding…", command=self._embed_dialog
        ).grid(row=0, column=3, sticky="e")
        ttk.Entry(embed, textvariable=state["path"]).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0)
        )
        ttk.Button(
            embed, text="Choose PDF", command=self._choose_embed_pdf
        ).grid(row=1, column=3, padx=(8, 0), pady=(8, 0))
        # Read-back of the whole selection: report type, position and PDF name.
        ttk.Label(
            embed, textvariable=state["summary"], style="Muted.TLabel"
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(
            embed, text="Report options…", command=self._report_options_dialog
        ).grid(row=2, column=3, sticky="e", pady=(8, 0))
        output = ttk.LabelFrame(page, text="  3  ·  Output  ", style="Panel.TLabelframe")
        output.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        output.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            output, text="Save report and evidence in a different folder",
            variable=self.custom_output
        ).grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.output_folder).grid(
            row=0, column=1, sticky="ew", padx=(12, 8)
        )
        ttk.Button(
            output, text="Browse", command=lambda: self._dir(self.output_folder)
        ).grid(row=0, column=2)

        workspace = ttk.LabelFrame(
            page, text="  4  ·  Run and monitor  ", style="Panel.TLabelframe"
        )
        workspace.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(2, weight=1)
        action_row = ttk.Frame(workspace)
        action_row.grid(row=0, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)
        self.go = ttk.Button(
            action_row, text="Generate report  ·  Timestamp  ·  Verify",
            command=self.start, style="Accent.TButton", takefocus=True
        )
        self.go.grid(row=0, column=0, sticky="ew")
        self.stop = ttk.Button(
            action_row, text="Cancel", command=self.cancel_run,
            state="disabled", width=13
        )
        self.stop.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        progress = ttk.Frame(workspace, padding=(0, 14, 0, 8))
        progress.grid(row=1, column=0, sticky="ew")
        progress.columnconfigure(0, weight=1)
        self.run_stats = tk.StringVar(value="Waiting to start  ·  0%")
        ttk.Label(progress, text="LIVE RUN STATUS", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(progress, textvariable=self.run_stats, style="Muted.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        self.pb = ttk.Progressbar(progress, maximum=100, style="Horizontal.TProgressbar")
        self.pb.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 0))

        log_card = ttk.Frame(workspace)
        log_card.grid(row=2, column=0, sticky="nsew", pady=(4, 0))
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)
        log_toolbar = ttk.Frame(log_card)
        log_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(log_toolbar, text="Execution log", style="Section.TLabel").pack(side="left")
        ttk.Button(
            log_toolbar, text="Copy selected",
            command=lambda: self._copy_text_widget(self.log, False)
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            log_toolbar, text="Copy all",
            command=lambda: self._copy_text_widget(self.log, True)
        ).pack(side="right")
        log_box = ttk.Frame(log_card)
        log_box.grid(row=1, column=0, sticky="nsew")
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(0, weight=1)
        palette = branding.PALETTE
        self.log = tk.Text(
            log_box, height=12, wrap="word", background=palette["console_bg"],
            foreground=palette["console_fg"],
            insertbackground=palette["console_fg"],
            selectbackground=palette["console_select"],
            selectforeground=palette["on_accent"],
            font=self._fonts().font(branding.FONT_SIZES["small"], role="mono"),
            relief="flat", padx=12, pady=10
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log_scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.log_scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=self.log_scroll.set)

    def _build_settings_page(self):
        page = self.set_tab
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)
        self._page_heading(
            page, "Configuration", "Settings & trust",
            "Manage the local runtime, report generator and timestamp provider trust."
        )
        scroll_host = ttk.Frame(page)
        scroll_host.grid(row=3, column=0, sticky="nsew")
        scroll_host.columnconfigure(0, weight=1)
        scroll_host.rowconfigure(0, weight=1)
        canvas = tk.Canvas(scroll_host, background=branding.PALETTE["background"],
                           highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        inner = ttk.Frame(canvas, padding=(0, 0, 10, 12))
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
            add="+"
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
            add="+"
        )
        actual_page = self.set_tab
        self.set_tab = inner
        self._settings_ui()
        self.set_tab = actual_page
        self._bind_settings_mousewheel(canvas)

    @staticmethod
    def _bind_settings_mousewheel(canvas):
        def scroll(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            return "break"
        canvas.bind("<MouseWheel>", scroll, add="+")
        canvas.bind("<Button-4>", scroll, add="+")
        canvas.bind("<Button-5>", scroll, add="+")

    def _build_diagnostics_page(self):
        page = self.diag_tab
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)
        self._page_heading(
            page, "Operational assurance", "Diagnostics & evidence",
            "Run a preflight, inspect status and open the retained evidence package."
        )
        panel = ttk.Frame(page)
        panel.grid(row=3, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)
        actual_page = self.diag_tab
        self.diag_tab = panel
        self._diag_ui()
        self.diag_tab = actual_page
        palette = branding.PALETTE
        self.diag.configure(
            wrap="word", background=palette["console_bg"],
            foreground=palette["console_fg"],
            insertbackground=palette["console_fg"],
            selectbackground=palette["console_select"],
            selectforeground=palette["on_accent"],
            font=self._fonts().font(branding.FONT_SIZES["small"], role="mono"),
            relief="flat", padx=12, pady=10
        )

    def _refresh_filter_indicator(self):
        filters = getattr(self, "file_filters", None) or []
        selection = getattr(self, "file_selection", None) or []
        if not hasattr(self, "filter_summary"):
            return
        if selection:
            count = len(selection)
            noun = "file" if count == 1 else "files"
            self.filter_summary.set(
                f"{count} explicitly selected {noun} - the folder is only the evidence anchor"
            )
        elif not filters:
            self.filter_summary.set("none - every file in the folder is evidence")
        elif self.mode.get() != "combined":
            self.filter_summary.set(f"{file_filters.describe(filters)}  (ignored for a single file)")
        else:
            self.filter_summary.set(file_filters.describe(filters))

    def _clear_filter_indicator(self):
        self.file_filters = []
        self._refresh_filter_indicator()
        panel = getattr(self, "filter_panel", None)
        if panel is not None:
            try:
                panel.clear_filters()
            except tk.TclError:
                pass

    def _sync_input_mode(self):
        super()._sync_input_mode()
        self._refresh_filter_indicator()

    def _select_page(self, name):
        page = getattr(self, name)
        self.nb.select(page)
        self._on_page_changed()
        return "break"

    def _on_page_changed(self, _event=None):
        try:
            current = self.nb.select()
            for name, *_rest in self.NAV_ITEMS:
                page = getattr(self, name)
                selected = str(page) == current
                self._nav_buttons[name].configure(
                    style="NavSelected.TButton" if selected else "Nav.TButton",
                    image=self._nav_icons[name]["selected" if selected else "idle"],
                )
        except (AttributeError, tk.TclError):
            return

    def prog(self, n, stage):
        def apply():
            try:
                value = max(0, min(100, float(n)))
                self.pb.configure(value=value)
                self.status.set(f"{value:g}%  ·  {stage}")
                self.run_stats.set(f"{stage}  ·  {value:g}%")
                if hasattr(self, "_footer_status"):
                    self._footer_status.set(f"{value:g}%  ·  {stage}")
            except (ValueError, TypeError, tk.TclError):
                pass
        self.after(0, apply)

    def _build_footer(self):
        footer = ttk.Frame(self, padding=(14, 7, 14, 9))
        footer.pack(fill="x")
        self._footer_status = tk.StringVar(value="Workspace ready")
        ttk.Label(footer, textvariable=self._footer_status, style="Status.TLabel").pack(
            side="left", fill="x", expand=True
        )
        ttk.Label(
            footer,
            text=f"{branding.PRODUCT['footer']}  ·  {branding.PRODUCT['version_label']}",
            style="BrandSub.TLabel",
        ).pack(side="right", padx=(10, 0))
        ttk.Label(
            footer,
            text=f"{branding.PRODUCT['licence']}  ·  {branding.PRODUCT['campaign']}",
            style="BrandSub.TLabel",
        ).pack(side="bottom", anchor="e", pady=(4, 0))

    @staticmethod
    def _nav_text(number, title, subtitle):
        return f"{number}   {i18n.tr(title)}\n       {i18n.tr(subtitle)}"

    def _refresh_nav_text(self):
        try:
            for page, number, title, subtitle in self.NAV_ITEMS:
                self._nav_buttons[page].configure(text=self._nav_text(number, title, subtitle))
        except tk.TclError:
            pass

    def _live_clock(self):
        if hasattr(self, "_clock_text"):
            now = datetime.now().astimezone()
            self._clock_text.set(
                f"{now.day:02d} {i18n.month_abbr(now.month)} {now.year}  ·  {now:%H:%M:%S} UTC{now:%z}")
        self.after(1000, self._live_clock)


if __name__ == "__main__":
    app = ChronoSealDesktop()
    app.mainloop()
