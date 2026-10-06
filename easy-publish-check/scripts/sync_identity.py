#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把全局发布人身份统一写入项目各处：

1. Git 提交身份 user.name / user.email（默认写仓库级 local，--global-git 写全局）
2. IDEA 插件 plugin.xml 的 <vendor name/email/url>（核心：vendor 必须是真实发布人，不是项目名）
3. package.json 的 author 字段
4. pom.xml 的 <developers> 声明

默认仅预览（dry-run），加 --apply 才真正写入。
Gradle Kotlin/Groovy DSL 中的 vendor 配置形态多变，不在此脚本改写，
请按 references/platforms.md 的 JetBrains 章节手工/由 AI 助手修改。

用法：
  python sync_identity.py [--project DIR] [--apply] [--global-git]
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_common import (  # noqa: E402
    Mark, _utf8_stdio, find_plugin_xml, git, git_identity,
    load_profile, project_root,
)


def plan_git(project, profile, use_global):
    scope = "global" if use_global else "local"
    name, email = git_identity(project, scope)
    plans = []
    if name != profile["name"]:
        plans.append(("git", f"config --{scope} user.name -> {profile['name']}"))
    if email != profile["email"]:
        plans.append(("git", f"config --{scope} user.email -> {profile['email']}"))
    return plans


def apply_git(project, profile, use_global):
    scope = "--global" if use_global else "--local"
    git(["config", scope, "user.name", profile["name"]], project)
    git(["config", scope, "user.email", profile["email"]], project)


def plan_plugin_xml(project, profile):
    pxml = find_plugin_xml(project)
    if not pxml:
        return None, []
    text = pxml.read_text(encoding="utf-8-sig", errors="replace")
    url = profile.get("vendor_url", "")
    new_vendor = (
        f'<vendor email="{profile["email"]}"'
        + (f' url="{url}"' if url else "")
        + f'>{profile.get("jetbrains_vendor") or profile["name"]}</vendor>'
    )
    m = re.search(r"<vendor[^>]*>.*?</vendor>\s*", text, re.S)
    if m:
        if m.group(0).strip() == new_vendor:
            return pxml, []
        return pxml, [("plugin.xml", f"替换 vendor: {m.group(0).strip()} -> {new_vendor}")]
    if "</idea-plugin>" not in text:
        return pxml, [("plugin.xml", "缺少 </idea-plugin>，无法插入 vendor，请人工检查")]
    return pxml, [("plugin.xml", f"新增 vendor 声明: {new_vendor}")]


def apply_plugin_xml(project, profile):
    pxml = find_plugin_xml(project)
    text = pxml.read_text(encoding="utf-8-sig", errors="replace")
    url = profile.get("vendor_url", "")
    new_vendor = (
        f'<vendor email="{profile["email"]}"'
        + (f' url="{url}"' if url else "")
        + f'>{profile.get("jetbrains_vendor") or profile["name"]}</vendor>'
    )
    m = re.search(r"<vendor[^>]*>.*?</vendor>\s*", text, re.S)
    if m:
        text = text[:m.start()] + new_vendor + "\n    " + text[m.end():]
    else:
        text = text.replace("</idea-plugin>", f"    {new_vendor}\n</idea-plugin>", 1)
    pxml.write_text(text, encoding="utf-8")


def plan_package_json(project, profile):
    pj = Path(project) / "package.json"
    if not pj.exists():
        return None, []
    import json
    try:
        data = json.loads(pj.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception as e:
        return pj, [("package.json", f"解析失败: {e}")]
    url = profile.get("vendor_url", "")
    want = {"name": profile["name"], "email": profile["email"]}
    if url:
        want["url"] = url
    cur = data.get("author")
    if isinstance(cur, dict) and cur.get("name") == profile["name"] and \
            cur.get("email") == profile["email"]:
        return pj, []
    if isinstance(cur, str) and profile["name"] in cur and profile["email"] in cur:
        return pj, []
    return pj, [("package.json", f"author -> {want['name']} <{want['email']}>")]


def apply_package_json(project, profile):
    import json
    pj = Path(project) / "package.json"
    data = json.loads(pj.read_text(encoding="utf-8-sig", errors="replace"))
    url = profile.get("vendor_url", "")
    author = {"name": profile["name"], "email": profile["email"]}
    if url:
        author["url"] = url
    data["author"] = author
    pj.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plan_pom(project, profile):
    pom = Path(project) / "pom.xml"
    if not pom.exists():
        return None, []
    text = pom.read_text(encoding="utf-8-sig", errors="replace")
    m = re.search(r"<developers>.*?</developers>", text, re.S)
    if m and profile["name"] in m.group(0):
        return pom, []
    if m:
        return pom, [("pom.xml", "已有 <developers> 但不含发布人姓名，请人工核对")]
    if "</project>" not in text:
        return pom, [("pom.xml", "未找到 </project>，无法插入 developers")]
    block = (
        "    <developers>\n"
        "        <developer>\n"
        f"            <name>{profile['name']}</name>\n"
        f"            <email>{profile['email']}</email>\n"
        "        </developer>\n"
        "    </developers>\n"
    )
    return pom, [("pom.xml", "新增 <developers> 发布人声明")]


def apply_pom(project, profile):
    pom = Path(project) / "pom.xml"
    text = pom.read_text(encoding="utf-8-sig", errors="replace")
    block = (
        "    <developers>\n"
        "        <developer>\n"
        f"            <name>{profile['name']}</name>\n"
        f"            <email>{profile['email']}</email>\n"
        "        </developer>\n"
        "    </developers>\n"
    )
    pom.write_text(text.replace("</project>", block + "</project>", 1), encoding="utf-8")


def main():
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="统一项目发布人身份")
    ap.add_argument("--project", default=None)
    ap.add_argument("--apply", action="store_true", help="真正写入（默认仅预览）")
    ap.add_argument("--global-git", action="store_true", help="Git 身份写入 --global 而非仓库级")
    args = ap.parse_args()

    project = project_root(args.project)
    profile = load_profile()
    if not profile or not profile.get("name") or not profile.get("email"):
        print(f"{Mark.FAIL} 全局档案缺失，请先运行: python profile.py init")
        return 1

    plans = []
    plans += plan_git(project, profile, args.global_git)
    _, p = plan_plugin_xml(project, profile)
    plans += p
    _, p = plan_package_json(project, profile)
    plans += p
    _, p = plan_pom(project, profile)
    plans += p

    if not plans:
        print(f"{Mark.PASS} 项目各处身份均已与全局档案一致，无需修改")
        return 0

    mode = "写入" if args.apply else "预览（加 --apply 执行写入）"
    print(f"=== 身份统一计划（{mode}）: {project} ===")
    for area, action in plans:
        print(f"  - [{area}] {action}")

    if not args.apply:
        return 0

    # 按计划实际存在的目标执行
    apply_git(project, profile, args.global_git)
    _pxml, pxml_plans = plan_plugin_xml(project, profile)
    if pxml_plans and "无法插入" not in pxml_plans[0][1]:
        apply_plugin_xml(project, profile)
    _pj, pj_plans = plan_package_json(project, profile)
    if pj_plans and "解析失败" not in pj_plans[0][1]:
        apply_package_json(project, profile)
    _pom, pom_plans = plan_pom(project, profile)
    if pom_plans and pom_plans[0][1].startswith("新增"):
        apply_pom(project, profile)

    print(f"\n{Mark.PASS} 身份信息已写入，建议随后运行 preflight.py 复核")
    return 0


if __name__ == "__main__":
    sys.exit(main())
