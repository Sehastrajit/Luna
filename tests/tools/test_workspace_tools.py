from __future__ import annotations

import unittest

from tests.tools import _bootstrap  # noqa: F401


class WorkspaceToolTests(unittest.TestCase):
    def test_workspace_read_write_round_trip(self) -> None:
        from backend.services.workspace import WORKSPACE_DIR, read_workspace_file, write_workspace_file

        path = "_tests/tool_smoke.txt"
        result = write_workspace_file(path, "luna tool smoke")
        self.assertEqual(result["path"], path)
        self.assertEqual(read_workspace_file(path), "luna tool smoke")

        target = WORKSPACE_DIR / path
        if target.exists():
            target.unlink()

    def test_workspace_path_escape_is_blocked(self) -> None:
        from backend.services.workspace import read_workspace_file

        with self.assertRaises(ValueError):
            read_workspace_file("../../.env")


if __name__ == "__main__":
    unittest.main(verbosity=2)
