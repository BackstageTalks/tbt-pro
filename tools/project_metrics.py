from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

SOURCE_EXTENSIONS = {
    ".py", ".yml", ".yaml", ".js", ".ts", ".tsx", ".css", ".html", ".md", ".toml", ".ini", ".cfg", ".sh",
}
DATA_EXTENSIONS = {".json", ".csv", ".xml"}
EXCLUDED_DIRS = {
    ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "venv", "env", "node_modules", "__pycache__",
    "corq/site", "site", "dist", "build", ".next", ".cache", "outputs",
}
# Large generated/cache data should not be presented as code work.
DATA_CACHE_DIRS = {
    "thinq/data", "data", "outputs", "corq/site", "corq/web/assets",
}
EXCLUDED_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def under_any(path: Path, root: Path, dirs: Iterable[str]) -> bool:
    rel = rel_path(path, root)
    parts = rel.split("/")
    checks = set(dirs)
    for idx in range(1, len(parts) + 1):
        if "/".join(parts[:idx]) in checks:
            return True
    return False


def count_file(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"lines": 0, "blank": 0, "comment": 0, "code": 0, "bytes": path.stat().st_size, "read_error": True}
    lines = text.splitlines()
    ext = path.suffix.lower()
    blank = 0
    comment = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank += 1
        elif ext in {".py", ".sh", ".yml", ".yaml", ".toml", ".ini", ".cfg"} and stripped.startswith("#"):
            comment += 1
        elif ext in {".js", ".ts", ".tsx", ".css"} and (stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")):
            comment += 1
        elif ext in {".html", ".md"} and stripped.startswith("<!--"):
            comment += 1
    total = len(lines)
    return {"lines": total, "blank": blank, "comment": comment, "code": max(total - blank - comment, 0), "bytes": path.stat().st_size, "read_error": False}


def iter_project_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in EXCLUDED_FILES:
            continue
        if under_any(path, root, EXCLUDED_DIRS):
            continue
        yield path


def bucket_for(path: Path, root: Path) -> str:
    ext = path.suffix.lower()
    if under_any(path, root, DATA_CACHE_DIRS) or ext in DATA_EXTENSIONS:
        return "data"
    if ext in SOURCE_EXTENSIONS:
        return "source"
    return "other"


def empty_totals() -> Dict[str, int]:
    return {"files": 0, "lines": 0, "code": 0, "blank": 0, "comment": 0, "bytes": 0}


def add_stats(total: Dict[str, int], stats: Dict[str, Any]) -> None:
    total["files"] += 1
    for key in ("lines", "code", "blank", "comment", "bytes"):
        total[key] += int(stats.get(key) or 0)


def git_stat(root: Path, args: List[str]) -> str:
    import subprocess
    try:
        return subprocess.check_output(["git", *args], cwd=str(root), stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def build_metrics(root: Path) -> Dict[str, Any]:
    totals = {"source": empty_totals(), "data": empty_totals(), "other": empty_totals(), "all_tracked_text": empty_totals()}
    by_ext: Dict[str, Dict[str, int]] = defaultdict(empty_totals)
    by_dir: Dict[str, Dict[str, int]] = defaultdict(empty_totals)
    largest_source: List[Dict[str, Any]] = []
    largest_data: List[Dict[str, Any]] = []

    for path in iter_project_files(root):
        ext = path.suffix.lower() or "[no_ext]"
        if ext not in SOURCE_EXTENSIONS | DATA_EXTENSIONS:
            continue
        stats = count_file(path)
        bucket = bucket_for(path, root)
        rel = rel_path(path, root)
        top = rel.split("/", 1)[0]
        add_stats(totals[bucket], stats)
        add_stats(totals["all_tracked_text"], stats)
        add_stats(by_ext[ext], stats)
        add_stats(by_dir[top], stats)
        item = {"path": rel, "bucket": bucket, "ext": ext, **stats}
        if bucket == "source":
            largest_source.append(item)
        elif bucket == "data":
            largest_data.append(item)

    largest_source.sort(key=lambda r: int(r.get("lines") or 0), reverse=True)
    largest_data.sort(key=lambda r: int(r.get("lines") or 0), reverse=True)
    commit_count = git_stat(root, ["rev-list", "--count", "HEAD"])
    return {
        "generated_at": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat(),
        "git": {
            "branch": git_stat(root, ["rev-parse", "--abbrev-ref", "HEAD"]),
            "commit_count": int(commit_count) if commit_count.isdigit() else None,
            "latest_commit": git_stat(root, ["log", "-1", "--format=%h %cs %s"]),
        },
        "totals": totals,
        "by_extension": dict(sorted(by_ext.items(), key=lambda kv: (-kv[1]["code"], kv[0]))),
        "by_top_directory": dict(sorted(by_dir.items(), key=lambda kv: (-kv[1]["code"], kv[0]))),
        "largest_source_files": largest_source[:20],
        "largest_data_files": largest_data[:20],
        "notes": [
            "Source totals exclude generated site files, outputs, virtualenvs, caches and large data caches.",
            "Data totals are reported separately so JSON/CSV caches are not presented as hand-written code.",
        ],
    }


def markdown_report(metrics: Dict[str, Any]) -> str:
    source = metrics["totals"]["source"]
    data = metrics["totals"]["data"]
    all_text = metrics["totals"]["all_tracked_text"]
    git = metrics.get("git") or {}
    lines: List[str] = []
    lines.append("# BackstageTalks Project Development Metrics")
    lines.append("")
    lines.append(f"Generated: `{metrics.get('generated_at')}`")
    lines.append("")
    lines.append("## Customer-facing summary")
    lines.append(f"- Maintained source/config/docs files: **{source['files']:,}**")
    lines.append(f"- Maintained source/config/docs lines: **{source['lines']:,}**")
    lines.append(f"- Estimated maintained code/config lines: **{source['code']:,}**")
    lines.append(f"- Data/cache files tracked separately: **{data['files']:,}**")
    lines.append(f"- Data/cache lines tracked separately: **{data['lines']:,}**")
    lines.append(f"- All tracked text files together: **{all_text['files']:,} files / {all_text['lines']:,} lines**")
    if git.get("commit_count") is not None:
        lines.append(f"- Git commits: **{git.get('commit_count')}**")
    if git.get("latest_commit"):
        lines.append(f"- Latest commit: `{git.get('latest_commit')}`")
    lines.append("")
    lines.append("## By file type")
    lines.append("")
    lines.append("| Extension | Files | Lines | Code/config lines | Size KB |")
    lines.append("|---:|---:|---:|---:|---:|")
    for ext, row in metrics["by_extension"].items():
        lines.append(f"| `{ext}` | {row['files']:,} | {row['lines']:,} | {row['code']:,} | {row['bytes'] / 1024:.1f} |")
    lines.append("")
    lines.append("## By top-level directory")
    lines.append("")
    lines.append("| Directory | Files | Lines | Code/config lines |")
    lines.append("|---|---:|---:|---:|")
    for directory, row in metrics["by_top_directory"].items():
        lines.append(f"| `{directory}` | {row['files']:,} | {row['lines']:,} | {row['code']:,} |")
    lines.append("")
    lines.append("## Largest maintained source files")
    lines.append("")
    lines.append("| File | Lines | Code/config lines |")
    lines.append("|---|---:|---:|")
    for row in metrics.get("largest_source_files", [])[:15]:
        lines.append(f"| `{row['path']}` | {row['lines']:,} | {row['code']:,} |")
    lines.append("")
    lines.append("## Largest data/cache files, separated from code")
    lines.append("")
    lines.append("| File | Lines | Size KB |")
    lines.append("|---|---:|---:|")
    for row in metrics.get("largest_data_files", [])[:10]:
        lines.append(f"| `{row['path']}` | {row['lines']:,} | {row['bytes'] / 1024:.1f} |")
    lines.append("")
    for note in metrics.get("notes", []):
        lines.append(f"_Note: {note}_")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate project code/work metrics report")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default="outputs/project_metrics")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir)
    metrics = build_metrics(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "project_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "project_metrics.md").write_text(markdown_report(metrics), encoding="utf-8")
    print(markdown_report(metrics))


if __name__ == "__main__":
    main()
