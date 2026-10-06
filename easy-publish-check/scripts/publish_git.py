#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向 GitHub / GitLab / Gitee / Gitea 多平台统一发布：
配置同名 remote -> 打版本 tag -> 逐平台独立推送（单个平台失败不影响其它平台）
-> 输出各平台 Release 网页填写地址，并把配置记忆到项目内 .easy-publish.json。

用法（--remote 可重复，平台名取 github/gitlab/gitee/gitea）：
  python publish_git.py --setup-only --save \
      --remote github=git@github.com:you/repo.git \
      --remote gitee=git@gitee.com:you/repo.git
  python publish_git.py --remote github=git@github.com:you/repo.git \
      --remote gitee=https://gitee.com/you/repo.git --branch main
  python publish_git.py --tag v1.4.0 --message "Release v1.4.0"
  python publish_git.py --no-tag          # 只推分支不打 tag

前提：
  - 远端仓库需已在各平台网页创建（脚本不会代为创建仓库）；
  - 推送凭据走本机 Git 凭据管理器/SSH Key，脚本不接触、不保存任何密码令牌。
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_common import (  # noqa: E402
    GIT_PLATFORMS, Mark, _utf8_stdio, current_branch, current_version,
    git, load_project_config, project_root, remote_url, release_web_url,
    save_project_config, ssh_to_https, working_tree_dirty,
)


def parse_remote(item):
    m = re.match(r"^(github|gitlab|gitee|gitea)=(.+)$", item.strip())
    if not m:
        raise ValueError(f"--remote 格式应为 平台=地址，收到: {item}")
    platform, url = m.group(1), m.group(2).strip()
    if not re.match(r"^(git@[\w.\-]+:|https?://|file:///)", url):
        raise ValueError(f"远端地址仅支持 SSH(git@host:path)、HTTPS 或 file:// 本地镜像: {url}")
    return platform, url


def ensure_remote(project, platform, url, force):
    """返回 (状态, 说明)；状态: created/exists/updated/error。"""
    existing = remote_url(project, platform)
    if existing == url:
        return "exists", f"remote {platform} 已存在且地址一致"
    if existing:
        if not force:
            return "error", f"remote {platform} 已存在但地址不同: {existing}（确认覆盖请加 --force-url）"
        p = git(["remote", "set-url", platform, url], project)
        if p.returncode != 0:
            return "error", p.stderr.strip()
        return "updated", f"remote {platform} 地址已更新"
    p = git(["remote", "add", platform, url], project)
    if p.returncode != 0:
        return "error", p.stderr.strip()
    return "created", f"remote {platform} 已添加: {url}"


def main():
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="多平台 Git 发布")
    ap.add_argument("--project", default=None)
    ap.add_argument("--remote", action="append", default=[],
                    help="平台=地址，可重复，如 github=git@github.com:u/r.git")
    ap.add_argument("--branch", default=None, help="推送分支，默认当前分支")
    ap.add_argument("--tag", default=None, help="指定 tag，如 v1.4.0")
    ap.add_argument("--no-tag", action="store_true", help="不打 tag")
    ap.add_argument("--message", default=None, help="tag 附注信息")
    ap.add_argument("--setup-only", action="store_true", help="只配置 remote，不推送")
    ap.add_argument("--save", action="store_true",
                    help="把平台/地址记忆到 .easy-publish.json（setup-only 时需显式指定）")
    ap.add_argument("--force-url", action="store_true", help="remote 地址冲突时覆盖")
    ap.add_argument("--allow-dirty", action="store_true", help="工作区不干净也继续")
    ap.add_argument("--no-save", action="store_true", help="不写入 .easy-publish.json")
    args = ap.parse_args()

    project = project_root(args.project)
    if git(["rev-parse", "--is-inside-work-tree"], project).returncode != 0:
        print(f"{Mark.FAIL} 不是 Git 仓库: {project}")
        return 1

    try:
        remotes = dict(parse_remote(x) for x in args.remote)
    except ValueError as e:
        print(f"{Mark.FAIL} {e}")
        return 1

    # 未通过命令行给地址时，读取已记忆的项目配置
    cfg = load_project_config(project)
    if not remotes and cfg.get("remotes"):
        remotes = {k: v for k, v in cfg["remotes"].items() if k in GIT_PLATFORMS}
        print(f"{Mark.INFO} 沿用已记忆发布配置: {', '.join(remotes)}")
    if not remotes:
        print(f"{Mark.FAIL} 未提供任何 --remote 平台=地址，且无历史配置")
        return 1

    # 1) 配置 remote
    print("=== 配置远端 ===")
    ok_platforms = []
    for platform, url in remotes.items():
        status, msg = ensure_remote(project, platform, url, args.force_url)
        marker = {
            "created": Mark.PASS, "exists": Mark.PASS,
            "updated": Mark.PASS, "error": Mark.FAIL,
        }[status]
        print(f"{marker} {msg}")
        if status != "error":
            ok_platforms.append(platform)
    if not ok_platforms:
        return 1

    # 2) setup-only：按 --save 记忆后直接结束（不检查脏工作区、不推送）
    if args.setup_only:
        if args.save and not args.no_save:
            cfg.update({
                "platforms": sorted(set(cfg.get("platforms", [])) | set(ok_platforms)),
                "remotes": {**{k: v for k, v in (cfg.get("remotes") or {}).items()},
                            **{k: remotes[k] for k in ok_platforms}},
                "branch": args.branch or current_branch(project) or cfg.get("branch", "main"),
                "updated": datetime.now().isoformat(timespec="seconds"),
            })
            save_project_config(project, cfg)
            print(f"{Mark.PASS} 发布配置已记忆到 .easy-publish.json（已加入 .gitignore）")
        print(f"{Mark.INFO} setup-only 完成，未推送")
        return 0

    # 真正推送前先检查工作区（配置记忆可能改写 .gitignore，故检查置于保存之前）
    if working_tree_dirty(project) and not args.allow_dirty:
        print(f"{Mark.FAIL} 工作区存在未提交改动；提交后再发布，或确认无误加 --allow-dirty")
        print(git(["status", "--short"], project).stdout)
        return 1

    # 3) 正式发布：记忆配置
    if not args.no_save:
        cfg.update({
            "platforms": sorted(set(cfg.get("platforms", [])) | set(ok_platforms)),
            "remotes": {**{k: v for k, v in (cfg.get("remotes") or {}).items()},
                        **{k: remotes[k] for k in ok_platforms}},
            "branch": args.branch or current_branch(project) or cfg.get("branch", "main"),
            "updated": datetime.now().isoformat(timespec="seconds"),
        })
        save_project_config(project, cfg)
        print(f"{Mark.PASS} 发布配置已记忆到 .easy-publish.json（已加入 .gitignore）")

    # 3) 确定分支与 tag
    branch = args.branch or current_branch(project) or cfg.get("branch", "main")
    tag = None
    if not args.no_tag:
        tag = args.tag
        if not tag:
            version, _ = current_version(project)
            tag = f"v{version}" if version else None
        if tag:
            existing = git(["tag", "-l", tag], project).stdout.strip()
            if not existing:
                msg = args.message or f"Release {tag}"
                p = git(["tag", "-a", tag, "-m", msg], project)
                if p.returncode != 0:
                    print(f"{Mark.FAIL} tag 创建失败: {p.stderr.strip()}")
                    return 1
                print(f"{Mark.PASS} 已创建附注 tag {tag}")
            else:
                print(f"{Mark.INFO} tag {tag} 已存在，跳过创建")

    # 4) 逐平台推送（互不阻断）
    print("\n=== 逐平台推送 ===")
    results = {}
    for platform in ok_platforms:
        print(f"---> {platform}")
        p = git(["push", "-u", platform, branch], project)
        branch_ok = p.returncode == 0
        if not branch_ok:
            print((p.stderr or p.stdout or "").strip()[:800])
        tag_ok = True
        if tag:
            p2 = git(["push", platform, tag], project)
            tag_ok = p2.returncode == 0
            if not tag_ok:
                print((p2.stderr or p2.stdout or "").strip()[:800])
        results[platform] = branch_ok and tag_ok
        if results[platform]:
            print(f"{Mark.PASS} {platform} 推送成功（分支 {branch}"
                  + (f"，tag {tag}" if tag else "") + "）")

    # 5) Release 网页地址
    print("\n=== Release 发布页（粘贴更新说明/附件） ===")
    for platform in ok_platforms:
        url = remotes[platform]
        if tag and re.match(r"^(git@|https?://)", url):
            web = release_web_url(platform, ssh_to_https(url), tag)
            print(f"  {platform}: {web}")
        elif tag:
            print(f"  {platform}: 本地/镜像远端（{url}），无 Web Release 页")

    failed = [p for p, ok in results.items() if not ok]
    if failed:
        print(f"\n{Mark.FAIL} 以下平台推送失败: {', '.join(failed)}")
        print("  常见原因：国内网络波动（可重试）、远端仓库未创建、SSH Key/凭据未配置")
        return 1
    print(f"\n{Mark.PASS} 全部 {len(results)} 个平台发布完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
