#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JetBrains Marketplace（IDEA 插件库）发布助手。

自动完成：
  1. 定位 Gradle Wrapper / 系统 Gradle，识别 IntelliJ Gradle 插件世代
     （1.x org.jetbrains.intellij 与 2.x org.jetbrains.intellij.platform）；
  2. 校验 plugin.xml 的 vendor/版本/change-notes 与发布 Token；
  3. 构建并校验插件包（--build-only），产出 build/distributions/*.zip；
  4. 正式上传 Marketplace（--apply）；默认只做预检与命令预览，不会上传。

Token 只允许通过环境变量或未入库的 gradle.properties 提供，脚本不接收、不打印、不落盘。

用法：
  python publish_jetbrains.py                         # 预检 + 打印将执行的命令
  python publish_jetbrains.py --build-only            # 构建 + verifyPlugin
  python publish_jetbrains.py --apply                 # 正式发布到 stable 渠道
  python publish_jetbrains.py --apply --channel beta  # 发布到 beta 渠道
"""

import argparse
import glob
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_common import (  # noqa: E402
    Mark, _utf8_stdio, current_version, find_plugin_xml,
    load_project_config, project_root, run, save_project_config,
)

TOKEN_ENVS = [
    "ORG_GRADLE_PROJECT_INTELLIJ_PUBLISH_TOKEN",          # 1.x 模板常见写法
    "ORG_GRADLE_PROJECT_INTELLIJPUBLISHTOKEN",
    "ORG_GRADLE_PROJECT_INTELLIJPLATFORMPUBLISHINGTOKEN",  # 2.x
    "INTELLIJ_PUBLISH_TOKEN",
]
MANAGE_URL = "https://plugins.jetbrains.com/plugin/manage"
TOKENS_URL = "https://plugins.jetbrains.com/author/me/tokens"


def gradle_executable(project):
    wrapper = project / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if wrapper.exists():
        if os.name != "nt":
            try:
                wrapper.chmod(0o755)
            except Exception:
                pass
        return [str(wrapper)]
    if run(["gradle", "--version"], project).returncode == 0:
        return ["gradle"]
    return None


def detect_plugin_generation(project):
    """返回 '2.x' / '1.x' / None。"""
    text = ""
    for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"):
        f = project / name
        if f.exists():
            text += f.read_text(encoding="utf-8-sig", errors="replace")
    if "org.jetbrains.intellij.platform" in text:
        return "2.x"
    if "org.jetbrains.intellij" in text:
        return "1.x"
    return None


def token_present(project):
    if any(os.environ.get(k) for k in TOKEN_ENVS):
        return True
    gp = project / "gradle.properties"
    if gp.exists() and re.search(
        r"(?im)^\s*intellij(platform)?(publishing)?token\s*=",
        gp.read_text(encoding="utf-8-sig", errors="replace"),
    ):
        return True
    return False


def precheck(project, rpt):
    pxml = find_plugin_xml(project)
    if not pxml:
        rpt.append((Mark.FAIL, "未找到 src/main/resources/META-INF/plugin.xml"))
        return False
    text = pxml.read_text(encoding="utf-8-sig", errors="replace")
    ok = True
    vm = re.search(r"<vendor([^>]*)>(.*?)</vendor>", text, re.S)
    if not vm:
        rpt.append((Mark.FAIL, "plugin.xml 缺少 <vendor>，先运行 sync_identity.py --apply"))
        ok = False
    elif not re.search(r'email\s*=\s*"[^"]+"', vm.group(1)):
        rpt.append((Mark.WARN, "vendor 缺少 email 属性"))
    if not re.search(r"<id>[\w.\-]+</id>", text):
        rpt.append((Mark.FAIL, "plugin.xml 缺少 <id>"))
        ok = False
    if not re.search(r"<change-notes", text):
        rpt.append((Mark.WARN, "plugin.xml 缺少 <change-notes>（市场页“最新变化”）"))
    version, src = current_version(project)
    if not version:
        rpt.append((Mark.WARN, "未检测到版本号，请确认 gradle.properties/plugin.xml 版本声明"))
    else:
        rpt.append((Mark.PASS, f"当前版本 {version}（来源 {src}）"))
    return ok


def run_gradle(project, exe, tasks, step_name):
    cmd = exe + tasks
    print(f"{Mark.INFO} 执行: {' '.join(cmd)}")
    p = run(cmd, project)
    out = (p.stdout or "") + (p.stderr or "")
    tail = "\n".join(out.splitlines()[-25:])
    if p.returncode != 0:
        print(f"{Mark.FAIL} {step_name}失败（退出码 {p.returncode}）:\n{tail}")
        return False
    print(f"{Mark.PASS} {step_name}完成")
    return True


def main():
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="JetBrains Marketplace 发布助手")
    ap.add_argument("--project", default=None)
    ap.add_argument("--build-only", action="store_true", help="构建并校验，不上传")
    ap.add_argument("--apply", action="store_true", help="正式上传（默认不上传）")
    ap.add_argument("--channel", default="stable", help="发布渠道 stable/beta/自定义")
    args = ap.parse_args()

    project = project_root(args.project)
    print(f"=== JetBrains 发布检查: {project} ===")

    rpt = []
    precheck_ok = precheck(project, rpt)
    for level, msg in rpt:
        print(f"{level} {msg}")

    exe = gradle_executable(project)
    gen = detect_plugin_generation(project)
    if not exe:
        print(f"{Mark.FAIL} 未找到 gradlew 包装器，且系统无 gradle；请先执行 gradle wrapper")
        return 1
    print(f"{Mark.PASS} Gradle: {exe[0]}    插件世代: {gen or '未识别（默认按 1.x）'}")

    has_token = token_present(project)
    if args.apply and not has_token:
        print(f"{Mark.FAIL} 未检测到发布 Token。请在 {TOKENS_URL} 生成后通过环境变量提供，例如：")
        print('  PowerShell: $env:ORG_GRADLE_PROJECT_INTELLIJ_PUBLISH_TOKEN="xxx"')
        print("  并确认 gradle.properties 已被 .gitignore 忽略（切勿入库）")
        return 1
    if not has_token:
        print(f"{Mark.WARN} 未检测到发布 Token，仅可构建；上传前请配置（{TOKENS_URL}）")

    # 构建 + 校验
    build_tasks = ["clean", "buildPlugin"]
    if gen != "2.x":
        build_tasks.append("verifyPlugin")
    else:
        build_tasks.append("verifyPlugin")  # 2.x 同样提供 verifyPlugin
    if not run_gradle(project, exe, build_tasks, "构建/校验插件"):
        return 1

    zips = glob.glob(str(project / "build" / "distributions" / "*.zip"))
    if not zips:
        print(f"{Mark.FAIL} 构建成功但未找到 build/distributions/*.zip")
        return 1
    print(f"{Mark.PASS} 插件包: {', '.join(zips)}")

    cfg = load_project_config(project)
    cfg["platforms"] = sorted(set(cfg.get("platforms", [])) | {"jetbrains"})
    save_project_config(project, cfg)

    if args.build_only or not args.apply:
        print(f"\n{Mark.INFO} 构建完成。正式发布命令预览：")
        if gen == "2.x" and args.channel != "stable":
            print(f"  {' '.join(exe)} publishPlugin --channel {args.channel}")
        elif args.channel != "stable":
            print(f"  {' '.join(exe)} publishPlugin -PreleaseChannel={args.channel}")
            print("  注意：1.x 需在 build.gradle 的 publishPlugin { channels = ... } 中接线该属性")
        else:
            print(f"  {' '.join(exe)} publishPlugin")
        print(f"\n也可手动上传 zip: {MANAGE_URL} -> 选择插件 -> Upload Plugin Update")
        if not args.apply:
            return 0

    # 正式上传
    tasks = ["publishPlugin"]
    if gen == "2.x" and args.channel != "stable":
        tasks += [f"--channel={args.channel}"]
    elif args.channel != "stable":
        tasks += [f"-PreleaseChannel={args.channel}"]
    if not run_gradle(project, exe, tasks, "上传 Marketplace"):
        return 1
    print(f"{Mark.PASS} 已提交到 JetBrains Marketplace（{args.channel} 渠道），"
          f"审核通过后自动上架，可在 {MANAGE_URL} 查看")
    return 0


if __name__ == "__main__":
    sys.exit(main())
