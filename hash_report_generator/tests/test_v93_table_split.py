import io
import unittest
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from hash_report_generator.safe_table import PolicyTable

class PolicyTableTests(unittest.TestCase):
    def test_no_one_two_row_fragments(self):
        t=PolicyTable([[str(i)] for i in range(14)],rowHeights=[20]*14)
        for h in (30, 50, 60, 80, 100, 200, 250):
            parts=t.split(400,h)
            if len(parts)==2:
                self.assertGreaterEqual(len(parts[0]._cellvalues),3)
                self.assertGreaterEqual(len(parts[1]._cellvalues),3)
    def test_real_pdf_render(self):
        import fitz
        b=io.BytesIO()
        doc=SimpleDocTemplate(b,pagesize=A4,topMargin=50,bottomMargin=50)
        rows=[[f"Zeile {i} Ä Ö Ü ä ö ü ß",f"{i:064X}"] for i in range(80)]
        table=PolicyTable(rows,colWidths=[145,340],rowHeights=[18]*80)
        doc.build([table])
        pdf=fitz.open(stream=b.getvalue(),filetype="pdf")
        self.assertGreaterEqual(len(pdf),2)
        text="".join(page.get_text() for page in pdf)
        for i in range(80):
            self.assertIn(f"Zeile {i} ",text)
        self.assertIn("000000000000000000000000000000000000000000000000000000000000004F",text)

if __name__=="__main__": unittest.main()
