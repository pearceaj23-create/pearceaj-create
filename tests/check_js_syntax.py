import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"


def main():
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js is required for the JavaScript syntax check.")
    html = HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", html, re.IGNORECASE | re.DOTALL)
    if not scripts:
        raise SystemExit(f"No inline scripts found in {HTML.name}.")
    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir) / "inline.js"
        script_path.write_text("\n".join(scripts), encoding="utf-8")
        subprocess.run([node, "--check", str(script_path)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
