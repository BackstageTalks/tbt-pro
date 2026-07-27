from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_INCLUDE_EXTENSIONS = {
    ".py", ".yml", ".yaml", ".json", ".js", ".ts", ".tsx", ".css", ".html", ".md", ".txt", ".toml", ".ini", ".cfg", ".sh",
}
DEFAULT_EXCLUDED_DIRS = {
    ".git", ".github/cache", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "venv", "env", "node_modules", "__pycache__",
    "corq/site", "site", "dist", "build", ".next", ".cache",
}
DEFAULT_EXCLUDED_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
}
GENERATED_OUTPUT_DIRS = {"outputs/project_metrics"}


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_excluded(path: Path, root: Path, excluded_dirs: Iterable[str]) -> bool:
    rel = rel_path(path, root)
    parts = rel.split("/")
    excluded = set(excluded_dirs) | GENERATED_OUTPUT_DIRS
    for idx in range(1, len(parts) + 1):
        prefix = "/".join(parts[:idx])
        if prefix in excluded:
            return True
    return False


def iter_files(root: Path, include_exts: Iterable[str], excluded_dirs: Iterable[str], excluded_files: Iterable[str]) -> Iterable[Path]:
    include = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in include_exts}
    excluded_file_names = set(excluded_files)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded(path, root, excluded_dirs):
            continue
        if path.name in excluded_file_names:
            continue
        if path.suffix.lower() not in include:
            continue
        yield path


def count_file(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"lines": 0, "blank": 0, "comment": 0, "code": 0, "bytes": path.stat().st_size, "read_error": True}
    lines = text.splitlines()
    blank = 0
    comment = 0
    ext = path.suffix.lower()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank += 1
            continue
        if ext in {".py", ".sh", ".yml", ".yaml", ".toml", ".ini", ".cfg"} and stripped.startswith("#"):
            comment += 1
        elif ext in {".js", ".ts", ".tsx", ".css"} and (stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")):
            comment += 1
        elif ext in {".html", ".md"} and stripped.startswith("<!--"):
            comment += 1
    total = len(lines)
    code = max(total - blank - comment, 0)
    return {"lines": total, "blank": blank, "comment": comment, "code": code, "bytes": path.stat().st_size, "read_error": False}


def git_stat(root: Path, args: List[str]) -> str:
    import subprocess
    try:
        out = subprocess.check_output(["git", *args], cwd=str(root), stderr=subprocess.DEVNULL, text=True).strip()
        return out
    except Exception:
        return ""


def build_metrics(root: Path, include_exts: Iterable[str], excluded_dirs: Iterable[str], excluded_files: Iterable[str]) -> Dict[str, Any]:
    files = list(iter_files(root, include_exts, excluded_dirs, excluded_files))
    by_ext: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"files": 0, "lines": 0, "code": 0, "blank": 0, "comment": 0, "bytes": 0})
    by_top_dir: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"files": 0, "lines": 0, "code": 0})
    largest: List[Dict[str, Any]] = []
    total = {"files": 0, "lines": 0, "code": 0, "blank": 0, "comment": 0, "bytes": 0}

    for path in files:
        stats = count_file(path)
        ext = path.suffix.lower() or "[no_ext]"
        rel = rel_path(path, root)
        top = rel.split("/", 1)[0]
        total["files"] += 1
        for key in ("lines", "code", "blank", "comment", "bytes"):
            total[key] += int(stats.get(key) or 0)
            by_ext[ext][key] += int(stats.get(key) or 0)
        by_ext[ext]["files"] += 1
        by_top_dir[top]["files"] += 1
        by_top_dir[top]["lines"] += int(stats.get("lines") or 0)
        by_top_dir[top]["code"] += int(stats.get("code") or 0)
        largest.append({"path": rel, "ext": ext, **stats})

    largest.sort(key=lambda x: int(x.get("lines") or 0), reverse=True)
    commit_count = git_stat(root, ["rev-list", "--count", "HEAD"])
    latest_commit = git_stat(root, ["log", "-1", "--format=%h %cs %s"])
    branch = git_stat(root, ["rev-parse", "--abbrev-ref", "HEAD"])

    return {
        "generated_at": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat(),
        "root": str(root.resolve()),
        "git": {"branch": branch, "commit_count": int(commit_count) if commit_count.isdigit() else None, "latest_commit": latest_commit},
        "totals": total,
        "by_extension": dict(sorted(by_ext.items(), key=lambda kv: (-kv[1]["code"], kv[0]))),
        "by_top_directory": dict(sorted(by_top_dir.items(), key=lambda kv: (-kv[1]["code"], kv[0]))),
        "largest_files": largest[:25],
    }


def markdown_report(metrics: Dict[str, Any]) -> str:
    totals = metrics["totals"]
    git = metrics.get("git") or {}
    lines: List[str] = []
    lines.append("# BackstageTalks Project Development Metrics")
    lines.append("")
    lines.append(f"Generated: `{metrics.get('generated_at')}`")
    if git.get("branch") or git.get("commit_count") or git.get("latest_commit"):
        lines.append("")
        lines.append("## Git snapshot")
        if git.get("branch"):
            lines.append(f"- Branch: `{git.get('branch')}`")
        if git.get("commit_count") is not None:
            lines.append(f"- Commit count: **{git.get('commit_count')}**")
        if git.get("latest_commit"):
            lines.append(f"- Latest commit: `{git.get('latest_commit')}`")
    lines.append("")
    lines.append("## Executive summary")
    lines.append(f"- Tracked files: **{totals['files']:,}**")
    lines.append(f"- Total lines: **{totals['lines']:,}**")
    lines.append(f"- Estimated code lines: **{totals['code']:,}**")
    lines.append(f"- Blank lines: **{totals['blank']:,}**")
    lines.append(f"- Comment/config note lines: **{totals['comment']:,}**")
    lines.append(f"- Tracked text size: **{totals['bytes'] / 1024:.1f} KB**")
    lines.append("")
    lines.append("## By file type")
    lines.append("")
    lines.append("| Extension | Files | Total lines | Code lines | Size KB |")
    lines.append("|---:|---:|---:|---:|---:|")
    for ext, row in metrics["by_extension"].items():
        lines.append(f"| `{ext}` | {row['files']:,} | {row['lines']:,} | {row['code']:,} | {row['bytes'] / 1024:.1f} |")
    lines.append("")
    lines.append("## By top-level directory")
    lines.append("")
    lines.append("| Directory | Files | Total lines | Code lines |")
    lines.append("|---|---:|---:|---:|")
    for directory, row in metrics["by_top_directory"].items():
        lines.append(f"| `{directory}` | {row['files']:,} | {row['lines']:,} | {row['code']:,} |")
    lines.append("")
    lines.append("## Largest tracked files")
    lines.append("")
    lines.append("| File | Lines | Code lines |")
    lines.append("|---|---:|---:|")
    for row in metrics.get("largest_files", [])[:15]:
        lines.append(f"| `{row['path']}` | {row['lines']:,} | {row['code']:,} |")
    lines.append("")
    lines.append("_Note: Generated folders, site build outputs, virtual environments, caches and lock files are excluded to keep the report focused on maintained project work._")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate project code/work metrics report")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--output-dir", default="outputs/project_metrics", help="Output directory")
    parser.add_argument("--extensions", default=",".join(sorted(DEFAULT_INCLUDE_EXTENSIONS)), help="Comma-separated extensions")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir)
    include_exts = [x.strip() for x in args.extensions.split(",") if x.strip()]
    metrics = build_metrics(root, include_exts, DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_FILES)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "project_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "project_metrics.md").write_text(markdown_report(metrics), encoding="utf-8")
    print(markdown_report(metrics))


if __name__ == "__main__":
    main()
