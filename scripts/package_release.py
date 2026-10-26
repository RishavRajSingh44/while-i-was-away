"""Build a source-only standalone archive from an explicit allowlist."""
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "release/while-i-was-away-0.1.0.tar.gz"
FILES = [
    ".gitignore", ".github/workflows/ci.yml", "LICENSE", "README.md",
    "THIRD_PARTY_NOTICES.md", "pyproject.toml", "requirements.lock", "render.yaml",
    "frontend/.env.public-demo", "frontend/eslint.config.js", "frontend/index.html",
    "frontend/package.json", "frontend/package-lock.json", "frontend/playwright.config.ts",
    "frontend/tsconfig.json", "frontend/vite.config.ts",
]
DIRECTORIES = ["backend", "docs", "frontend/e2e", "frontend/public", "frontend/src", "scripts", "tests"]
EXCLUDED = {".venv", ".data", ".git", "node_modules", "dist", "dist-demo", "__pycache__", "test-results", "playwright-report"}


def sources():
    paths = [ROOT / name for name in FILES]
    paths += [path for directory in DIRECTORIES for path in (ROOT / directory).rglob("*") if path.is_file()]
    for path in sorted(set(paths)):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED for part in relative.parts) or path.suffix in {".pyc", ".sqlite"} or path.name == ".DS_Store":
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Unsafe release input: {relative}")
        yield path, relative


def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    with tarfile.open(OUTPUT, "w:gz") as archive:
        for path, relative in sources():
            archive.add(path, arcname=Path("while-i-was-away") / relative, recursive=False)
    with tarfile.open(OUTPUT) as archive:
        names = archive.getnames()
        assert len(names) == len(set(names))
        assert "while-i-was-away/frontend/public/demo-data.json" in names
        assert not any(any(part in EXCLUDED for part in Path(name).parts) for name in names)
    print(OUTPUT)


if __name__ == "__main__":
    main()
