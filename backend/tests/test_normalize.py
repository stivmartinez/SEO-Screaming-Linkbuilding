import unittest

from app.crawler.normalize import expand_hosts, is_internal, normalize_url


class NormalizeTests(unittest.TestCase):
    def test_strips_fragment_tracking_and_slash(self) -> None:
        url = normalize_url("https://Example.com/path/?utm_source=x&keep=1#section")
        self.assertEqual(url, "https://example.com/path?keep=1")

    def test_resolves_relative(self) -> None:
        url = normalize_url("../about", "https://example.com/blog/post")
        self.assertEqual(url, "https://example.com/about")

    def test_skips_non_http(self) -> None:
        self.assertIsNone(normalize_url("mailto:hi@example.com"))
        self.assertIsNone(normalize_url("javascript:void(0)"))

    def test_expand_and_internal(self) -> None:
        hosts = expand_hosts(["example.com"])
        self.assertIn("www.example.com", hosts)
        self.assertTrue(is_internal("https://www.example.com/a", hosts))
        self.assertFalse(is_internal("https://other.com/", hosts))


if __name__ == "__main__":
    unittest.main()
