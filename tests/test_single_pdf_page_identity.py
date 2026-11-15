import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import fitz
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, ByteStringObject, DictionaryObject, NameObject, NumberObject,
    TextStringObject,
)
from reportlab.pdfgen import canvas

from chronoseal.page_identity import normalize_text
from chronoseal.pdf_preflight import inspect_pdf
from chronoseal.pipeline import Pipeline


class SinglePdfPageIdentityTests(unittest.TestCase):
    def test_signed_and_timestamped_source_is_embedded_byte_exact_with_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / 'RPT-20261009-54321-ABCD_HASHREPORT_TYP_SINGLE.pdf'
            source = root / 'signed-source.pdf'
            case = root / 'case'
            case.mkdir()

            report_canvas = canvas.Canvas(str(report), pagesize=(595.2756, 841.8898))
            report_canvas.drawString(80, 720, 'Report containing signed source')
            report_canvas.save()
            source_canvas = canvas.Canvas(str(source), pagesize=(595.2756, 841.8898))
            source_canvas.drawString(80, 720, 'Signed source PDF content')
            source_canvas.save()

            base = PdfReader(str(source), strict=True)
            source_writer = PdfWriter(clone_from=base)
            signature = DictionaryObject({
                NameObject('/Type'): NameObject('/Sig'),
                NameObject('/SubFilter'): NameObject('/ETSI.CAdES.detached'),
                NameObject('/ByteRange'): ArrayObject([
                    NumberObject(0), NumberObject(100), NumberObject(200), NumberObject(50),
                ]),
                NameObject('/Contents'): ByteStringObject(b'synthetic-signature'),
            })
            field = DictionaryObject({
                NameObject('/FT'): NameObject('/Sig'),
                NameObject('/T'): TextStringObject('ExistingSignature'),
                NameObject('/V'): source_writer._add_object(signature),
            })
            source_writer._root_object.update({
                NameObject('/AcroForm'): DictionaryObject({
                    NameObject('/Fields'): ArrayObject([source_writer._add_object(field)]),
                }),
                NameObject('/Perms'): DictionaryObject({
                    NameObject('/DocTimeStamp'): source_writer._add_object(DictionaryObject({
                        NameObject('/Type'): NameObject('/DocTimeStamp'),
                        NameObject('/SubFilter'): NameObject('/ETSI.RFC3161'),
                        NameObject('/ByteRange'): ArrayObject([
                            NumberObject(0), NumberObject(100), NumberObject(200), NumberObject(50),
                        ]),
                    })),
                }),
            })
            with source.open('wb') as stream:
                source_writer.write(stream)
            original_bytes = source.read_bytes()

            inventory = inspect_pdf(source)
            self.assertEqual(inventory['verification_status'], 'SIGNATURES_PRESENT_NOT_CRYPTOGRAPHICALLY_VALIDATED')
            self.assertEqual(len(inventory['signatures']), 2)
            self.assertEqual(
                {signature['subfilter'] for signature in inventory['signatures']},
                {'/ETSI.CAdES.detached', '/ETSI.RFC3161'},
            )

            output = Pipeline(root, {}, log=lambda _message: None)._compose(
                report, source, case, include_source_pdf=True,
            )
            result = PdfReader(str(output), strict=True)
            embedded = result.attachments['signed-source.pdf'][0]
            self.assertEqual(embedded, original_bytes)
            appendix_text = result.pages[len(result.pages) - 1].extract_text()
            self.assertIn('Source signature objects detected: 2', appendix_text)
            self.assertIn('does not validate signatures', appendix_text)
            audit = json.loads((case / 'source-pdf-signature-audit.json').read_text(encoding='utf-8'))
            self.assertTrue(audit['attachment_sha256_verified'])
            self.assertEqual(audit['source_signature_audit']['verification_status'],
                             'SIGNATURES_PRESENT_NOT_CRYPTOGRAPHICALLY_VALIDATED')
            self.assertIn('not these derived visible pages', audit['visible_page_copy_note'])

    def test_imported_pages_are_preserved_and_get_page_hash_appendices(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / 'RPT-20261009-12345-ABCD_HASHREPORT_TYP_SINGLE.pdf'
            source = root / 'source.pdf'
            case = root / 'case'
            case.mkdir()

            report_canvas = canvas.Canvas(str(report), pagesize=(595.2756, 841.8898))
            report_canvas.drawString(80, 720, 'Hash report body')
            report_canvas.save()

            source_canvas = canvas.Canvas(str(source), pagesize=(500, 700))
            source_canvas.drawString(45, 680, 'Original source content near page edge')
            source_canvas.drawString(45, 20, 'Original source footer that must not be covered')
            source_canvas.showPage()
            source_canvas.setPageSize((500, 700))
            source_canvas.drawString(45, 640, 'Second source page')
            source_canvas.save()
            source_bytes = source.read_bytes()
            source_hash = hashlib.sha256(source_bytes).hexdigest()

            output = Pipeline(root, {}, log=lambda _message: None)._compose(
                report, source, case, include_source_pdf=True,
            )
            result = PdfReader(str(output), strict=True)
            self.assertEqual(len(result.pages), 4)
            self.assertIn('1 / 4', result.pages[0].extract_text())
            self.assertIn('Original source footer', result.pages[1].extract_text())
            self.assertIn('PAGE TEXT HASHES', result.pages[1].extract_text())
            self.assertIn('2 / 4', result.pages[1].extract_text())
            last_text = result.pages[3].extract_text()
            for expected in ('TEXT CHECKSUMS', 'FILE TEXT', 'PDF TEXT', '4 / 4'):
                self.assertIn(expected, last_text)
            with fitz.open(str(output)) as checked:
                for appendix_index in (3,):
                    page = checked[appendix_index]
                    limit = page.rect.width - 20 / 25.4 * 72
                    drawing_right = max(d['rect'].x1 for d in page.get_drawings() if d['rect'].width < page.rect.width * 0.95 or d['rect'].x1 <= limit + 1)
                    self.assertLessEqual(drawing_right, limit + 1)

            embedded = result.attachments['source.pdf']
            self.assertEqual(hashlib.sha256(embedded[0]).hexdigest(), source_hash)
            original = PdfReader(str(source), strict=True)
            for page_index, source_page in enumerate(original.pages):
                visible_page = result.pages[page_index + 1]
                self.assertAlmostEqual(
                    float(visible_page.mediabox.width),
                    float(source_page.mediabox.width),
                    places=2,
                )
                self.assertAlmostEqual(
                    float(visible_page.mediabox.height),
                    float(source_page.mediabox.height) + 91,
                    places=2,
                )

            identity = json.loads((case / 'page-identity.json').read_text(encoding='utf-8'))
            self.assertEqual(identity['pages'], 4)
            source_entries = [
                entry for entry in identity['page_manifest']
                if entry.get('preserved_original_page')
            ]
            self.assertEqual(len(source_entries), 2)
            with fitz.open(source) as original_pages:
                for index, entry in enumerate(source_entries):
                    text = normalize_text(original_pages[index].get_text('text', sort=True))
                    expected = hashlib.sha256(text.encode('utf-8')).hexdigest()
                    self.assertEqual(entry['text_sha256'], expected)


if __name__ == '__main__':
    unittest.main()
