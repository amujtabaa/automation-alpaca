#!/usr/bin/env python3
"""Check that the optional MCP control-plane spec files exist.

MCP is an optional layer: if no mcp/ tree exists in either layout, the check
skips instead of failing. Paths resolve through the manifest install_map.

Usage:
  python scripts/check_mcp_spec.py
"""
import sys

from ai_os_paths import find_root, resolve, resolve_dir

REQUIRED = [
    "14_MCP_CONTROL_PLANE.md",
    "mcp/README.md",
    "mcp/RESOURCE_SPEC.md",
    "mcp/PROMPT_SPEC.md",
    "mcp/TOOL_SPEC.md",
    "mcp/IMPLEMENTATION_PLAN.md",
    "mcp/CONFIG_EXAMPLES.md",
    "mcp/schemas/context_packet.schema.json",
    "mcp/server/README.md",
]

def main() -> int:
    root = find_root()
    if root is None:
        print("MCP SPEC CHECK FAILED")
        print("- AI_OS_MANIFEST.yaml not found walking up from the current directory")
        return 1
    if not resolve_dir(root, "mcp").exists():
        print("MCP SPEC CHECK SKIPPED: mcp/ not installed (MCP is an optional layer)")
        return 0
    missing = [p for p in REQUIRED if not resolve(root, p).exists()]
    if missing:
        print("MCP SPEC CHECK FAILED")
        for p in missing:
            print("- missing", p)
        return 1
    print("MCP SPEC CHECK PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
