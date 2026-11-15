"""Non-mutating audit of local PDF layout values. Exit nonzero only on known regressions."""
from pathlib import Path
import re, json
ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
  "page_geometry": r"\b(?:leftMargin|rightMargin|topMargin|bottomMargin|pagesize)\s*=",
  "table_width": r"\bcolWidths\s*=",
  "spacer": r"\bSpacer\s*\(",
  "style": r"\b(?:ParagraphStyle|TableStyle)\s*\(",
  "page_break": r"\bPageBreak\s*\(",
  "canvas_coordinate": r"\b(?:drawString|drawRightString|drawCentredString|rect|line)\s*\("
}
findings=[]
for path in ROOT.rglob("*.py"):
    if "tests" in path.parts or "tools" in path.parts: continue
    for n,line in enumerate(path.read_text(encoding="utf-8",errors="replace").splitlines(),1):
        for name,pattern in PATTERNS.items():
            if re.search(pattern,line): findings.append({"file":str(path.relative_to(ROOT)),"line":n,"category":name,"source":line.strip()[:200]})
if __name__=="__main__":
    print(json.dumps({"remaining_candidates":len(findings),"findings":findings},ensure_ascii=False,indent=2))
