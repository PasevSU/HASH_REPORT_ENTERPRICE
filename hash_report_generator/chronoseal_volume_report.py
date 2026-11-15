"""Read-only Volume evidence section; no additional output files."""
import json
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer

# Support package imports and direct execution from an unrelated working directory.
_REPORT_DIR = Path(__file__).resolve().parent
for _IMPORT_ROOT in (_REPORT_DIR.parent, _REPORT_DIR):
    if str(_IMPORT_ROOT) not in sys.path:
        sys.path.insert(0, str(_IMPORT_ROOT))

try:
    from .style_loader import load_styles
    from .pdf_object_rules import volume_block_table_style, block_heading, block_data_style
except ImportError:
    from style_loader import load_styles
    from pdf_object_rules import volume_block_table_style, block_heading, block_data_style

def _fallback_volume(path):
    """Probe the storage of the working folder when the pipeline did not provide it."""
    if not path:
        return None
    try:
        from chronoseal.storage_identity import inspect_storage
        return inspect_storage(Path(path))
    except Exception:
        return None


def append_volume_section(story, style, fallback_path=None):
    raw=os.environ.get('CHRONOSEAL_VOLUME_JSON')
    if raw:
        data=json.loads(raw)
    else:
        data=_fallback_volume(fallback_path)
        if not data: return
    rules=load_styles()
    block=rules['INFORMATION_BLOCK_STYLE']
    typography=block['volume_typography']
    volume_style=block_data_style(style)
    story.append(block_heading('Volume'))
    from pathlib import PureWindowsPath
    requested=str(data.get('requested_path') or data.get('probed_directory') or '')
    if os.path.isfile(requested) or (not os.path.isdir(requested) and PureWindowsPath(requested).suffix):
        requested=str(PureWindowsPath(requested).parent)
    path=PureWindowsPath(requested)
    short=(str(path.drive)+'\\...\\'+path.name) if path.drive and path.name else (path.name or requested)
    guid=str(data.get('volume_guid_path') or '').replace('\\\\?\\Volume{','').strip('}\\')
    entries=(('Working Folder',short),('Volume GUID',guid),('Mounted On',data.get('volume_mount_point')),('Filesystem',data.get('filesystem_name')),('Volume Serial',data.get('volume_serial_number')))
    for label,val in entries:
        if val:
            story.append(Paragraph(f'<b>{escape(label)}:</b> {escape(str(val))}',volume_style))
