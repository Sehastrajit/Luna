from __future__ import annotations

import subprocess
import unittest

from tests.tools import _bootstrap


class CliToolTests(unittest.TestCase):
    def test_cli_entrypoint_syntax(self) -> None:
        result = subprocess.run(
            ["node", "--check", "cli/luna.mjs"],
            cwd=_bootstrap.ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
