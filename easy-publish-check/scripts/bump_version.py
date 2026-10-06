#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义化版本迭代：自动判定级别、同步所有清单版本号、更新 CHANGELOG。

级别判定（auto，依据上个 tag 之后的 Conventional Commits）：
  BREAKING CHANGE / feat!:  major
  feat:                    minor
  其它（fix/chore/docs…）:  patch

用法：
  python bump_version.py [--project DIR]
  python bump_version.py --level minor
  python bump_version.py --set 1.4.0
  python bump_version.py --level patch --no-changelog
  python bump_version.py --json
  python bump_version.py --commit        # 同时生成 release 提交（不打 tag）

注意：脚本只更新“已存在版本号”的清单，不会向没有版本声明的文件注入版本。
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_common import (  # noqa: E402
    Mark, _utf8_stdio, bump_semver, current_version, find_changelog,
    git, git_text, latest_tag, list_version_files, project_root,
    suggest_level, update_changelog, SEMVER_RE,
)

CHANGELOG_TEMPLATE = """# Changelog

本项目所有显著变更均记录于此，格式遵循 [Keep a Changelog](https://keepachangelog.com/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- 

### Changed
- 

### Fixed
- 

"""


def classify_commits(project):
    """把自上个 tag 以来的提交按 Conventional Commits 归类，供撰写迭代说明。"""
    last = latest_tag(project)
    rev = f"{last}..HEAD" if last else "HEAD"
    log = git_text(["log", rev, "--pretty=format:%s", "--no-merges"], project)
    groups = {"feat": [], "fix": [], "perf": [], "refactor": [], "docs": [],
              "chore": [], "test": [], "style": [], "ci": [], "build": [], "other": []}
    breaking = []
    for line in log.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^(\w+)(?:\([^)]*\))?(!)?:\s*(.+)$", s)
        if "BREAKING CHANGE" in s or (m and m.group(2)):
            breaking.append(s)
        if m:
            kind = m.group(1)
            groups.setdefault(kind, []).append(m.group(3))
        else:
            groups["other"].append(s)
    return groups, breaking


def ensure_changelog(project, new_version, release_date):
    f = find_changelog(project)
    if f:
        return update_changelog(project, new_version, release_date)
    f = Path(project) / "CHANGELOG.md"
    text = CHANGELOG_TEMPLATE.replace(
        "## [Unreleased]",
        f"## [Unreleased]\n\n## [{new_version}] - {release_date}",
        1,
    )
    f.write_text(text, encoding="utf-8")
    return f


def main():
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="语义化版本迭代")
    ap.add_argument("--project", default=None)
    ap.add_argument("--level", choices=["auto", "major", "minor", "patch"], default="auto")
    ap.add_argument("--set", dest="set_version", help="直接指定版本号，覆盖自动判定")
    ap.add_argument("--date", dest="release_date", default=None, help="发布日期 YYYY-MM-DD")
    ap.add_argument("--no-changelog", action="store_true")
    ap.add_argument("--commit", action="store_true", help="生成 release 提交")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    project = project_root(args.project)
    old_version, source = current_version(project)
    groups, breaking = classify_commits(project)

    if args.set_version:
        new_version = args.set_version
        if not SEMVER_RE.match(new_version):
            print(f"{Mark.FAIL} 指定版本号不符合语义化规范: {new_version}")
            return 1
        level = "manual"
    else:
        level = args.level
        if level == "auto":
            level, _ = suggest_level(project)
        if not old_version:
            old_version = "0.0.0"
            print(f"{Mark.WARN} 未发现现有版本，按 0.0.0 起算，首个正式版建议用 1.0.0")
        try:
            new_version = bump_semver(old_version, level)
        except ValueError as e:
            print(f"{Mark.FAIL} {e}；可用 --set 手动指定")
            return 1

    release_date = args.release_date or date.today().isoformat()

    changed = []
    for kind, path, ver in list_version_files(project):
        if not ver:
            continue
        try:
            if __import__("release_common").write_version(kind, path, new_version):
                changed.append(f"{kind} ({ver} -> {new_version})")
        except Exception as e:
            print(f"{Mark.WARN} {kind} 更新失败: {e}")

    changelog_path = None
    if not args.no_changelog:
        changelog_path = ensure_changelog(project, new_version, release_date)

    if args.commit and (changed or changelog_path):
        git(["add", "-A"], project)
        msg = f"chore(release): v{new_version}"
        git(["commit", "-m", msg], project)

    result = {
        "project": str(project),
        "old_version": old_version,
        "version_source": source,
        "level": level,
        "new_version": new_version,
        "updated_manifests": changed,
        "changelog": str(changelog_path) if changelog_path else None,
        "commit_summary": {k: v for k, v in groups.items() if v},
        "breaking": breaking,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== 版本迭代: {project} ===")
        print(f"{old_version or '(无)'} [{source}]  --{level}-->  {new_version}")
        print(f"已同步清单: {len(changed)} 个")
        for c in changed:
            print(f"  - {c}")
        if changelog_path:
            print(f"CHANGELOG: {changelog_path}")
        feat_n = len(groups["feat"])
        fix_n = len(groups["fix"])
        print(f"提交摘要: {feat_n} 个新功能 / {fix_n} 个问题修复"
              + (f" / {len(breaking)} 个破坏性变更" if breaking else ""))
        if not any(groups[k] for k in groups):
            print(f"{Mark.WARN} 自上个 tag 以来没有可解析的提交，迭代内容请与用户确认")
        print(f"\n{Mark.INFO} 下一步：把本版本迭代内容整理进 CHANGELOG 的 [{new_version}] 段落")
    return 0


if __name__ == "__main__":
    sys.exit(main())
