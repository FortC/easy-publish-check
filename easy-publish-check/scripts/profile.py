#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布人全局身份档案：姓名、邮箱等信息一次录入，所有项目复用。

用法：
  python profile.py get                      查看档案（JSON）；未配置时退出码 3
  python profile.py set --name "张三" --email "zs@example.com" [选项]
  python profile.py init                     交互式逐项录入
  python profile.py path                     打印档案文件路径

可选字段：
  --vendor-url          个人主页/公司主页
  --github-user         GitHub 用户名
  --gitlab-user         GitLab 用户名
  --gitee-user          Gitee 用户名
  --gitea-url           自建 Gitea 根地址，如 https://gitea.example.com
  --jetbrains-vendor    JetBrains Marketplace 供应商名称（必须是真实姓名/公司名，不能是产品名）
  --license             默认开源协议，如 MIT
  --branch              默认分支，如 main
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_common import (  # noqa: E402
    PROFILE_PATH, Mark, _utf8_stdio, load_profile, save_json, save_profile,
)

FIELDS = {
    "name": ("发布人姓名", True),
    "email": ("发布人邮箱", True),
    "vendor_url": ("个人/公司主页（可留空）", False),
    "github_user": ("GitHub 用户名（可留空）", False),
    "gitlab_user": ("GitLab 用户名（可留空）", False),
    "gitee_user": ("Gitee 用户名（可留空）", False),
    "gitea_url": ("自建 Gitea 地址（可留空）", False),
    "jetbrains_vendor": ("JetBrains 供应商名称（真实姓名/公司名，可留空）", False),
    "license": ("默认开源协议（可留空，如 MIT）", False),
    "branch": ("默认分支（可留空，如 main）", False),
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ask(prompt, default=""):
    tip = f" [{default}]" if default else ""
    val = input(f"{prompt}{tip}: ").strip()
    return val or default


def cmd_get(_args):
    profile = load_profile()
    if not profile:
        print(f"{Mark.WARN} 尚未配置发布人档案，路径: {PROFILE_PATH}")
        print(f"{Mark.INFO} 请先运行: python profile.py init")
        return 3
    import json
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    missing = [k for k in ("name", "email") if not profile.get(k)]
    if missing:
        print(f"{Mark.WARN} 缺少必填字段: {', '.join(missing)}")
        return 3
    print(f"{Mark.PASS} 发布人: {profile.get('name')} <{profile.get('email')}>")
    return 0


def cmd_set(args):
    profile = load_profile() or {}
    mapping = {
        "name": args.name, "email": args.email,
        "vendor_url": args.vendor_url, "github_user": args.github_user,
        "gitlab_user": args.gitlab_user, "gitee_user": args.gitee_user,
        "gitea_url": args.gitea_url, "jetbrains_vendor": args.jetbrains_vendor,
        "license": args.license, "branch": args.branch,
    }
    changed = False
    for key, val in mapping.items():
        if val is not None and val != "":
            profile[key] = val
            changed = True
    if not changed:
        print(f"{Mark.WARN} 未提供任何字段")
        return 1
    if profile.get("email") and not EMAIL_RE.match(profile["email"]):
        print(f"{Mark.FAIL} 邮箱格式不正确: {profile['email']}")
        return 1
    if not profile.get("name") or not profile.get("email"):
        print(f"{Mark.FAIL} name 与 email 为必填项")
        return 1
    save_profile(profile)
    print(f"{Mark.PASS} 已保存全局档案 -> {PROFILE_PATH}")
    print(f"{Mark.PASS} 发布人: {profile['name']} <{profile['email']}>")
    return 0


def cmd_init(_args):
    existing = load_profile() or {}
    profile = {}
    print("录入发布人身份（仅需一次，全局所有项目复用，直接回车保留已有值）\n")
    for key, (label, required) in FIELDS.items():
        default = existing.get(key, "")
        while True:
            val = _ask(label, default)
            if key == "email" and val and not EMAIL_RE.match(val):
                print("  邮箱格式不正确，请重填")
                continue
            if required and not val:
                print("  该项必填")
                continue
            profile[key] = val
            break
    save_profile(profile)
    print(f"\n{Mark.PASS} 档案已保存 -> {PROFILE_PATH}")
    return 0


def cmd_path(_args):
    print(PROFILE_PATH)
    return 0


def main():
    _utf8_stdio()
    parser = argparse.ArgumentParser(description="发布人全局身份档案")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("get", help="查看档案")
    p_set = sub.add_parser("set", help="设置字段")
    p_set.add_argument("--name")
    p_set.add_argument("--email")
    p_set.add_argument("--vendor-url", dest="vendor_url")
    p_set.add_argument("--github-user", dest="github_user")
    p_set.add_argument("--gitlab-user", dest="gitlab_user")
    p_set.add_argument("--gitee-user", dest="gitee_user")
    p_set.add_argument("--gitea-url", dest="gitea_url")
    p_set.add_argument("--jetbrains-vendor", dest="jetbrains_vendor")
    p_set.add_argument("--license")
    p_set.add_argument("--branch")
    sub.add_parser("init", help="交互式录入")
    sub.add_parser("path", help="打印档案路径")

    args = parser.parse_args()
    return {
        "get": cmd_get, "set": cmd_set, "init": cmd_init, "path": cmd_path,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
