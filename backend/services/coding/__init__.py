"""
Luna coding agent package.

Public API — import from here, not from submodules:
  stream_coding_agent   — main SSE generator
  execute_coding_tool   — direct tool invocation
  build_workspace_index — project snapshot builder
  tool_read_file        — read a workspace file
  tool_write_file       — write a workspace file
  tool_list_files       — list a directory
  WORKSPACE_ROOT        — default workspace path
"""
from backend.services.coding.agent import stream_coding_agent
from backend.services.coding.indexer import build_workspace_index
from backend.services.coding.tools import (
    WORKSPACE_ROOT,
    execute_coding_tool,
    tool_list_files,
    tool_read_file,
    tool_write_file,
)

__all__ = [
    "stream_coding_agent",
    "execute_coding_tool",
    "build_workspace_index",
    "tool_read_file",
    "tool_write_file",
    "tool_list_files",
    "WORKSPACE_ROOT",
]
