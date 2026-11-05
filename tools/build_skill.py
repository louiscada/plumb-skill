#!/usr/bin/env python3
"""Package the plumb/ folder for installing in Claude.

Builds two identical zips with plumb/ at their root:
  dist/plumb.zip    for Customize > Skills > Upload a skill
  dist/plumb.skill  for dropping into a Claude chat ("Save skill")

Run from anywhere:  python tools/build_skill.py
The release workflow runs this and attaches both files to each GitHub Release.
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plumb")
OUTS = [os.path.join(ROOT, "dist", "plumb.zip"),
        os.path.join(ROOT, "dist", "plumb.skill")]
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_FILES = {".DS_Store"}


def main():
    if not os.path.isfile(os.path.join(SKILL, "SKILL.md")):
        sys.exit("plumb/SKILL.md not found")
    os.makedirs(os.path.dirname(OUTS[0]), exist_ok=True)
    for out in OUTS:
        count = 0
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for folder, dirs, files in os.walk(SKILL):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    if name in SKIP_FILES or name.endswith(".pyc"):
                        continue
                    path = os.path.join(folder, name)
                    z.write(path, os.path.relpath(path, ROOT))
                    count += 1
        print(f"Built {os.path.relpath(out, ROOT)} ({count} files, "
              f"{os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
