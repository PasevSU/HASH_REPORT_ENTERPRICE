"""Pre-seal page identity footer. Requires PyMuPDF, pypdf, reportlab.
Text digest = SHA256(NFC normalized page text, excluding this footer), UTF-8.
Must be applied BEFORE any RFC3161 timestamps; never edit signed PDF.
"""
from __future__ import annotations
import hashlib, io, re, unicodedata
from pathlib import Path
import fitz
from reportlab.lib import colors
from pypdf import PdfReader, PdfWriter, Transformation
from hash_report_generator.pdf_object_rules import display_hash
from reportlab.pdfgen import canvas

def _identity_rules():
    # Central JS configuration is mandatory; no silent local fallback.
    from hash_report_generator.style_loader import load_styles
    rules = load_styles()['PAGE_IDENTITY']
    if not isinstance(rules, dict):
        raise ValueError('PAGE_IDENTITY must be a style object')
    return rules

MARKER = 'PAGE TEXT HASHES'
HASH_ALGORITHMS = ('MD5','SHA-1','SHA-224','SHA-256','SHA-384','SHA-512','SHA3-224','SHA3-256','SHA3-384','SHA3-512','RIPEMD-160')
def all_hashes(data):
    values={}
    for name in HASH_ALGORITHMS:
        try: h=hashlib.new(name.lower().replace('sha3-', 'sha3_').replace('-', ''))
        except ValueError as exc: raise RuntimeError(f'Required digest unavailable: {name}') from exc
        h.update(data); values[name]=h.hexdigest()
    return values

def normalize_text(s):
    return unicodedata.normalize('NFC', s.replace('\r\n','\n').replace('\r','\n')).strip()

def _remove_legacy_center_pagination(doc, *, preserve_pages=()):
    """Remove only proven old page counters in the bottom-center margin.

    The old generator prints `N / total` around y=780 on A4; it must not
    coexist with the new document-wide counter. This runs on a temporary
    assembled PDF, never on the source. Fail closed on ambiguous matches.
    """
    removed=[]
    for index,page in enumerate(doc):
        if index in preserve_pages:
            continue
        rect=page.rect
        # Locate exact page counter, not a number within the report body.
        expected=re.compile(rf'(?<!\d){index+1}\s*/\s*\d+(?!\d)')
        candidates=[]
        for line in page.get_text('dict').get('blocks',[]):
            if 'lines' not in line: continue
            for item in line['lines']:
                spans=item.get('spans',[])
                text=''.join(span.get('text','') for span in spans).strip()
                box=fitz.Rect(item['bbox'])
                if (expected.fullmatch(text) and
                    rect.height*.88 < box.y0 < rect.height*.96 and
                    rect.width*.40 < (box.x0+box.x1)/2 < rect.width*.60):
                    candidates.append(box)
        if len(candidates)>1:
            raise ValueError(f'Page {index+1}: ambiguous legacy page numbers')
        if candidates:
            # Remove actual text operators, not merely cover with a white box.
            page.add_redact_annot(candidates[0]+(-1,-1,1,1), fill=(1,1,1))
            page.apply_redactions(images=0,graphics=0,text=0)
            removed.append(index+1)
    return removed

def apply_footer(src, dst, report_id, version, *, margin=None, preserve_pages=(),
                 source_pdf_signature_audit=None):
    rules = _identity_rules()
    from hash_report_generator.pdf_object_rules import font_name
    # Register Unicode fonts before either footer or checksum appendix is drawn.
    for role in ("regular", "bold", "monospace"):
        font_name(role)
    from hash_report_generator.style_loader import load_styles
    page_rules = load_styles()['PAGE']
    pt = 72 / 25.4
    left = page_rules['left_mm'] * pt
    right = rules['footer_right_margin_mm'] * pt
    separator_right = page_rules['right_mm'] * pt if rules['separator_use_page_margins'] else right
    page_width = page_rules['width_mm'] * pt
    page_height = page_rules['height_mm'] * pt
    if margin is not None and margin != page_rules['left_mm']:
        raise ValueError('Local margin overrides are forbidden: configure style/00_page.js')
    src, dst = Path(src), Path(dst)
    if src.resolve() == dst.resolve():
        raise ValueError('Input and output must differ')
    preserve_pages = frozenset(int(index) for index in preserve_pages)
    preserved_page_numbers = {index: number for number, index in enumerate(sorted(preserve_pages), 1)}
    doc = fitz.open(src)
    if any(index < 0 or index >= len(doc) for index in preserve_pages):
        doc.close()
        raise ValueError('preserve_pages contains an invalid zero-based page index')
    # Normalize legacy numbering in a disposable working copy before hashing.
    _remove_legacy_center_pagination(doc, preserve_pages=preserve_pages)
    # A previously composed ChronoSeal PDF may have an old footer. Remove it
    # only in the NEW visual copy; never modify the source or its signatures.
    # Identity strings come from the style rules, so a re-composed PDF always
    # loses its old footer even when the branding text changed.
    furniture = tuple(
        rules[key] for key in ('brand', 'license', 'developer', 'url')
        if isinstance(rules.get(key), str) and rules[key].strip()
    )
    for index,page in enumerate(doc):
        if index in preserve_pages:
            continue
        lines=page.get_text('dict').get('blocks', [])
        for block in lines:
            for line in block.get('lines', []):
                content=''.join(span.get('text','') for span in line.get('spans', []))
                box=fitz.Rect(line['bbox'])
                # Footer furniture is everything below the separator rule, so a
                # re-composed PDF loses its old footer whatever the footer geometry.
                if box.y0 > page.rect.height-rules['separator_y_pt'] and (
                    ('PAGE TEXT SHA-256' in content or 'PAGE TEXT HASHES' in content) or
                    'ChronoSeal v5.' in content or
                    'CRYPTO REPORT ENTERPRICE' in content or
                    any(text in content for text in furniture) or
                    re.fullmatch(r'[A-Fa-f0-9]{16,}',content.strip()) or
                    # Per-page hash rows are written as "ALGORITHM: <hex>".
                    re.fullmatch(r'[A-Za-z0-9_.-]{2,24}:\s*[A-Fa-f0-9]{16,}',content.strip()) or
                    re.fullmatch(r'\d+\s*/\s*\d+',content.strip()) or
                    re.fullmatch(r'RPT-[\w-]+',content.strip())
                ):
                    page.add_redact_annot(box+(-1,-1,1,1),fill=(1,1,1))
        if page.annots() is not None:
            page.apply_redactions(images=0,graphics=0,text=0)
    prepared = io.BytesIO(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    doc = fitz.open(stream=prepared.getvalue(), filetype='pdf')
    reader = PdfReader(prepared)
    if len(doc) != len(reader.pages): raise ValueError('Page count mismatch')
    writer = PdfWriter()
    manifest = []
    canonical_pages = [normalize_text(doc[i].get_text('text', sort=True)) for i in range(len(doc))]
    # Length-prefix framing prevents ambiguous page concatenation. The appendix is excluded.
    document_bytes = b''.join(len(t.encode('utf-8')).to_bytes(8, 'big') + t.encode('utf-8') for t in canonical_pages)
    document_hashes = all_hashes(document_bytes)
    total_pages = len(reader.pages) + 1
    source_page_hashes = []
    for idx, page in enumerate(reader.pages):
        text = normalize_text(doc[idx].get_text('text', sort=True))
        if MARKER in text: raise ValueError('Footer already present: refuse double stamping')
        page_hashes = all_hashes(text.encode('utf-8'))
        digest = page_hashes['SHA-256']
        box = page.mediabox
        width, height = float(box.width), float(box.height)
        preserved_source_page = idx in preserve_pages
        if not preserved_source_page and (abs(width-page_width)>1 or abs(height-page_height)>1):
            raise ValueError(
                f'Page {idx+1}: not canonical A4; no implicit resizing; '
                f'MediaBox={tuple(round(float(v), 3) for v in (box.left, box.bottom, box.right, box.top))}; '
                f'actual={width:.3f}x{height:.3f}pt; expected={page_width:.3f}x{page_height:.3f}pt; '
                f'CropBox={tuple(round(float(v), 3) for v in (page.cropbox.left, page.cropbox.bottom, page.cropbox.right, page.cropbox.top))}; '
                f'Rotate={page.get("/Rotate", 0)}; source={src}')
        # Require a reserved footer strip: refuse covering existing text.
        words = doc[idx].get_text('words')
        collision_words = [] if preserved_source_page else [
            w for w in words if w[3] > height-rules['collision_boundary_from_bottom_pt']
        ]
        collision = bool(collision_words)
        if collision:
            samples = [{'text': str(w[4])[:100], 'bbox_top_pt': round(w[1], 2),
                        'bbox_bottom_pt': round(w[3], 2)} for w in collision_words[:12]]
            raise ValueError(
                f'Page {idx+1}: content overlaps footer zone; '
                f'boundary_y_from_top={height-rules["collision_boundary_from_bottom_pt"]:.2f}pt; '
                f'colliding_words={len(collision_words)}; samples={samples!r}; '
                'fix upstream pagination; original imported PDFs may require a separate appendix, no automatic scaling')
        footer_extension = 0.0
        if preserved_source_page:
            # No scaling: the original page is placed unchanged on a taller
            # canvas whose added bottom strip carries the footer.
            if int(page.get('/Rotate', 0) or 0):
                page.transfer_rotation_to_content()
                box = page.mediabox
                width, height = float(box.width), float(box.height)
            footer_extension = float(rules['collision_boundary_from_bottom_pt'])
            extended = writer.add_blank_page(width=width, height=height + footer_extension)
            extended.merge_transformed_page(
                page, Transformation().translate(-float(box.left), -float(box.bottom) + footer_extension))
            page = extended
            height += footer_extension
            source_page_hashes.append({
                'source_page_index': idx + 1,
                'source_pdf_page': preserved_page_numbers[idx],
                'document_page_index': idx + 1,
                'text_sha256': digest,
                'text_hashes': page_hashes,
                'page_size_pt': [width, height - footer_extension],
                'footer_extension_pt': footer_extension,
                'text': text,
            })
        else:
            page = writer.add_page(page)
        stream = io.BytesIO()
        c = canvas.Canvas(stream, pagesize=(width,height))
        # Thin separator above the reserved footer strip, inside 20 mm margins.
        c.setStrokeColor(colors.HexColor(rules['separator_color']))
        c.setLineWidth(rules['separator_width_pt'])
        c.line(left, rules['separator_y_pt'], width-separator_right, rules['separator_y_pt'])
        c.setStrokeColorRGB(0, 0, 0)
        # Six per-page algorithms, tiny but searchable text. The other five
        # are also calculated and retained in the returned manifest.
        c.setFont(rules['font_regular'], rules['footer_hash_font_pt'])
        c.drawString(rules['footer_left_x_pt'], rules['footer_heading_y_pt'], 'PAGE TEXT HASHES (UTF-8 / NFC; footer excluded)')
        # Tight baseline spacing: all six hashes in the lower-left corner.
        for j, name in enumerate(HASH_ALGORITHMS[:6]):
            c.drawString(rules['footer_left_x_pt'], rules['footer_hash_start_y_pt']-j*rules['footer_hash_leading_pt'], f'{name}: {display_hash(page_hashes[name])}')
        # Identity zone: one consistent three-line signature on every page.
        c.setFont(rules['font_regular'], rules['footer_id_font_pt'])
        c.drawRightString(width-right, rules['footer_id_y_pt'], report_id)
        c.setFont(rules['font_bold'], rules['footer_page_font_pt'])
        c.drawCentredString(width/2, rules['footer_page_y_pt'], f'{idx+1} / {total_pages}')
        c.setFont(rules['font_bold'], rules['footer_brand_font_pt'])
        c.drawRightString(width-right, rules['footer_brand_y_pt'], rules['brand'])
        c.setFont(rules['font_regular'], rules['footer_other_font_pt'])
        c.drawRightString(width-right, rules['footer_license_y_pt'], rules['license'])
        c.setFillColorRGB(0.12, 0.28, 0.46)
        c.drawRightString(width-right, rules['footer_developer_y_pt'], rules['developer'])
        c.drawRightString(width-right, rules['footer_url_y_pt'], rules['url'])
        c.setFillColorRGB(0, 0, 0)
        c.save(); stream.seek(0)
        overlay = PdfReader(stream).pages[0]
        page.merge_page(overlay)
        manifest.append({'page':idx+1,'text_sha256':digest,'text_hashes':page_hashes,'algorithm':'SHA-256','normalization':'PyMuPDF sorted text, Unicode NFC, LF, strip; footer excluded', 'layout_adjusted':collision,
                         'preserved_original_page':preserved_source_page,'footer_applied':True,
                         'footer_extension_pt':footer_extension})
    doc.close()
    imported_texts = [item.pop('text') for item in source_page_hashes]
    imported_bytes = b''.join(len(t.encode('utf-8')).to_bytes(8, 'big') + t.encode('utf-8') for t in imported_texts)
    imported_hashes = all_hashes(imported_bytes) if imported_texts else {}
    # One final, explicitly excluded summary page avoids self-referential hashing.
    stream=io.BytesIO()
    c=canvas.Canvas(stream, pagesize=(page_width,page_height))
    combined = bool(source_page_hashes)
    c.setFont(rules['font_bold'], rules['appendix_heading_font_pt'])
    if combined:
        c.drawString(left,rules['appendix_heading_y_pt'],rules['combined_appendix_title'])
        c.setFont(rules['font_regular'],rules['appendix_body_font_pt'])
        c.drawString(left,rules['appendix_intro_ys_pt'][0],rules['document_appendix_scope'])
        c.drawString(left,rules['appendix_intro_ys_pt'][1],rules['document_appendix_encoding'])
        c.drawString(left,rules['appendix_intro_ys_pt'][2],rules['document_appendix_framing'])
    else:
        c.drawString(left,rules['appendix_heading_y_pt'],rules['document_appendix_title'])
        c.setFont(rules['font_regular'],rules['appendix_body_font_pt'])
        c.drawString(left,rules['appendix_intro_ys_pt'][0],rules['document_appendix_scope'])
        c.drawString(left,rules['appendix_intro_ys_pt'][1],rules['document_appendix_encoding'])
        c.drawString(left,rules['appendix_intro_ys_pt'][2],rules['document_appendix_framing'])
        c.drawString(left,rules['appendix_intro_ys_pt'][3],rules['document_appendix_page_count'].format(page_count=len(reader.pages)))
    # All presentation values come from the shared table JS rule.
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from hash_report_generator.pdf_object_rules import GlobalReportTable, table_relief_commands
    from hash_report_generator.style_loader import load_styles
    from xml.sax.saxutils import escape
    all_table_rules = load_styles()
    table_rules = all_table_rules['CHECKSUM_APPENDIX_TABLE']
    profile = all_table_rules['GLOBAL_TABLE_PROFILE']
    metrics = all_table_rules['CORE_REPORT_METRICS']
    from hash_report_generator.pdf_object_rules import reportlab_table_style, table_header_paragraph
    class AppendixTable(GlobalReportTable):
        pass
    # Same body paragraph as the FILE INFORMATION tables on pages 1-3.
    cell_style = ParagraphStyle('ChecksumDigest', fontName=font_name('regular'),
        fontSize=metrics['FONT_SIZE_TABLE_TEXT'], leading=metrics['LEADING_TABLE_TEXT'],
        textColor=colors.HexColor(profile['body_text_color']))
    label_style = ParagraphStyle('ChecksumLabel', parent=cell_style)
    chunk = profile['hash_chunk_chars']
    from reportlab.pdfbase.pdfmetrics import stringWidth
    def digest_cell(value):
        # Presentation-only wrap, one character before the cell border; the digest stays intact.
        from hash_report_generator.pdf_object_rules import display_hash
        value = display_hash(value)
        value_width = available_width*ratios[1]
        limit = value_width - 2*profile['cell_padding_pt'] - stringWidth('0', cell_style.fontName, cell_style.fontSize)
        lines, line = [], ''
        for ch in value:
            if line and stringWidth(line+ch, cell_style.fontName, cell_style.fontSize) > limit:
                lines.append(line); line = ''
            line += ch
        lines.append(line)
        return Paragraph('<br/>'.join(escape(l) for l in lines), cell_style)
    available_width = page_width-left-page_rules['right_mm']*pt-profile['shadow_clearance_pt']
    ratios = list(all_table_rules['COLUMNS']['hashes'].values())
    def build_table(hashes):
        rows_ = [[table_header_paragraph(rules['appendix_property_header']), table_header_paragraph(rules['appendix_value_header'])]] + [[Paragraph(escape(name), label_style), digest_cell(hashes[name])] for name in HASH_ALGORITHMS]
        t = AppendixTable(rows_, colWidths=[available_width*r for r in ratios],
                          repeatRows=int(profile['header_repeat_rows']))
        t.setStyle(reportlab_table_style('hashes'))
        return t
    if len(ratios) != 2 or abs(sum(ratios)-1)>1e-8 or chunk <= 0:
        raise ValueError('Invalid global COLUMNS.hashes JS configuration')
    if combined:
        gap = rules['combined_section_gap_pt']
        line_h = rules['combined_line_leading_pt']
        def section(top, heading, lines):
            c.setFont(rules['font_bold'], rules['combined_heading_font_pt'])
            c.setFillColor(colors.HexColor(profile['body_text_color']))
            c.drawString(left, top, heading)
            y = top - rules['combined_heading_gap_pt']
            c.setFont(rules['font_regular'], rules['appendix_body_font_pt'])
            for text_line in lines:
                c.drawString(left, y, text_line); y -= line_h
            return y
        y = section(rules['combined_file_heading_y_pt'], rules['combined_file_heading'],
                    [rules['document_appendix_page_count'].format(page_count=len(reader.pages))])
        table = build_table(document_hashes)
        _, th = table.wrapOn(c, available_width, table_rules['available_height_pt'])
        table.drawOn(c, left, y - th)
        y = y - th - gap
        y = section(y, rules['combined_pdf_heading'], [
            rules['source_appendix_reference'].format(
                first_page=source_page_hashes[0]['document_page_index'],
                last_page=source_page_hashes[-1]['document_page_index'],
                source_page_count=len(source_page_hashes)),
            rules['source_appendix_scope']])
        source_table = build_table(imported_hashes)
        _, sh = source_table.wrapOn(c, available_width, table_rules['available_height_pt'])
        source_table.drawOn(c, left, y - sh)
        y = y - sh - rules['combined_notes_gap_pt']
        signature_count = len((source_pdf_signature_audit or {}).get('signatures', []))
        notes = [rules['appendix_note_page_values'], rules['appendix_note_all_algorithms'],
                 rules['appendix_note_scope'], rules['source_appendix_note'],
                 rules['source_appendix_signature_status'].format(
                     status=(source_pdf_signature_audit or {}).get('verification_status', 'NO_SIGNATURES_DETECTED'),
                     signature_count=signature_count),
                 rules['source_appendix_signature_scope']]
        c.setFont(rules['font_regular'], rules['appendix_note_font_pt'])
        for note in notes:
            y -= rules['combined_note_leading_pt']
            c.drawString(left, y, note)
        if y < rules['combined_min_bottom_pt']:
            raise ValueError('Combined text checksum page exceeds available height')
    else:
        table = build_table(document_hashes)
        tw,th=table.wrapOn(c,available_width,table_rules['available_height_pt'])
        if th > table_rules['available_height_pt']:
            raise ValueError('Checksum appendix table exceeds configured available height')
        table.drawOn(c,left,rules['appendix_table_top_pt']-th)
        c.setFont(rules['font_regular'],rules['appendix_note_font_pt'])
        c.drawString(left,rules['appendix_notes_y_pt'][0],rules['appendix_note_page_values'])
        c.drawString(left,rules['appendix_notes_y_pt'][1],rules['appendix_note_all_algorithms'])
        c.drawString(left,rules['appendix_notes_y_pt'][2],rules['appendix_note_scope'])
    c.setStrokeColor(colors.HexColor(rules['separator_color']))
    c.setLineWidth(rules['separator_width_pt'])
    c.line(left,rules['separator_y_pt'],page_width-separator_right,rules['separator_y_pt'])
    c.setStrokeColorRGB(0,0,0)
    c.setFont(rules['font_regular'],rules['footer_id_font_pt'])
    c.drawRightString(page_width-right,rules['footer_id_y_pt'],report_id)
    c.setFont(rules['font_bold'],rules['footer_page_font_pt'])
    c.drawCentredString(page_width/2,rules['footer_page_y_pt'],f'{len(reader.pages)+1} / {total_pages}')
    c.setFont(rules['font_bold'],rules['footer_brand_font_pt'])
    c.drawRightString(page_width-right,rules['footer_brand_y_pt'],rules['brand'])
    c.setFont(rules['font_regular'],rules['footer_other_font_pt'])
    c.drawRightString(page_width-right,rules['footer_license_y_pt'],rules['license'])
    c.setFillColorRGB(0.12,0.28,0.46)
    c.drawRightString(page_width-right,rules['footer_developer_y_pt'],rules['developer'])
    c.drawRightString(page_width-right,rules['footer_url_y_pt'],rules['url'])
    c.setFillColorRGB(0,0,0)
    c.save();stream.seek(0)
    writer.add_page(PdfReader(stream).pages[0])
    manifest.append({'document_text_hashes':document_hashes,'scope':'report and preserved imported PDF pages; appendices and footer excluded','page_count':len(reader.pages),'framing':'8-byte big-endian length per UTF-8 page','imported_pdf_pages':source_page_hashes})
    for source_item in ([{'text_hashes':imported_hashes,'text_sha256':imported_hashes.get('SHA-256'),'source_pdf_page':'ALL','document_page_index':[i['document_page_index'] for i in source_page_hashes]}] if source_page_hashes else []):
        source_page = source_item['source_pdf_page']
        appendix_number = len(writer.pages)
        manifest.append({
            'source_page_text_hashes':source_item['text_hashes'],
            'source_page_sha256':source_item['text_sha256'],
            'source_page_index':source_page,
            'document_page_index':source_item['document_page_index'],
            'identity_appendix_page':appendix_number,
            'scope':'source page text before footer; appendix excluded',
        })
    with dst.open('wb') as f: writer.write(f)
    return manifest
