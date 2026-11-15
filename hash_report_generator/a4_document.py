"""Shared A4 ReportLab frame: removes the implicit 6pt inset on all four sides."""

# Unified report import bootstrap: supports script, GUI and package invocation.
import sys as _report_sys
from pathlib import Path as _report_Path
_report_dir = _report_Path(__file__).resolve().parent
for _report_path in (str(_report_dir.parent), str(_report_dir)):
    if _report_path not in _report_sys.path:
        _report_sys.path.insert(0, _report_path)



# Support direct execution from hash_report_generator and package imports.
import sys as _cs_sys
from pathlib import Path as _cs_Path
_cs_root = str(_cs_Path(__file__).resolve().parents[1])
if _cs_root not in _cs_sys.path:
    _cs_sys.path.insert(0, _cs_root)

from hash_report_generator.style_runtime import visual as _central_visual
from reportlab.platypus import SimpleDocTemplate, BaseDocTemplate, PageTemplate, Frame
from reportlab.platypus.doctemplate import _doNothing
from reportlab.pdfgen import canvas
try:
    from .pdf_object_rules import page_geometry
except ImportError:
    from pdf_object_rules import page_geometry

class A4DocTemplate(SimpleDocTemplate):
    """Enforce one canonical A4 body rectangle for every ReportLab profile."""
    def __init__(self, filename, **kwargs):
        g = page_geometry()
        required = dict(pagesize=(g['page_width_pt'],g['page_height_pt']),
            leftMargin=g['left_margin_pt'],rightMargin=g['right_margin_pt'],
            topMargin=g['top_margin_pt'],bottomMargin=g['bottom_margin_pt'])
        for key, value in required.items():
            if key in kwargs:
                supplied=kwargs[key]
                if key=='pagesize':
                    if any(abs(a-b)>0.01 for a,b in zip(supplied,value)):
                        raise ValueError('Noncanonical A4 page size')
                elif abs(supplied-value)>0.01:
                    raise ValueError(f'Noncanonical A4 margin: {key}')
            kwargs[key]=value
        super().__init__(filename, **kwargs)

    def _makePageTemplates(self, onFirstPage=_doNothing, onLaterPages=_doNothing):
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      id='normal', leftPadding=_central_visual('a4_document__L30__leftPadding'), rightPadding=_central_visual('a4_document__L30__rightPadding'),
                      topPadding=_central_visual('a4_document__L31__topPadding'), bottomPadding=_central_visual('a4_document__L31__bottomPadding'))
        return [PageTemplate(id='First', frames=frame, onPage=onFirstPage,
                             pagesize=self.pagesize, autoNextPageTemplate='Later'),
                PageTemplate(id='Later', frames=frame, onPage=onLaterPages,
                             pagesize=self.pagesize)]

    def build(self, flowables, onFirstPage=_doNothing, onLaterPages=_doNothing,
              canvasmaker=canvas.Canvas):
        self._calc()
        self.addPageTemplates(self._makePageTemplates(onFirstPage, onLaterPages))
        if onFirstPage is _doNothing and hasattr(self, 'onFirstPage'):
            self.pageTemplates[0].beforeDrawPage = self.onFirstPage
        if onLaterPages is _doNothing and hasattr(self, 'onLaterPages'):
            self.pageTemplates[1].beforeDrawPage = self.onLaterPages
        BaseDocTemplate.build(self, flowables, canvasmaker=canvasmaker)
