import unittest

from app.crawler.language import infer_default_lang, lang_from_path, normalize_locale
from app.crawler.sitemap import parse_sitemap


class LanguageTests(unittest.TestCase):
    def test_path_prefix(self) -> None:
        self.assertEqual(lang_from_path("https://betuber.com/es/cookies"), "es")
        self.assertEqual(lang_from_path("https://betuber.com/ja/cookie"), "ja")
        self.assertIsNone(lang_from_path("https://betuber.com/best-vtuber-software"))

    def test_normalize_locale(self) -> None:
        self.assertEqual(normalize_locale("en-US"), "en")
        self.assertEqual(normalize_locale("x-default"), "x-default")

    def test_default_fallback_without_signals(self) -> None:
        self.assertEqual(infer_default_lang([], "https://example.com/about"), "default")

    def test_default_from_hreflang(self) -> None:
        pairs = [
            ("https://betuber.com/", "en", "https://betuber.com/"),
            ("https://betuber.com/", "x-default", "https://betuber.com/"),
            ("https://betuber.com/", "es", "https://betuber.com/es/"),
        ]
        self.assertEqual(infer_default_lang(pairs, "https://betuber.com/"), "en")

    def test_sitemap_xhtml(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:xhtml="http://www.w3.org/1999/xhtml">
          <url>
            <loc>https://betuber.com/best-vtuber-software/</loc>
            <xhtml:link rel="alternate" hreflang="en-US" href="https://betuber.com/best-vtuber-software/"/>
            <xhtml:link rel="alternate" hreflang="es-ES" href="https://betuber.com/es/mejor-software-para-vtuber/"/>
          </url>
        </urlset>
        """
        document = parse_sitemap(xml)
        langs = {lang for _source, lang, _target in document.hreflangs}
        self.assertEqual(langs, {"en", "es"})


if __name__ == "__main__":
    unittest.main()
