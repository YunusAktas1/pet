from pathlib import Path

FILES = [
    Path("backend/main.py"),
    Path("pytest.ini"),
    Path("backend/.env"),
    Path("pyproject.toml"),
]


def to_utf8_nobom(p: Path) -> None:
    raw = p.read_bytes()
    for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "cp1254", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1")
    text = text.replace("\ufeff", "")
    p.write_bytes(text.encode("utf-8"))


for file_path in FILES:
    if file_path.exists():
        to_utf8_nobom(file_path)

print("Re-encoded target files to UTF-8 (no BOM).")
