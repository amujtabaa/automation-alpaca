from pathlib import Path

missing = []
for line in Path("CLAUDE.md").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line.startswith("@"):
        p = Path(line[1:])
        if not p.exists():
            missing.append(str(p))
if missing:
    print("MISSING @ imports:")
    print("\n".join(missing))
    raise SystemExit(1)
print("All CLAUDE.md @ imports resolve.")
