#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布前审查（pre-release review）。

用法：
  python preflight.py [--project 项目目录] [--json] [--strict]

检查项：Git 身份与全局档案是否一致、最近提交作者、版本号在各清单中是否一致、
IDEA 插件 plugin.xml 的 vendor 是否为真实发布人（而非项目名/占位名）、
README/LICENSE/CHANGELOG/.gitignore、误提交的构建产物、硬编码密钥、
package.json/pom.xml 作者信息、未推送提交等。

退出码：存在 FAIL 项时为 1（--strict 下 WARN 也视为不通过），否则 0。
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_common import (  # noqa: E402
    Mark, _utf8_stdio, current_version, detect_project_types,
    find_plugin_xml, git, git_identity, git_text, list_remotes,
    list_version_files, load_profile, load_project_config, project_root,
    tracked_files, working_tree_dirty, current_branch,
    SCAN_FILE_SUFFIXES, SKIP_SCAN_DIRS,
)

# 命中即视为硬编码密钥（FAIL）
SECRET_HARD_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
     "私钥内容被提交"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "GitHub Personal Token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub Fine-grained Token"),
    (re.compile(r"glpat-[A-Za-z0-9_\-]{20}"), "GitLab Token"),
]
# 疑似账号密码配置（WARN，需人工确认）
SECRET_SOFT_PATTERN = re.compile(
    r"""(?ix)(password|passwd|secret|token|api[_-]?key|access[_-]?key)
        \s*[:=]\s*['"]?([^\s"'#<>]{8,})"""
)
SECRET_WHITELIST = re.compile(
    r"(example|sample|placeholder|xxxx+|your[-_ ]|process\.|getenv|environ|"
    r"\$\{|\$ENV:|System\.|os\.environ|@Value|configService)",
    re.I,
)
ARTIFACT_PATTERN = re.compile(
    r"(^|/)(node_modules|target|build|dist|out|\.idea|\.gradle)(/|$)|"
    r"\.(iml|class|pyc)$"
)
README_SECTIONS = [
    ("安装 / Install", re.compile(r"^#{1,4}\s.*(安装|install|快速开始|quick\s?start)", re.I | re.M)),
    ("使用 / Usage", re.compile(r"^#{1,4}\s.*(使用|usage|how to|用法|运行)", re.I | re.M)),
    ("许可证 / License", re.compile(r"^#{1,4}\s.*(许可|license|协议)", re.I | re.M)),
]


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, area, msg, fix=""):
        self.items.append({"level": level, "area": area, "msg": msg, "fix": fix})

    def fails(self):
        return [i for i in self.items if i["level"] == Mark.FAIL]

    def warns(self):
        return [i for i in self.items if i["level"] == Mark.WARN]

    def passes(self):
        return [i for i in self.items if i["level"] == Mark.PASS]


def check_git_and_profile(project, rpt):
    p = git(["rev-parse", "--is-inside-work-tree"], project)
    if p.returncode != 0:
        rpt.add(Mark.FAIL, "Git", "当前目录不是 Git 仓库", "先执行 git init 并完成首次提交")
        return False
    profile = load_profile()
    if not profile or not profile.get("name") or not profile.get("email"):
        rpt.add(Mark.FAIL, "发布人身份",
                "未配置全局发布人档案（姓名/邮箱）",
                "运行 python profile.py init 录入，后续所有项目复用")
        return False
    rpt.add(Mark.PASS, "发布人身份",
            f"全局档案: {profile['name']} <{profile['email']}>")

    local_name, local_email = git_identity(project, "local")
    glob_name, glob_email = git_identity(project, "global")
    eff_name = local_name or glob_name
    eff_email = local_email or glob_email
    scope = "local（仓库级）" if local_name else "global（全局）"
    if not eff_name or not eff_email:
        rpt.add(Mark.FAIL, "Git 身份", "Git 未配置 user.name/user.email",
                "运行 python sync_identity.py --apply")
    elif eff_name != profile["name"] or eff_email != profile["email"]:
        rpt.add(Mark.FAIL, "Git 身份",
                f"当前生效身份({scope}) {eff_name} <{eff_email}> 与档案 "
                f"{profile['name']} <{profile['email']}> 不一致",
                "运行 python sync_identity.py --apply 统一为仓库级配置")
    else:
        rpt.add(Mark.PASS, "Git 身份", f"提交身份一致({scope}): {eff_name} <{eff_email}>")

    # 最近提交的作者是否混入其它身份
    log = git_text(["log", "-20", "--pretty=format:%an|%ae"], project)
    bad = []
    for line in log.splitlines():
        if "|" in line:
            an, ae = line.split("|", 1)
            if ae.strip() != profile["email"] and (an.strip(), ae.strip()) not in bad:
                bad.append((an.strip(), ae.strip()))
    if bad:
        detail = "; ".join(f"{n} <{e}>" for n, e in bad[:5])
        rpt.add(Mark.WARN, "Git 历史",
                f"最近 20 条提交中存在其它作者身份: {detail}",
                "历史提交身份不影响本次发布；如需修正可 git commit --amend / filter-repo（有风险，先备份）")
    else:
        rpt.add(Mark.PASS, "Git 历史", "最近提交作者身份统一")
    return True


def check_worktree(project, rpt):
    if working_tree_dirty(project):
        rpt.add(Mark.WARN, "工作区", "存在未提交改动",
                "发布前应提交或暂存所有改动：git status / git add & commit")
    else:
        rpt.add(Mark.PASS, "工作区", "工作区干净")
    branch = current_branch(project)
    if branch:
        rpt.add(Mark.INFO, "分支", f"当前分支: {branch}")
    # 未推送提交
    up = git_text(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], project)
    if up:
        ahead = git_text(["rev-list", "--count", f"{up}..HEAD"], project)
        try:
            n = int(ahead)
            if n > 0:
                rpt.add(Mark.WARN, "推送状态", f"有 {n} 个提交尚未推送到 {up}")
            else:
                rpt.add(Mark.PASS, "推送状态", "本地与远端一致")
        except ValueError:
            pass
    else:
        rpt.add(Mark.INFO, "推送状态", "分支尚未设置上游，首次发布时由 publish_git 处理")


def check_versions(project, rpt):
    items = [(k, f, v) for k, f, v in list_version_files(project) if v]
    if not items:
        rpt.add(Mark.WARN, "版本号", "未发现任何版本声明文件",
                "建议在 gradle.properties / package.json 等处维护语义化版本")
        return
    versions = sorted({v for _, _, v in items})
    detail = ", ".join(f"{k}={v}" for k, _, v in items)
    if len(versions) > 1:
        rpt.add(Mark.FAIL, "版本号", f"各清单版本不一致: {detail}",
                "运行 python bump_version.py --set <统一版本号> 同步")
    else:
        rpt.add(Mark.PASS, "版本号", f"版本一致: {versions[0]}（{detail}）")


def check_docs(project, rpt, version):
    readme = None
    for name in ("README.md", "readme.md", "README.MD"):
        f = Path(project) / name
        if f.exists():
            readme = f
            break
    if not readme:
        rpt.add(Mark.FAIL, "README", "缺少 README.md 项目介绍",
                "由发布流程多轮问答生成，模板见 assets/README.template.md")
    else:
        text = readme.read_text(encoding="utf-8-sig", errors="replace")
        missing = [label for label, pat in README_SECTIONS if not pat.search(text)]
        if missing:
            rpt.add(Mark.WARN, "README", f"缺少章节: {', '.join(missing)}")
        else:
            rpt.add(Mark.PASS, "README", "章节完整（安装/使用/许可证）")

    lic = any((Path(project) / n).exists()
              for n in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"))
    rpt.add(Mark.PASS if lic else Mark.WARN, "LICENSE",
            "LICENSE 已存在" if lic else "缺少 LICENSE 开源协议文件")

    gi = Path(project) / ".gitignore"
    rpt.add(Mark.PASS if gi.exists() else Mark.WARN, ".gitignore",
            ".gitignore 已存在" if gi.exists() else "缺少 .gitignore")

    cl = None
    for name in ("CHANGELOG.md", "changelog.md", "CHANGES.md", "更新日志.md"):
        f = Path(project) / name
        if f.exists():
            cl = f
            break
    if not cl:
        rpt.add(Mark.WARN, "CHANGELOG", "缺少 CHANGELOG.md 更新日志",
                "模板见 assets/CHANGELOG.template.md")
    elif version and not re.search(
            rf"(?m)^##\s*\[?\s*{re.escape(version)}\b", cl.read_text(encoding="utf-8-sig", errors="replace")):
        rpt.add(Mark.WARN, "CHANGELOG", f"未找到版本 {version} 的更新条目",
                "bump_version 会自动把 Unreleased 转为本版本；或手工补充本版本迭代内容")
    else:
        rpt.add(Mark.PASS, "CHANGELOG", "更新日志已覆盖当前版本")


def check_tracked_hygiene(project, rpt):
    files = tracked_files(project)
    if not files:
        rpt.add(Mark.WARN, "Git", "仓库没有任何被跟踪文件")
        return
    artifacts = [f for f in files if ARTIFACT_PATTERN.search(f.replace("\\", "/"))]
    env_files = [f for f in files if re.search(r"(^|/)\.env(\.|$)", f.replace("\\", "/"))]
    if env_files:
        rpt.add(Mark.FAIL, "敏感文件",
                f".env 被纳入版本管理: {', '.join(env_files[:5])}",
                "git rm --cached <file> 并加入 .gitignore")
    if artifacts:
        rpt.add(Mark.WARN, "仓库卫生",
                f"构建产物/IDE 文件疑似被跟踪({len(artifacts)} 个): "
                f"{', '.join(artifacts[:6])}",
                "git rm -r --cached <path> 并补充 .gitignore")
    if not artifacts and not env_files:
        rpt.add(Mark.PASS, "仓库卫生", "未发现被跟踪的构建产物")


def _iter_scan_files(project, files):
    for rel in files:
        p = Path(project) / rel
        parts = set(p.parts)
        if parts & SKIP_SCAN_DIRS:
            continue
        if p.suffix.lower() not in SCAN_FILE_SUFFIXES and p.name not in (".env",):
            continue
        try:
            if p.stat().st_size > 512 * 1024:
                continue
            yield rel, p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue


def check_secrets(project, rpt):
    files = tracked_files(project) or []
    hard_hits, soft_hits = [], []
    for rel, text in _iter_scan_files(project, files):
        for i, line in enumerate(text.splitlines(), 1):
            for pat, label in SECRET_HARD_PATTERNS:
                if pat.search(line):
                    hard_hits.append(f"{rel}:{i} ({label})")
            if SECRET_SOFT_PATTERN.search(line) and not SECRET_WHITELIST.search(line):
                m = SECRET_SOFT_PATTERN.search(line)
                soft_hits.append(f"{rel}:{i} ({m.group(1)})")
    if hard_hits:
        rpt.add(Mark.FAIL, "密钥扫描",
                f"发现疑似真实密钥 {len(hard_hits)} 处: {'; '.join(hard_hits[:6])}",
                "立即移除并轮换该密钥；改用环境变量/配置注入")
    if soft_hits:
        rpt.add(Mark.WARN, "密钥扫描",
                f"发现疑似硬编码凭据 {len(soft_hits)} 处（需人工确认）: "
                f"{'; '.join(soft_hits[:6])}",
                "确认为敏感信息则移除并改用环境变量")
    if not hard_hits and not soft_hits:
        rpt.add(Mark.PASS, "密钥扫描", "未发现硬编码密钥/凭据")


def check_intellij(project, rpt, profile):
    pxml = find_plugin_xml(project)
    if not pxml:
        return
    text = pxml.read_text(encoding="utf-8-sig", errors="replace")

    def tag(name):
        m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", text, re.S)
        return m.group(1).strip() if m else None

    plugin_id = tag("id")
    plugin_name = tag("name")
    if not plugin_id:
        rpt.add(Mark.FAIL, "IDEA 插件", "plugin.xml 缺少 <id>（全局唯一标识）")
    else:
        rpt.add(Mark.PASS, "IDEA 插件", f"插件 id={plugin_id}, name={plugin_name}")
    if not plugin_name:
        rpt.add(Mark.FAIL, "IDEA 插件", "plugin.xml 缺少 <name>")

    vm = re.search(r"<vendor([^>]*)>(.*?)</vendor>", text, re.S)
    if not vm:
        rpt.add(Mark.FAIL, "IDEA 插件", "plugin.xml 缺少 <vendor> 供应商声明",
                "运行 python sync_identity.py --apply 自动写入发布人姓名/邮箱")
    else:
        attrs, vendor_text = vm.group(1), vm.group(2).strip()
        email_m = re.search(r'email\s*=\s*"([^"]+)"', attrs)
        problems = []
        if not email_m:
            problems.append("缺少 email 属性")
        # 核心痛点：vendor 不能是产品名/项目名/占位名
        slug_candidates = {
            (plugin_name or "").lower().replace(" ", ""),
            pxml.parents[3].name.lower() if len(pxml.parents) >= 4 else "",
            "aitools", "yourcompany", "your company", "plugin vendor",
        }
        slug_candidates.discard("")
        if vendor_text.lower().replace(" ", "") in slug_candidates:
            problems.append(f"供应商名“{vendor_text}”疑似项目名/占位名，必须是真实姓名或公司名")
        elif profile and vendor_text != profile["name"] and \
                vendor_text != profile.get("jetbrains_vendor"):
            problems.append(
                f"供应商名“{vendor_text}”与档案姓名“{profile['name']}”不一致")
        if problems:
            rpt.add(Mark.FAIL, "IDEA 插件",
                    "vendor 声明有问题: " + "；".join(problems),
                    "运行 python sync_identity.py --apply 统一修正")
        else:
            rpt.add(Mark.PASS, "IDEA 插件",
                    f"供应商正确: {vendor_text} <{email_m.group(1) if email_m else ''}>")

    if not tag("description"):
        rpt.add(Mark.WARN, "IDEA 插件", "缺少 <description>（市场页展示，建议 ≥40 字符）")
    if not re.search(r"<change-notes\s*/?>", text) and not tag("change-notes"):
        rpt.add(Mark.WARN, "IDEA 插件", "缺少 <change-notes> 版本更新说明")
    if not re.search(r'<idea-version[^>]+since-build', text):
        rpt.add(Mark.WARN, "IDEA 插件", "未声明 <idea-version since-build=...> 兼容范围")
    res_dir = pxml.parent
    icons = list(res_dir.rglob("*.svg")) + list(res_dir.rglob("*.png"))
    if not icons:
        rpt.add(Mark.WARN, "IDEA 插件", "未提供插件图标（建议 40x40 与 80x80）")


def check_identity_manifests(project, rpt, profile):
    if not profile:
        return
    pj = Path(project) / "package.json"
    if pj.exists():
        import json
        try:
            data = json.loads(pj.read_text(encoding="utf-8-sig", errors="replace"))
            author = data.get("author")
            if isinstance(author, dict):
                author = author.get("name", "")
            author = (author or "").strip()
            if not author:
                rpt.add(Mark.WARN, "package.json", "缺少 author 字段",
                        "运行 python sync_identity.py --apply")
            elif profile["name"] not in author:
                rpt.add(Mark.FAIL, "package.json",
                        f"author“{author}”与发布人“{profile['name']}”不一致",
                        "运行 python sync_identity.py --apply")
            else:
                rpt.add(Mark.PASS, "package.json", f"author 一致: {author}")
        except Exception as e:
            rpt.add(Mark.WARN, "package.json", f"解析失败: {e}")

    pom = Path(project) / "pom.xml"
    if pom.exists():
        text = pom.read_text(encoding="utf-8-sig", errors="replace")
        devs = re.search(r"<developers>(.*?)</developers>", text, re.S)
        if not devs or profile["name"] not in devs.group(1):
            rpt.add(Mark.WARN, "pom.xml", "缺少包含发布人姓名的 <developers> 声明",
                    "运行 python sync_identity.py --apply")
        else:
            rpt.add(Mark.PASS, "pom.xml", "developers 已包含发布人")


ABOUT_SUFFIXES = {
    ".kt", ".java", ".vue", ".tsx", ".ts", ".js", ".jsx", ".py",
    ".xml", ".md", ".json", ".html", ".fxml", ".kts", ".gradle",
}
ABOUT_NAME_RE = re.compile(r"about|关于|关于作者|联系", re.I)
ABOUT_CODE_RE = re.compile(
    r"(class\s+\w*About\w*(Action|Dialog|Panel|Window|View|Page|Component)?"
    r"|setAboutPanelOptions|role\s*:\s*['\"]about"
    r"|path\s*:\s*['\"]/about|name\s*:\s*['\"]about"
    r"|--about|AboutDialog|关于(我们|软件|作者|本)|联系作者|联系我们)",
    re.I,
)
CONTACT_README_RE = re.compile(
    r"^#{1,4}\s.*(联系作者|联系方式|联系我们|关于作者|contact|maintainer|author)",
    re.I | re.M,
)


def _iter_about_files(project, files):
    for rel in files:
        p = Path(project) / rel
        if set(p.parts) & SKIP_SCAN_DIRS:
            continue
        if p.suffix.lower() not in ABOUT_SUFFIXES:
            continue
        try:
            if p.stat().st_size > 256 * 1024:
                continue
            yield rel, p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue


def check_about_module(project, rpt, types, profile):
    """检测软件内是否存在「关于 / 联系作者」入口；缺失则按技术栈给生成建议。"""
    files = tracked_files(project) or []
    if not files:
        return
    evidence = []
    readme_contact = False
    for rel, text in _iter_about_files(project, files):
        low = rel.replace("\\", "/").lower()
        if ABOUT_NAME_RE.search(low) and ABOUT_CODE_RE.search(text):
            evidence.append(rel)
        elif low.endswith(("plugin.xml",)) and re.search(
                r"(?is)<action[^>]*(about|关于)", text):
            evidence.append(rel)
        elif re.search(r"class\s+\w*About\w*(Action|Dialog|Panel|Window)", text):
            evidence.append(rel)
        elif ABOUT_CODE_RE.search(text) and not low.endswith(".md"):
            evidence.append(rel)
        if low.endswith("readme.md") and CONTACT_README_RE.search(text):
            readme_contact = True

    pj = Path(project) / "package.json"
    frameworks, is_cli = set(), False
    if pj.exists():
        import json as _json
        try:
            data = _json.loads(pj.read_text(encoding="utf-8-sig"))
            deps = {**(data.get("dependencies") or {}),
                    **(data.get("devDependencies") or {})}
            for fw in ("electron", "vue", "react"):
                if any(k == fw or k.startswith(fw + "-") or k.startswith("@" + fw)
                       for k in deps):
                    frameworks.add(fw)
            is_cli = bool(data.get("bin"))
        except Exception:
            pass

    fix_doc = "按 references/about-module.md 对应模板生成，并把发布人姓名/邮箱/主页写入"
    if "intellij" in types:
        if evidence:
            rpt.add(Mark.PASS, "关于/联系", f"IDEA 插件已发现关于入口: {', '.join(sorted(set(evidence))[:3])}")
        else:
            rpt.add(Mark.FAIL, "关于/联系",
                    "IDEA 插件缺少「关于/联系作者」入口（Help 菜单 Action 或设置页）",
                    fix_doc + "；推荐新增 AboutAction.kt 并在 plugin.xml 注册到 HelpMenu")
        return
    if "electron" in frameworks:
        rpt.add(Mark.PASS if evidence else Mark.WARN, "关于/联系",
                "Electron 已配置 About 面板" if evidence else
                "Electron 应用缺少 About 面板（app.setAboutPanelOptions 或自定义关于窗口）",
                "" if evidence else fix_doc)
        return
    if frameworks & {"vue", "react"}:
        if evidence:
            rpt.add(Mark.PASS, "关于/联系", f"前端已发现关于页/入口: {', '.join(sorted(set(evidence))[:3])}")
        else:
            rpt.add(Mark.WARN, "关于/联系",
                    f"{'/'.join(sorted(frameworks))} 应用缺少「关于/联系作者」页面或菜单入口",
                    fix_doc + "；新增 About 页面、路由与菜单项")
        return
    if is_cli or "python" in types:
        if evidence:
            rpt.add(Mark.PASS, "关于/联系", "命令行已发现 --about/关于命令")
        elif readme_contact:
            rpt.add(Mark.PASS, "关于/联系", "CLI 项目 README 已含联系作者章节")
        else:
            rpt.add(Mark.WARN, "关于/联系",
                    "命令行工具缺少 --about 输出，README 也无联系作者章节",
                    fix_doc + "；CLI 增加 --about 输出块，或在 README 增加联系作者章节")
        return
    # 通用兜底（库/服务/其它）：README 联系章节即可
    if readme_contact:
        rpt.add(Mark.PASS, "关于/联系", "README 已含联系作者章节")
    else:
        rpt.add(Mark.WARN, "关于/联系",
                "未发现「关于/联系作者」模块或 README 联系章节",
                fix_doc + "；无界面项目至少在 README 增加联系作者章节")


def check_platforms(project, rpt):
    cfg = load_project_config(project)
    platforms = cfg.get("platforms", [])
    remotes = list_remotes(project)
    if platforms:
        missing = [p for p in platforms if p in ("github", "gitlab", "gitee", "gitea")
                   and p not in remotes]
        if missing:
            rpt.add(Mark.WARN, "发布目标",
                    f"已配置平台但缺少同名 remote: {', '.join(missing)}",
                    "运行 publish_git.py --remote <平台>=<地址> --save")
        else:
            rpt.add(Mark.PASS, "发布目标", f"已配置平台: {', '.join(platforms)}")
    elif remotes:
        rpt.add(Mark.INFO, "发布目标", f"现有 remotes: {', '.join(remotes)}（本次发布可再多选平台）")
    else:
        rpt.add(Mark.WARN, "发布目标", "尚未配置任何远端仓库")

    if "jetbrains" in platforms or detect_project_types(project).count("intellij"):
        token = any([
            __import__("os").environ.get("ORG_GRADLE_PROJECT_INTELIJ_PUBLISH_TOKEN"),
            __import__("os").environ.get("ORG_GRADLE_PROJECT_INTELLIJ_PLATFORM_PUBLISH_TOKEN"),
            __import__("os").environ.get("INTELLIJ_PUBLISH_TOKEN"),
        ])
        gp = Path(project) / "gradle.properties"
        if not token and not (gp.exists() and
                              re.search(r"(?i)intellij.*publish.*token\s*=",
                                        gp.read_text(encoding="utf-8-sig", errors="replace"))):
            rpt.add(Mark.WARN, "JetBrains",
                    "未检测到发布 Token（环境变量 ORG_GRADLE_PROJECT_INTELIJ_PUBLISH_TOKEN）",
                    "在 https://plugins.jetbrains.com/author/me/tokens 生成，仅通过环境变量传入")


def main():
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="发布前审查")
    ap.add_argument("--project", default=None, help="项目目录，默认当前目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON 报告")
    ap.add_argument("--strict", action="store_true", help="WARN 也视为不通过")
    args = ap.parse_args()

    project = project_root(args.project)
    rpt = Report()

    ok = check_git_and_profile(project, rpt)
    check_worktree(project, rpt)
    check_versions(project, rpt)
    version, _src = current_version(project)
    check_docs(project, rpt, version)
    check_tracked_hygiene(project, rpt)
    check_secrets(project, rpt)
    profile = load_profile()
    check_intellij(project, rpt, profile)
    check_identity_manifests(project, rpt, profile)
    check_about_module(project, rpt, detect_project_types(project), profile)
    check_platforms(project, rpt)

    if args.json:
        print(json.dumps({
            "project": str(project),
            "version": version,
            "types": detect_project_types(project),
            "items": rpt.items,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"=== 发布前审查报告: {project} ===")
        if version:
            print(f"当前版本: {version}    工程类型: {', '.join(detect_project_types(project)) or '未知'}\n")
        order = [Mark.FAIL, Mark.WARN, Mark.INFO, Mark.PASS]
        for level in order:
            group = [i for i in rpt.items if i["level"] == level]
            for i in group:
                line = f"{i['level']} [{i['area']}] {i['msg']}"
                print(line)
                if i["level"] in (Mark.FAIL, Mark.WARN) and i["fix"]:
                    print(f"       修复建议: {i['fix']}")
        nf, nw, np_ = len(rpt.fails()), len(rpt.warns()), len(rpt.passes())
        print(f"\n汇总: {nf} FAIL / {nw} WARN / {np_} PASS")

    if rpt.fails() or (args.strict and rpt.warns()):
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
