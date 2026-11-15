import unittest
from hash_report_generator.style_loader import load_styles
from hash_report_generator.pdf_object_rules import volume_block_table_style

class VolumeCentralGeometryTest(unittest.TestCase):
    def test_volume_row_geometry_is_from_js(self):
        g=load_styles()['INFORMATION_BLOCK_STYLE']['volume_row_geometry']
        cmds=volume_block_table_style().getCommands()
        self.assertIn(('TOPPADDING',(0,0),(-1,-1),g['top_padding_pt']),cmds)
        self.assertIn(('BOTTOMPADDING',(0,0),(-1,-1),g['bottom_padding_pt']),cmds)
        self.assertIn(('LEFTPADDING',(0,0),(-1,-1),g['horizontal_padding_pt']),cmds)

class VolumeRenderedMetricsTest(unittest.TestCase):
    def test_six_lines_match_reference_vertical_step(self):
        import os, json, tempfile
        from pathlib import Path
        from unittest.mock import patch
        import fitz
        from reportlab.platypus import SimpleDocTemplate
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from hash_report_generator.chronoseal_volume_report import append_volume_section
        data={'requested_path':'C:/sample.pdf','volume_guid_path':'abc123',
              'volume_mount_point':'C:/','filesystem_name':'NTFS',
              'volume_serial_number':'12345678'}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CHRONOSEAL_VOLUME_JSON':json.dumps(data)}):
            output=str(Path(tmp)/'volume.pdf')
            story=[]
            append_volume_section(story,getSampleStyleSheet()['Normal'])
            SimpleDocTemplate(output,pagesize=A4).build(story)
            with fitz.open(output) as doc:
                spans=[line for block in doc[0].get_text('dict')['blocks'] for line in block.get('lines',[])
                       if any(''.join(s['text'] for s in line['spans']).startswith(key)
                              for key in ('VOLUME:','Working Folder:','Volume GUID:','Mounted On:','Filesystem:','Volume Serial:'))]
                self.assertEqual(len(spans),6)
                self.assertTrue(all(abs(spans[i+1]['bbox'][1]-spans[i]['bbox'][1]-12)<0.12 for i in range(1,5)))
                self.assertTrue(all(abs(s['size']-10)<0.01 for s in spans[0]['spans']))
                self.assertTrue(all(abs(s['size']-9)<0.01 for line in spans[1:] for s in line['spans']))
                self.assertTrue(all(s['color']==0 for line in spans for s in line['spans']))
                self.assertTrue(all('Bold' in line['spans'][0]['font'] for line in spans))
