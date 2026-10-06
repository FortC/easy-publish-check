#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
easy-publish-check 共享库：全局发布人档案、项目配置、清单/版本探测、Git 辅助。

仅依赖 Python 3.8+ 标准库，可跨 Windows / macOS / Linux 使用。
其它脚本统一通过 `from release_common import ...` 引用（同目录运行即可）。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------- 路径与常量

PROFILE_DIR = Path.home() / ".easy-publish-check"
PROFILE_PATH = PROFILE_DIR / "profile.json"
PROJECT_CONFIG_NAME = ".easy-publish.json"

GIT_PLATFORMS = ("github", "gitlab", "gitee", "gitea")
ALL_PLATFORMS = ("github", "gitlab", "gitee", "gitea", "jetbrains")

PLATFORM_LABELS = {
    "github": "GitHub",
    "gitlab": "GitLab",
    "gitee": "Gitee 码云",
    "gitea": "Gitea",
    "jetbrains": "JetBrains Marketplace (IDEA 插件库)",
}

# 各 Git 平台的 Web 发布页（release notes 填写页）
RELEASE_WEB_PATHS = {
    "github": "/releases/new?tag={tag}",
    "gitlab": "/-/releases/new?tag_name={tag}",
    "gitee": "/releases/new?tag_name={tag}",
    "gitea": "/releases/new?tag_name={tag}",
}

SKIP_SCAN_DIRS = {
    ".git", "node_modules", "target", "build", "dist", "out",
    ".idea", ".gradle", ".vscode", "__pycache__", ".venv", "venv",
}
SCAN_FILE_SUFFIXES = {
    ".py", ".java", ".kt", ".groovy", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yml", ".yaml", ".properties", ".xml", ".gradle", ".kts",
    ".env", ".cfg", ".conf", ".ini", ".toml", ".sh", ".bat", ".ps1", ".md",
}

# ---------------------------------------------------------------- 输出工具


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


class Mark:
    PASS = "[PASS]"
    WARN = "[WARN]"
    FAIL = "[FAIL]"
    INFO = "[INFO]"


# ---------------------------------------------------------------- 进程执行


def run(cmd, cwd=None, check=False, capture=True, env=None):
    """执行外部命令；返回 subprocess.CompletedProcess。命令不存在时返回 127。"""
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=check,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            env=env,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            cmd, 127, "", f"命令未找到: {cmd[0]}"
        )


def git(args, project, check=False):
    return run(["git"] + args, cwd=project, check=check)


def git_text(args, project):
    """取 git 命令输出；失败返回空字符串。"""
    p = git(args, project)
    return p.stdout.strip() if p.returncode == 0 else ""


# ---------------------------------------------------------------- JSON 配置


def read_utf8(path):
    """读取文本；utf-8-sig 可兼容 Windows 编辑器误存的 BOM。"""
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return default
    except Exception:
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_profile():
    """读取全局发布人档案；不存在返回 None。"""
    return load_json(PROFILE_PATH, default=None)


def save_profile(profile):
    save_json(PROFILE_PATH, profile)
    try:
        PROFILE_PATH.chmod(0o600)  # 仅当前用户可读写（类 Unix 生效）
    except Exception:
        pass


def project_root(start=None):
    """定位 git 仓库根目录；非 git 项目时回退为给定目录/当前目录。"""
    start = Path(start or os.getcwd()).resolve()
    p = git(["rev-parse", "--show-toplevel"], start)
    if p.returncode == 0 and p.stdout.strip():
        return Path(p.stdout.strip())
    return start


def project_config_path(project):
    return Path(project) / PROJECT_CONFIG_NAME


def load_project_config(project):
    return load_json(project_config_path(project), default={}) or {}


def save_project_config(project, cfg):
    save_json(project_config_path(project), cfg)
    # 确保本地配置不会被提交
    gi = Path(project) / ".gitignore"
    try:
        lines = gi.read_text(encoding="utf-8-sig", errors="replace").splitlines() if gi.exists() else []
    except Exception:
        lines = []
    if PROJECT_CONFIG_NAME not in lines:
        with gi.open("a", encoding="utf-8") as f:
            if lines and lines[-1].strip():
                f.write("\n")
            f.write(PROJECT_CONFIG_NAME + "\n")


# ---------------------------------------------------------------- 项目类型探测


def detect_project_types(project):
    """返回项目包含的工程类型集合。"""
    project = Path(project)
    types = []
    if (project / "package.json").exists():
        types.append("node")
    if list(project.glob("**/src/main/resources/META-INF/plugin.xml")) or \
            (project / "plugin.xml").exists():
        types.append("intellij")
    if (project / "build.gradle").exists() or \
            (project / "build.gradle.kts").exists() or \
            (project / "settings.gradle").exists() or \
            (project / "settings.gradle.kts").exists():
        types.append("gradle")
    if (project / "pom.xml").exists():
        types.append("maven")
    if (project / "pyproject.toml").exists() or \
            (project / "setup.py").exists() or \
            (project / "setup.cfg").exists():
        types.append("python")
    return types


def find_plugin_xml(project):
    project = Path(project)
    hits = sorted(project.glob("**/src/main/resources/META-INF/plugin.xml"))
    if hits:
        return hits[0]
    top = project / "plugin.xml"
    return top if top.exists() else None


# ---------------------------------------------------------------- 版本读写
#
# 每个 handler 返回 (version, raw_text)；write_back 用新号原地替换，保持风格。

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")


def _read_package_json(project):
    f = Path(project) / "package.json"
    if not f.exists():
        return None
    data = load_json(f)
    return data.get("version") if isinstance(data, dict) else None


def _read_gradle_properties(project):
    f = Path(project) / "gradle.properties"
    if not f.exists():
        return None, None
    text = f.read_text(encoding="utf-8-sig", errors="replace")
    for key in ("pluginVersion", "version"):
        m = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([^\s#]+)", text)
        if m:
            return m.group(1).strip(), key
    return None, None


def _read_gradle_build(project, filename):
    f = Path(project) / filename
    if not f.exists():
        return None
    text = f.read_text(encoding="utf-8-sig", errors="replace")
    m = re.search(r"""(?m)^\s*version\s*(?:=|\s)\s*['"]([^'"]+)['"]""", text)
    return m.group(1).strip() if m else None


def _read_pom_version(project):
    f = Path(project) / "pom.xml"
    if not f.exists():
        return None
    text = f.read_text(encoding="utf-8-sig", errors="replace")
    # 跳过 <parent> 块，取项目自身的第一个 <version>
    body = re.sub(r"<parent>.*?</parent>", "", text, flags=re.S)
    m = re.search(r"<version>\s*([^<\s]+)\s*</version>", body)
    return m.group(1).strip() if m else None


def _read_plugin_xml_version(project):
    f = find_plugin_xml(project)
    if not f:
        return None
    m = re.search(r"<version>\s*([^<\s]+)\s*</version>", f.read_text(encoding="utf-8-sig", errors="replace"))
    return m.group(1).strip() if m else None


def _read_pyproject(project):
    f = Path(project) / "pyproject.toml"
    if not f.exists():
        return None
    text = f.read_text(encoding="utf-8-sig", errors="replace")
    m = re.search(r"(?ms)^\[project\].*?^\s*version\s*=\s*['\"]([^'\"]+)['\"]", text)
    return m.group(1).strip() if m else None


def _read_setup_py(project):
    f = Path(project) / "setup.py"
    if not f.exists():
        return None
    m = re.search(r"""version\s*=\s*['"]([^'"]+)['"]""", f.read_text(encoding="utf-8-sig", errors="replace"))
    return m.group(1).strip() if m else None


def list_version_files(project):
    """
    返回当前项目所有携带版本号的清单：
    [(kind, path, version), ...]，version 可能为 None（文件存在但未声明版本）。
    """
    project = Path(project)
    items = []

    if (project / "package.json").exists():
        items.append(("package.json", project / "package.json", _read_package_json(project)))

    gp = project / "gradle.properties"
    if gp.exists():
        v, key = _read_gradle_properties(project)
        items.append(("gradle.properties", gp, v))

    for fn in ("build.gradle", "build.gradle.kts"):
        if (project / fn).exists():
            items.append((fn, project / fn, _read_gradle_build(project, fn)))

    if (project / "pom.xml").exists():
        items.append(("pom.xml", project / "pom.xml", _read_pom_version(project)))

    pxml = find_plugin_xml(project)
    if pxml:
        items.append(("plugin.xml", pxml, _read_plugin_xml_version(project)))

    if (project / "pyproject.toml").exists():
        items.append(("pyproject.toml", project / "pyproject.toml", _read_pyproject(project)))
    if (project / "setup.py").exists():
        items.append(("setup.py", project / "setup.py", _read_setup_py(project)))

    return items


CANONICAL_ORDER = [
    "gradle.properties", "package.json", "build.gradle", "build.gradle.kts",
    "pom.xml", "plugin.xml", "pyproject.toml", "setup.py",
]


def current_version(project):
    """按权威顺序取项目当前版本；取不到再回退到最新 git tag。"""
    found = {k: v for k, _, v in list_version_files(project) if v}
    for kind in CANONICAL_ORDER:
        if kind in found:
            return found[kind], kind
    tag = latest_tag(project)
    if tag:
        return tag.lstrip("v"), "git-tag"
    return None, None


def latest_tag(project):
    tags = git_text(["tag", "--sort=-v:refname"], project)
    lines = [t for t in tags.splitlines() if t.strip()]
    return lines[0].strip() if lines else ""


def write_version(kind, path, new_version):
    """把指定清单中的版本号原地替换为 new_version，返回是否改动。"""
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    original = text

    if kind == "package.json":
        data = json.loads(text)
        if isinstance(data, dict) and data.get("version"):
            data["version"] = new_version
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return True
        return False

    if kind == "gradle.properties":
        key = "pluginVersion" if re.search(
            r"(?m)^\s*pluginVersion\s*=", text) else "version"
        text = re.sub(
            rf"(?m)^(\s*{key}\s*=\s*)[^\s#]+",
            lambda m: m.group(1) + new_version,
            text,
            count=1,
        )

    elif kind in ("build.gradle", "build.gradle.kts"):
        text = re.sub(
            r"""(?m)^(\s*version\s*(?:=|\s)\s*)['"][^'"]+['"]""",
            lambda m: m.group(1) + "'" + new_version + "'",
            text,
            count=1,
        )

    elif kind == "pom.xml":
        body_no_parent = re.sub(r"<parent>.*?</parent>", "", text, flags=re.S)
        m = re.search(r"<version>\s*[^<\s]+\s*</version>", body_no_parent)
        if not m:
            return False
        target = m.group(0)
        text = text.replace(target, f"<version>{new_version}</version>", 1)

    elif kind == "plugin.xml":
        text = re.sub(
            r"<version>\s*[^<\s]+\s*</version>",
            f"<version>{new_version}</version>",
            text,
            count=1,
        )

    elif kind == "pyproject.toml":
        text = re.sub(
            r"((?ms)^\[project\].*?^\s*version\s*=\s*)['\"][^'\"]+['\"]",
            lambda m: m.group(1) + '"' + new_version + '"',
            text,
            count=1,
        )

    elif kind == "setup.py":
        text = re.sub(
            r"""(version\s*=\s*)['"][^'"]+['"]""",
            lambda m: m.group(1) + "'" + new_version + "'",
            text,
            count=1,
        )

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


# ---------------------------------------------------------------- 语义化版本


def bump_semver(version, level):
    """major/minor/patch 递进；预发布版本（如 1.0.0-rc.1）转正为同级 release。"""
    base = re.split(r"[-+]", version, maxsplit=1)[0]
    parts = base.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"非标准语义化版本号: {version}")
    major, minor, patch = (int(x) for x in parts)
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"未知级别: {level}")


def suggest_level(project):
    """
    依据最近一个 tag 之后的提交信息（Conventional Commits）推断版本级别：
    BREAKING CHANGE / feat!: -> major；feat -> minor；其余 -> patch。
    """
    last = latest_tag(project)
    rng = f"{last}..HEAD" if last else None
    log = git_text(["log", rng, "--pretty=format:%s%n%b", "--no-merges"] if rng
                   else ["log", "--pretty=format:%s%n%b", "--no-merges"], project)
    text = log or ""
    if re.search(r"BREAKING[ -]CHANGE|^\s*\w+(?:\([^)]*\))?!:", text, re.M | re.I):
        return "major", text
    if re.search(r"(?im)^\s*feat(?:\([^)]*\))?!?:", text):
        return "minor", text
    return "patch", text


# ---------------------------------------------------------------- CHANGELOG


def find_changelog(project):
    for name in ("CHANGELOG.md", "changelog.md", "CHANGES.md", "更新日志.md"):
        f = Path(project) / name
        if f.exists():
            return f
    return None


def update_changelog(project, new_version, release_date=None):
    """
    按 Keep a Changelog 约定把 [Unreleased] 段落转成正式版本；
    没有 CHANGELOG.md 时返回 None（由调用方决定是否创建）。
    """
    release_date = release_date or date.today().isoformat()
    f = find_changelog(project)
    if not f:
        return None
    text = f.read_text(encoding="utf-8-sig", errors="replace")
    header = f"## [{new_version}] - {release_date}"

    m = re.search(r"(?im)^##\s*\[\s*unreleased\s*\][^\n]*", text)
    if m:
        text = text[:m.start()] + header + text[m.end():]
        # 在文件顶部补一个新的 Unreleased 占位
        title_end = text.find("\n")
        insert_at = text.find("\n## ", title_end + 1)
        unreleased = "## [Unreleased]\n\n### Added\n- \n\n### Changed\n- \n\n### Fixed\n- \n\n"
        if insert_at != -1:
            text = text[:insert_at + 1] + unreleased + text[insert_at + 1:]
    elif re.search(rf"(?m)^##\s*\[?{re.escape(new_version)}\]?", text):
        pass  # 已存在该版本段落
    else:
        # 无 Unreleased：在标题之后插入版本段落
        idx = text.find("\n## ")
        block = header + "\n\n- \n"
        if idx == -1:
            text = text.rstrip() + "\n\n" + block
        else:
            text = text[:idx + 1] + block + "\n" + text[idx + 1:]

    f.write_text(text, encoding="utf-8")
    return f


# ---------------------------------------------------------------- Git 辅助


def git_identity(project, scope="local"):
    name = git_text(["config", f"--{scope}", "user.name"], project)
    email = git_text(["config", f"--{scope}", "user.email"], project)
    return name or None, email or None


def working_tree_dirty(project):
    return bool(git_text(["status", "--porcelain"], project))


def current_branch(project):
    return git_text(["rev-parse", "--abbrev-ref", "HEAD"], project)


def list_remotes(project):
    out = git_text(["remote"], project)
    return [r.strip() for r in out.splitlines() if r.strip()]


def remote_url(project, name):
    return git_text(["remote", "get-url", name], project)


def tracked_files(project):
    out = git_text(["ls-files"], project)
    return [l.strip() for l in out.splitlines() if l.strip()]


def ssh_to_https(url):
    """git@host:path.git -> https://host/path（去掉 .git）。"""
    m = re.match(r"git@([^:]+):(.+)$", url)
    if m:
        url = f"https://{m.group(1)}/{m.group(2)}"
    if url.endswith(".git"):
        url = url[:-4]
    return url


def release_web_url(platform, remote_https_url, tag):
    path_tpl = RELEASE_WEB_PATHS.get(platform)
    if not path_tpl:
        return None
    return remote_https_url.rstrip("/") + path_tpl.format(tag=tag)
