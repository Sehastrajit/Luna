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


if __name__ == "__main__":
    unittest.main(verbosity=2)
