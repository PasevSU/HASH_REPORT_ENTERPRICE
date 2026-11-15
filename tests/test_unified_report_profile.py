import unittest

from chronoseal.unified_report_profile import DEFAULT_PROFILE

MM = 72 / 25.4


class TestProfile(unittest.TestCase):
    def test_a4_and_margins(self):
        p = DEFAULT_PROFILE
        self.assertEqual((p.page_width_mm, p.page_height_mm), (210, 297))
        self.assertEqual((p.left_mm, p.right_mm, p.top_mm, p.bottom_mm), (20, 20, 20, 20))

    def test_audit_option_keys(self):
        self.assertEqual(len(DEFAULT_PROFILE.audit_options()), 7)
        self.assertEqual(DEFAULT_PROFILE.audit_options()['minimum_body_words'], 12)


class TestProfileMatchesEngine(unittest.TestCase):
    """The audit profile must describe the geometry the generator produces."""

    @classmethod
    def setUpClass(cls):
        from hash_report_generator.style_loader import load_styles
        styles = load_styles()
        cls.page = styles['PAGE']
        cls.identity = styles['PAGE_IDENTITY']

    def test_page_geometry_matches_engine(self):
        p = DEFAULT_PROFILE
        self.assertEqual(p.page_width_mm, self.page['width_mm'])
        self.assertEqual(p.page_height_mm, self.page['height_mm'])
        self.assertEqual(p.left_mm, self.page['left_mm'])
        self.assertEqual(p.right_mm, self.page['right_mm'])
        self.assertEqual(p.top_mm, self.page['top_mm'])

    def test_footer_band_covers_footer_strip(self):
        separator_mm = self.identity['separator_y_pt'] / MM
        self.assertGreaterEqual(DEFAULT_PROFILE.footer_band_mm, separator_mm)
        self.assertLess(DEFAULT_PROFILE.footer_band_mm - separator_mm, 1.0)

    def test_appendix_top_allowance_matches_engine(self):
        # appendix_heading_y_pt is a bottom-origin baseline for a 13pt title.
        heading_top_mm = (DEFAULT_PROFILE.page_height_mm * MM - self.identity['appendix_heading_y_pt']) / MM
        self.assertLessEqual(DEFAULT_PROFILE.appendix_top_mm, heading_top_mm - 0.5)
        self.assertLess(heading_top_mm - DEFAULT_PROFILE.appendix_top_mm, 6)

    def test_footer_block_clears_paper_edges(self):
        # Regression guard: the identity block printed 1.6mm from the bottom edge
        # and the last hash row 3.2mm from it, inside common printer dead zones.
        lowest = min(
            [self.identity['footer_url_y_pt'], self.identity['footer_developer_y_pt'],
             self.identity['footer_license_y_pt'], self.identity['footer_brand_y_pt'],
             self.identity['footer_id_y_pt'], self.identity['footer_page_y_pt'],
             self.identity['footer_hash_start_y_pt'] - 5 * self.identity['footer_hash_leading_pt']]
        )
        self.assertGreaterEqual(lowest / MM, 5.0)
        self.assertLess(self.identity['footer_heading_y_pt'], self.identity['separator_y_pt'])

    def test_footer_stays_inside_safe_edges(self):
        # Regression guard: footer_right_margin_mm was 1mm, so the identity block
        # printed 1mm from the paper edge while its separator respected the margin.
        safe_mm = 5.0
        self.assertGreaterEqual(self.identity['footer_right_margin_mm'], safe_mm)
        self.assertGreaterEqual(self.identity['footer_left_x_pt'] / MM, safe_mm)


if __name__ == '__main__':
    unittest.main()
