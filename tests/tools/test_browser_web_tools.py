from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO

from tests.tools import _bootstrap  # noqa: F401


class BrowserWebToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_read_rejects_non_http(self) -> None:
        from backend.services.browser_automation import browser_read

        with self.assertRaises(ValueError):
            await browser_read("file:///etc/passwd")

    async def test_web_fetch_rejects_empty_url_safely(self) -> None:
        from backend.services.web_tools import web_fetch

        with redirect_stdout(StringIO()):
            result = await web_fetch("")
        self.assertIsInstance(result, str)
        self.assertTrue(result)

    async def test_reference_url_extraction_for_research(self) -> None:
        from backend.services.web_tools import _extract_reference_urls

        result = "URL: https://example.com/a\nURL: https://example.com/b\nURL: https://example.com/a"
        self.assertEqual(
            _extract_reference_urls(result, limit=3),
            ["https://example.com/a", "https://example.com/b"],
        )

    def test_web_answer_reference_safeguard(self) -> None:
        from backend.routers.chat import _ensure_references

        tool_result = "References:\n[1] Example - https://example.com/"
        answer = _ensure_references("Short answer.", tool_result)
        self.assertIn("References:", answer)
        self.assertIn("https://example.com/", answer)

    async def test_web_download_rejects_non_http_url(self) -> None:
        from backend.services.web_tools import web_download_file

        with self.assertRaises(ValueError):
            await web_download_file("file:///tmp/data.csv", "_tests/data.csv")


if __name__ == "__main__":
    unittest.main(verbosity=2)
