# Easy Publish Check

> **AI 项目统一发布技能（Agent Skill）**：一次配置发布人身份，之后每个项目都能走同一条「审查 → 修正 → 发版 → 多平台发布」流水线。
>
> Unified release pipeline for AI-assisted projects: pre-release review & fixes, publisher identity unification (Git author / IDEA plugin vendor), README & About-module generation, semantic versioning with changelog, and one-shot publishing to GitHub / GitLab / Gitee / Gitea / JetBrains Marketplace.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)]()
[![Dependencies](https://img.shields.io/badge/dependencies-none-9cf.svg)]()

## 解决什么问题

大量 AI 辅助开发的项目在「最后一步发布」上反复踩同样的坑：

| 痛点 | 本技能的处理 |
|---|---|
| Git 提交作者姓名邮箱混乱、各项目不一致 | 全局发布人档案（`~/.easy-publish-check/profile.json`），一次录入跨项目复用，`sync_identity.py` 统一写入 Git / plugin.xml / package.json / pom.xml |
| IDEA 插件市场页供应商（vendor）显示成项目代号（如 `aitools`）而非真实姓名 | preflight 硬性检查 vendor 必须为真实发布人，并自动/引导修正 plugin.xml 与 Gradle 配置 |
| README 缺失或不合格 | 按模板多轮问答生成，含安装、使用、许可证章节 |
| 版本号各文件不一致、CHANGELOG 没写、tag 忘打 | `bump_version.py` 基于 Conventional Commits 自动判定 major/minor/patch，同步所有清单并转换 Unreleased |
| 多平台（GitHub/Gitee/GitLab/Gitea）重复手工操作、易遗漏 | `publish_git.py` 多远端配置记忆、自动打附注 tag、逐平台独立推送（单平台失败不影响其它） |
| JetBrains Marketplace 上传流程繁琐 | `publish_jetbrains.py` 构建校验 + token 走环境变量上传，附手动 zip 兜底 |
| 软件里找不到作者与反馈渠道 | 按技术栈生成「关于/联系作者」模块（IDEA Action / Vue / React / Electron / CLI / Python / README） |

## 仓库结构

```
easy-publish-check/
├── SKILL.md                  # 技能入口：触发条件、9 阶段工作流、命令速查
├── scripts/                  # 全部仅依赖 Python 3.8+ 标准库 + Git，无第三方依赖
│   ├── profile.py            # 发布人全局档案（一次录入，跨项目复用）
│   ├── preflight.py          # 发布前自动审查（身份/版本/文档/密钥扫描/vendor）
│   ├── sync_identity.py      # 统一写入 Git 身份与各清单 author/vendor
│   ├── bump_version.py       # 语义化版本判定与同步、CHANGELOG 日期转换
│   ├── publish_git.py        # 多平台 remote 配置、打 tag、逐平台独立推送
│   ├── publish_jetbrains.py  # Gradle 插件构建校验与 Marketplace 上传
│   └── release_common.py     # 共享工具库
├── references/               # 按需阅读的参考文档
│   ├── platforms.md          # 五大平台地址格式、认证、Gradle 两代插件配置、失败排查
│   ├── checklist.md          # 完整审查清单（FAIL/WARN/PASS 与放行规则）
│   ├── versioning.md         # 语义化版本、提交约定、tag 规则
│   └── about-module.md       # 「关于/联系作者」模块各技术栈生成模板
└── assets/                   # README / CHANGELOG / profile 模板
```

## 环境要求

- Python 3.8+（仅标准库，无需 pip install 任何东西）
- Git（SSH Key 或凭据管理器推送）
- 可选：Gradle（发布 IDEA 插件时）

## 安装

本技能兼容各类支持 Agent Skills 的运行时（ZCode、Claude Code、Codex、Cursor 等）。

```bash
git clone https://github.com/FortC/easy-publish-check.git

# ZCode
cp -r easy-publish-check/easy-publish-check ~/.zcode/skills/easy-publish-check

# Claude Code
cp -r easy-publish-check/easy-publish-check ~/.claude/skills/easy-publish-check

# Cursor（项目级）
cp -r easy-publish-check/easy-publish-check <你的项目>/.cursor/skills/easy-publish-check
```

装好后对 AI 说一句「发布这个项目」即可触发。

## 快速开始

在任意项目目录下对 AI 说：

- 「项目调整完毕，可以发布了」 / 「发布前帮我检查一下」
- 「发布到 GitHub 和 Gitee」 / 「推送到自建 Gitea」
- 「把 IDEA 插件发布到插件市场」 / 「插件市场供应商怎么显示成项目名了，帮我修」
- 「版本号该升 minor 还是 patch？打个 tag 发 Release」
- 「给软件加个关于页面，显示作者邮箱和反馈渠道」

首次使用会引导录入发布人档案（姓名、邮箱、各平台用户名、默认协议等），之后所有项目自动复用，不再重复询问。

## 工作流（9 个阶段，严格按序）

```
阶段0 身份 → 1 项目识别 & 平台多选 → 2 仓库地址确认 → 3 README
→ 4 关于/联系作者模块 → 5 版本 & 迭代内容 → 6 身份统一 & 发布前审查
→ 7 构建验证 → 8 确认后发布 → 9 Release 说明 & 验证
```

核心原则：

- **FAIL 项未修复不得发布**；WARN 汇总后由用户决定修复还是接受。
- 所有关键动作（身份覆盖、版本级别、最终发布计划、市场上传）**先给计划、用户确认后执行**。
- 单平台推送失败不影响其它平台，可单独重跑。

## 命令速查

脚本可脱离 AI 单独使用（`<skill>` 替换为技能目录路径）：

| 目的 | 命令 |
|---|---|
| 查看/初始化发布人档案 | `python <skill>/scripts/profile.py get`（或 `init`） |
| 配置多平台不推送 | `python <skill>/scripts/publish_git.py --setup-only --save --remote gitee=git@gitee.com:u/r.git` |
| 版本分析（不写文件） | `python <skill>/scripts/bump_version.py --level auto --json` |
| 版本同步 + CHANGELOG | `python <skill>/scripts/bump_version.py --level minor` |
| 统一身份（预览/写入） | `python <skill>/scripts/sync_identity.py`（加 `--apply` 写入） |
| 发布前审查 | `python <skill>/scripts/preflight.py` |
| 构建校验 IDEA 插件 | `python <skill>/scripts/publish_jetbrains.py --build-only` |
| 多平台推送 | `python <skill>/scripts/publish_git.py` |
| 上传插件市场 | `python <skill>/scripts/publish_jetbrains.py --apply [--channel beta]` |

## 支持范围

- **Git 托管平台**：GitHub、GitLab（含自建）、Gitee 码云、Gitea（自建），可一次多选、国内外混合。
- **JetBrains Marketplace**：IntelliJ 平台插件（Gradle `org.jetbrains.intellij` 1.x 与 `intellij-platform` 2.x 均支持），stable/beta 渠道。
- **工程类型**：Gradle / IntelliJ 插件 / Maven / Node（npm）/ Python。

## 安全与边界

- 凭据只走本机 SSH Key / Git 凭据管理器 / 环境变量；**绝不**打印、保存、写死 token/password。
- 禁止 `push --force` 与移动已推送的 tag；non-fast-forward 先 `git pull --rebase` 并与用户确认。
- 不代用户创建远端仓库、不上传市场，除非用户明确确认。
- README 示例、命令、版本、仓库地址必须来自项目实际或用户陈述，不得编造。
- 含密钥的本地配置（`.easy-publish.json`、含 token 的 `gradle.properties`）自动 gitignore。

## 许可证

[Apache License 2.0](LICENSE)
