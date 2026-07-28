#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate README.md from convert.py output."""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

output_dir = Path("output")
nodes = json.loads((output_dir / "all_nodes.json").read_text(encoding="utf-8"))

stats = {}
for n in nodes:
    p = n.get("protocol", "unknown")
    stats[p] = stats.get(p, 0) + 1

now = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
warp = "yes" if (output_dir / "warp_config.json").exists() else "no"

lines = [
    "# Proxy Nodes Converter",
    "",
    f"> Updated: {now} CST | WARP: {warp} | Daily 5:00 AM auto",
    "",
    "## Stats",
    "",
    "| Protocol | Count |",
    "|----------|-------|",
]
for p, c in sorted(stats.items()):
    lines.append(f"| {p} | {c} |")
lines.append(f"| **Total** | **{len(nodes)}** |")
lines.extend([
    "",
    "## Files",
    "",
    "| File | Use |",
    "|------|-----|",
    "| [share_links.txt](output/share_links.txt) | v2rayN / Nekoray import |",
    "| [subscription_b64.txt](output/subscription_b64.txt) | Base64 sub |",
    "| [clash_config.yaml](output/clash_config.yaml) | Clash Meta config |",
    "| [singbox_config.json](output/singbox_config.json) | sing-box with WARP chain |",
    "| [all_nodes.json](output/all_nodes.json) | Raw node data |",
    "",
    "## WARP Chain",
    "",
    "Sing-box config chains all nodes through WARP: node -> WARP outbound.",
    "Download [singbox_config.json](output/singbox_config.json) and use with sing-box.",
])

Path("README.md").write_text("\n".join(lines), encoding="utf-8")
print(f"OK: {len(nodes)} nodes")
