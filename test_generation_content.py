"""Reference style and watermark regressions, with no external requests."""
import unittest

from PIL import Image
from product_generation import branded_image, clean_description


class GenerationContent(unittest.TestCase):
    def test_descriptions_preserve_paragraphs_and_remove_markup(self):
        value = '<p>**Fideos** de arroz, 400 g.</p><p>• Para sopas y salteados.</p>'
        self.assertEqual(clean_description(value), 'Fideos de arroz, 400 g.\n\nPara sopas y salteados.')

    def test_short_description_is_one_bounded_sentence(self):
        short = clean_description(['Fideos de arroz.', 'Presentación de 400 g.'], short=True)
        self.assertEqual(short, 'Fideos de arroz. Presentación de 400 g.')
        self.assertLessEqual(len(clean_description('palabra ' * 80, short=True)), 240)
        self.assertEqual(clean_description(None), '')

    def test_center_watermark_and_corner_seal_match_colab(self):
        base = Image.new('RGB', (1000, 1000), 'white')
        logo = Image.new('RGBA', (100, 100), (0, 0, 0, 255))
        result = branded_image(base, logo)
        # 50% width in center, 15% alpha, and 20% opaque corner seal.
        self.assertEqual(result.size, base.size)
        self.assertEqual(result.mode, 'RGB')
        self.assertEqual(result.getpixel((100, 100)), (255, 255, 255))
        self.assertEqual(result.getpixel((500, 500)), (217, 217, 217))
        self.assertEqual(result.getpixel((800, 800)), (0, 0, 0))
        self.assertEqual(result.getpixel((990, 990)), (255, 255, 255))

    def test_transparent_logo_background_stays_transparent(self):
        base = Image.new('RGB', (100, 100), 'blue')
        logo = Image.new('RGBA', (20, 20), (255, 255, 255, 0))
        self.assertEqual(branded_image(base, logo).tobytes(), base.tobytes())


if __name__ == '__main__':
    unittest.main()
