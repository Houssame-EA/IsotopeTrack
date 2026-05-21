#!/usr/bin/env python3
"""
bump_version.py — Update IsotopeTrack version across ALL files.


"""

import sys
import re
from pathlib import Path

# ── Every file and every pattern that needs updating ──────────────────────────

FILES = [
    # ── README badge ──────────────────────────────────────────────────────────
    ("README.md", [
        (r"version-[\d\.]+\-blue\.svg", "version-{v}-blue.svg"),
    ]),

    # ── PyInstaller spec — macOS ──────────────────────────────────────────────
    ("IsotopeTrack_M.spec", [
        (r"'CFBundleShortVersionString':\s*'[\d\.]+'",
         "'CFBundleShortVersionString': '{v}'"),
        (r"'CFBundleVersion':\s*'[\d\.]+'",
         "'CFBundleVersion': '{v}'"),
    ]),

    # ── PyInstaller spec — Windows ────────────────────────────────────────────
    ("IsotopeTrack_W.spec", [
        (r"'CFBundleShortVersionString':\s*'[\d\.]+'",
         "'CFBundleShortVersionString': '{v}'"),
        (r"'CFBundleVersion':\s*'[\d\.]+'",
         "'CFBundleVersion': '{v}'"),
    ]),

    # ── Inno Setup installer ──────────────────────────────────────────────────
    ("IsotopeTrack_Setup.iss", [
        (r'#define AppVersion\s+"[\d\.]+"',
         '#define AppVersion     "{v}"'),
    ]),

    # ── project_manager.py (3 occurrences) ───────────────────────────────────
    ("save_export/project_manager.py", [
        (r"self\.project_version\s*=\s*'[\d\.]+'",
         "self.project_version = '{v}'"),
        (r"(?m)^Version=[\d\.]+$",
         "Version={v}"),
        (r"'application_version':\s*'[\d\.]+'",
         "'application_version': '{v}'"),
    ]),

    # ── help_dialogs.py ───────────────────────────────────────────────────────
    ("tools/help_dialogs.py", [
        (r"Version [\d\.]+</h3>",
         "Version {v}</h3>"),
    ]),

    # ── splash_screen.py ─────────────────────────────────────────────────────
    ("tools/splash_screen.py", [
        (r'version: str = "Version [\d\.]+(:[^"]*)??"',
         'version: str = "Version {v}:Beta"'),
    ]),

    # ── tutorial.py ──────────────────────────────────────────────────────────
    ("tools/tutorial.py", [
        (r"IsotopeTrack v[\d\.]+</h2>",
         "IsotopeTrack v{v}</h2>"),
    ]),
]


def bump(new_version: str):
    print(f"\nBumping version → {new_version}\n")

    updated = []
    skipped = []
    missing = []

    for filename, patterns in FILES:
        path = Path(filename)
        if not path.exists():
            missing.append(filename)
            continue

        content = path.read_text(encoding="utf-8")
        original = content

        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement.replace("{v}", new_version), content)

        if content != original:
            path.write_text(content, encoding="utf-8")
            updated.append(filename)
        else:
            skipped.append(filename)

    # ── Report ────────────────────────────────────────────────────────────────
    for f in updated:
        print(f"   {f}")
    for f in skipped:
        print(f"   {f}  (no match found — check pattern)")
    for f in missing:
        print(f"  {f}  (file not found)")

    print(f"\n Done! Version is now {new_version}")
    print("\nNext steps:")
    print(f"  git add .")
    print(f"  git commit -m \"chore: bump version to {new_version}\"")
    print(f"  git tag v{new_version}")
    print(f"  git push origin main --tags\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python bump_version.py <version>")
        print("Example: python bump_version.py 1.0.4")
        sys.exit(1)

    v = sys.argv[1].strip()
    if not re.match(r"^\d+\.\d+\.\d+$", v):
        print(" Version must be X.Y.Z  (e.g. 1.0.4)")
        sys.exit(1)

    bump(v)