"""COMBO_PDF / COMBO_ALL_PDF: an embedded document on the first or last pages.

The pipeline embeds exactly like SINGLE_PDF: the original file is attached
byte-exact, its pages are shown unmodified, and the footer only adds canvas space.
The difference is the position selector and the published report name.
"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from chronoseal.pipeline import Pipeline, PipelineError

A4 = (595.2756, 841.8898)


def _report(path, text='Hash report body'):
    page = canvas.Canvas(str(path), pagesize=A4)
    page.drawString(80, 720, text)
    page.save()
    return path


def _source(path, pages=2, size=(500, 700)):
    page = canvas.Canvas(str(path), pagesize=size)
    for number in range(1, pages + 1):
        page.setPageSize(size)
        page.drawString(45, 680, f'Original source page {number}')
        page.drawString(45, 20, 'Original source footer that must not be covered')
        page.showPage()
    page.save()
    return path


class ComboPdfComposeTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.case = self.root / 'case'
        self.case.mkdir()
        self.pipeline = Pipeline(self.root, {}, log=lambda _message: None)
        self.report = _report(self.root / 'RPT-20261116-00001-ABCD_HASHREPORT_TYP_COMBO.pdf')
        self.source = _source(self.root / 'Anlage.pdf')

    def tearDown(self):
        self._temporary.cleanup()

    def test_embedded_document_is_placed_before_the_report_on_request(self):
        source_bytes = self.source.read_bytes()
        output = self.pipeline._compose(
            self.report, self.root, self.case,
            embed_pdf=self.source, embed_position='before',
        )
        result = PdfReader(str(output), strict=True)
        self.assertEqual(len(result.pages), 4)
        self.assertIn('Original source page 1', result.pages[0].extract_text())
        self.assertIn('Original source page 2', result.pages[1].extract_text())
        self.assertIn('Hash report body', result.pages[2].extract_text())
        self.assertIn('1 / 4', result.pages[0].extract_text())
        self.assertIn('3 / 4', result.pages[2].extract_text())
        appendix = result.pages[3].extract_text()
        self.assertIn('TEXT CHECKSUMS', appendix)
        self.assertIn('4 / 4', appendix)
        self.assertEqual(result.attachments['Anlage.pdf'][0], source_bytes)

    def test_embedded_document_is_placed_after_the_report_on_request(self):
        output = self.pipeline._compose(
            self.report, self.root, self.case,
            embed_pdf=self.source, embed_position='after',
        )
        result = PdfReader(str(output), strict=True)
        self.assertEqual(len(result.pages), 4)
        self.assertIn('Hash report body', result.pages[0].extract_text())
        self.assertIn('Original source page 1', result.pages[1].extract_text())
        self.assertIn('Original source page 2', result.pages[2].extract_text())
        self.assertIn('4 / 4', result.pages[3].extract_text())

    def test_embedded_document_keeps_its_own_geometry_and_byte_identity(self):
        source_bytes = self.source.read_bytes()
        output = self.pipeline._compose(
            self.report, self.root, self.case,
            embed_pdf=self.source, embed_position='before',
        )
        result = PdfReader(str(output), strict=True)
        original = PdfReader(str(self.source), strict=True)
        for index, page in enumerate(original.pages):
            visible = result.pages[index]
            self.assertAlmostEqual(float(visible.mediabox.width), float(page.mediabox.width), places=2)
            # Only the reserved footer strip is added; nothing is scaled.
            self.assertAlmostEqual(
                float(visible.mediabox.height), float(page.mediabox.height) + 91, places=2,
            )
        self.assertEqual(
            hashlib.sha256(result.attachments['Anlage.pdf'][0]).hexdigest(),
            hashlib.sha256(source_bytes).hexdigest(),
        )
        audit = json.loads((self.case / 'embedded-original.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['embed_position'], 'before')
        self.assertEqual(audit['first_visible_page'], 1)
        self.assertEqual(audit['filename'], 'Anlage.pdf')
        identity = json.loads((self.case / 'page-identity.json').read_text(encoding='utf-8'))
        self.assertEqual(identity['pages'], 4)
        self.assertEqual(identity['sections'][0]['kind'], 'source_pdf')
        self.assertEqual(identity['sections'][0]['placement'], 'before')
        self.assertEqual(identity['sections'][0]['first_page'], 1)
        preserved = [entry for entry in identity['page_manifest'] if entry.get('preserved_original_page')]
        self.assertEqual(len(preserved), 2)
        self.assertEqual([entry['page'] for entry in preserved], [1, 2])

    def test_after_position_keeps_the_established_single_pdf_section_order(self):
        output = self.pipeline._compose(
            self.report, self.root, self.case,
            embed_pdf=self.source, embed_position='after',
        )
        identity = json.loads((self.case / 'page-identity.json').read_text(encoding='utf-8'))
        self.assertEqual([section['kind'] for section in identity['sections']],
                         ['report', 'source_pdf'])
        self.assertEqual(identity['sections'][1]['placement'], 'after')
        self.assertEqual(identity['sections'][1]['first_page'], 2)
        self.assertTrue(PdfReader(str(output), strict=True).pages)

    def test_explanation_stays_with_the_report_whichever_position_is_chosen(self):
        explanation = self.root / 'RPT-20261116-00001-ABCD_HASHREPORT_TYP_COMBO_ERLAEUTERUNG.pdf'
        _report(explanation, 'Explanation body')
        output = self.pipeline._compose(
            self.report, self.root, self.case,
            include_explanation=True, embed_pdf=self.source, embed_position='before',
        )
        result = PdfReader(str(output), strict=True)
        self.assertEqual(len(result.pages), 5)
        self.assertIn('Original source page 1', result.pages[0].extract_text())
        self.assertIn('Hash report body', result.pages[2].extract_text())
        self.assertIn('Explanation body', result.pages[3].extract_text())
        self.assertIn('5 / 5', result.pages[4].extract_text())

    def test_single_pdf_default_position_is_unchanged(self):
        output = self.pipeline._compose(
            self.report, self.source, self.case, include_source_pdf=True,
        )
        result = PdfReader(str(output), strict=True)
        self.assertIn('Hash report body', result.pages[0].extract_text())
        self.assertIn('Original source page 1', result.pages[1].extract_text())

    def test_unknown_position_is_refused_instead_of_guessed(self):
        with self.assertRaises(PipelineError) as caught:
            self.pipeline._compose(
                self.report, self.root, self.case,
                embed_pdf=self.source, embed_position='middle',
            )
        self.assertIn('EMBED_POSITION_INVALID', str(caught.exception))

    def test_embed_source_must_be_a_readable_pdf(self):
        text = self.root / 'notes.txt'
        text.write_text('not a pdf', encoding='utf-8')
        with self.assertRaises(PipelineError) as caught:
            self.pipeline._compose(self.report, self.root, self.case, embed_pdf=text)
        self.assertIn('EMBED_PDF_SOURCE_INVALID', str(caught.exception))

    def test_embedding_an_encrypted_pdf_is_refused(self):
        from pypdf import PdfWriter
        locked = self.root / 'locked.pdf'
        writer = PdfWriter(clone_from=str(self.source))
        writer.encrypt('secret')
        with locked.open('wb') as stream:
            writer.write(stream)
        with self.assertRaises(PipelineError) as caught:
            self.pipeline._compose(self.report, self.root, self.case, embed_pdf=locked)
        self.assertIn('COMBO_PDF_SOURCE_ENCRYPTED', str(caught.exception))


class ComboPdfRunGuardTests(unittest.TestCase):
    """The run-level guards fire before any evidence work starts."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.folder = self.root / 'evidence'
        self.folder.mkdir()
        (self.folder / 'a.txt').write_text('evidence', encoding='utf-8')
        self.embedded = _source(self.root / 'Anlage.pdf')
        self.pipeline = Pipeline(self.root, {}, log=lambda _message: None)

    def tearDown(self):
        self._temporary.cleanup()

    def test_position_must_be_before_or_after(self):
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(self.folder, embed_pdf=self.embedded, embed_position='top')
        self.assertIn('EMBED_POSITION_INVALID', str(caught.exception))

    def test_single_file_embedding_and_a_chosen_pdf_cannot_be_combined(self):
        single = _report(self.root / 'RPT-20261116-00002-ABCD_HASHREPORT_TYP_SINGLE.pdf')
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(single, include_source_pdf=True, embed_pdf=self.embedded)
        self.assertIn('EITHER the single-file PDF or a chosen PDF', str(caught.exception))

    def test_combo_embedding_requires_a_folder_or_file_list(self):
        single = _report(self.root / 'RPT-20261116-00003-ABCD_HASHREPORT_TYP_SINGLE.pdf')
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(single, embed_pdf=self.embedded)
        self.assertIn('COMBO+PDF requires a folder', str(caught.exception))

    def test_embed_source_that_is_not_a_pdf_is_refused(self):
        text = self.root / 'notes.txt'
        text.write_text('not a pdf', encoding='utf-8')
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(self.folder, embed_pdf=text)
        self.assertIn('EMBED_PDF_SOURCE_INVALID', str(caught.exception))

    def test_missing_embed_source_is_refused(self):
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(self.folder, embed_pdf=self.root / 'absent.pdf')
        self.assertIn('EMBED_PDF_SOURCE_INVALID', str(caught.exception))

    def test_the_evidence_folder_itself_cannot_be_the_embedded_document(self):
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(self.folder, embed_pdf=self.folder)
        self.assertIn('EMBED_PDF_SOURCE_INVALID', str(caught.exception))


class _StubbedPipeline(Pipeline):
    """A run without RFC3161: only the published name and the hand-over matter."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.compose_calls = []

    def preflight(self, target, mode='combined', pdf_embed=False, combo_embed=False):
        _info, _issues, _warnings = super().preflight(
            target, mode, pdf_embed=pdf_embed, combo_embed=combo_embed)
        return {'target': str(target), 'input_kind': _info['input_kind'], 'generator': 'stub'}, [], []

    def generate(self, target, mode='combined', recursive=False, include_explanation=False,
                 filters=None, files=None):
        # The generator always names a combined report COMBO; only the published
        # name gains the _ALL and _PDF suffixes.
        path = self.root / 'RPT-20261116-00009-ABCD_HASHREPORT_TYP_COMBO.pdf'
        _report(path)
        return path

    def _compose(self, report, target, case, include_explanation=False, include_source_pdf=False,
                 embed_pdf=None, embed_position='after'):
        self.compose_calls.append({
            'embed_pdf': str(embed_pdf) if embed_pdf is not None else None,
            'embed_position': embed_position,
            'include_source_pdf': include_source_pdf,
        })
        destination = case / 'report-before-rfc3161.UNSEALED.pdf'
        shutil.copyfile(report, destination)
        return destination

    def stamp(self, working, case):
        audit = case / 'rfc3161-audit.json'
        audit.write_text('{}', encoding='utf-8')
        return working, audit


class ComboPdfPublishNameTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.folder = self.root / 'evidence'
        self.folder.mkdir()
        (self.folder / 'a.txt').write_text('evidence', encoding='utf-8')
        self.embedded = _source(self.root / 'Anlage.pdf')
        self.pipeline = _StubbedPipeline(self.root, {}, log=lambda _message: None)

    def tearDown(self):
        self._temporary.cleanup()

    def test_combo_report_with_an_embedded_pdf_is_published_as_combo_pdf(self):
        manifest = self.pipeline.run(self.folder, embed_pdf=self.embedded, embed_position='before')
        published = sorted(path.name for path in self.folder.glob('*_HASHREPORT_TYP_COMBO_PDF.pdf'))
        self.assertEqual(len(published), 1, sorted(path.name for path in self.folder.iterdir()))
        self.assertTrue(published[0].endswith('_COMBO_PDF.pdf'))
        self.assertEqual(manifest['input_kind'], 'combo_embed')
        self.assertEqual(manifest['embed_position'], 'before')
        self.assertEqual(manifest['embed_pdf'], str(self.embedded.resolve()))
        self.assertEqual(self.pipeline.compose_calls[0]['embed_position'], 'before')
        self.assertEqual(self.pipeline.compose_calls[0]['embed_pdf'], str(self.embedded.resolve()))
        self.assertFalse(self.listdir_names().get('_COMBO.pdf'))

    def listdir_names(self):
        return {path.name.split('HASHREPORT_TYP_')[-1]: True for path in self.folder.glob('*.pdf')}

    def test_recursive_run_publishes_combo_all_pdf(self):
        manifest = self.pipeline.run(
            self.folder, recursive=True, embed_pdf=self.embedded, embed_position='after',
        )
        published = sorted(path.name for path in self.folder.glob('*_HASHREPORT_TYP_COMBO_ALL_PDF.pdf'))
        self.assertEqual(len(published), 1, sorted(path.name for path in self.folder.iterdir()))
        self.assertEqual(manifest['embed_position'], 'after')
        self.assertEqual(self.pipeline.compose_calls[0]['include_source_pdf'], False)

    def test_run_without_an_embedded_pdf_keeps_the_plain_combo_name(self):
        manifest = self.pipeline.run(self.folder)
        published = sorted(path.name for path in self.folder.glob('*_HASHREPORT_TYP_COMBO.pdf'))
        self.assertEqual(len(published), 1, sorted(path.name for path in self.folder.iterdir()))
        self.assertIsNone(manifest['embed_pdf'])
        self.assertIsNone(manifest['embed_position'])
        self.assertIsNone(self.pipeline.compose_calls[0]['embed_pdf'])


if __name__ == '__main__':
    unittest.main()
