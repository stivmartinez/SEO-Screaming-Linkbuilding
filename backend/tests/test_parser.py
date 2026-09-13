import unittest

from app.crawler.parser import is_indexable, parse_html


HTML = """
<html>
  <head>
    <title>Home</title>
    <meta name="description" content="A site">
    <meta name="robots" content="index,follow">
    <link rel="canonical" href="https://example.com/">
  </head>
  <body>
    <h1>Welcome</h1>
    <a href="/about">About</a>
    <a href="https://outbound.test/x" rel="nofollow">Out</a>
  </body>
</html>
"""


class ParserTests(unittest.TestCase):
    def test_extracts_seo_and_links(self) -> None:
        parsed = parse_html(HTML, "https://example.com/", {"example.com", "www.example.com"})
        self.assertEqual(parsed.title, "Home")
        self.assertEqual(parsed.meta_description, "A site")
        self.assertEqual(parsed.h1, "Welcome")
        self.assertEqual(parsed.canonical, "https://example.com/")
        kinds = {link.url: link.kind for link in parsed.links}
        self.assertEqual(kinds["https://example.com/about"], "internal")
        self.assertEqual(kinds["https://outbound.test/x"], "external")

    def test_indexable(self) -> None:
        self.assertTrue(is_indexable(200, "text/html", "index,follow", None))
        self.assertFalse(is_indexable(200, "text/html", "noindex", None))
        self.assertFalse(is_indexable(404, "text/html", None, None))


if __name__ == "__main__":
    unittest.main()
