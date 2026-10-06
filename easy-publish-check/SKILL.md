---
name: easy-publish-check
description: "AI 开发项目的统一发布技能：发布前审查与修正、统一发布人身份（Git 作者姓名邮箱、IDEA 插件 vendor 供应商名）、项目介绍 README 生成、语义化版本自动迭代与更新日志、向 GitHub/GitLab/Gitee/Gitea 多平台 Git 仓库以及 JetBrains Marketplace（IDEA 插件市场）发布。当用户说「项目调整完毕可以上线/发布/发版/release/publish」、「发布到 GitHub/Gitee/GitLab/Gitea」、「发布 IDEA/IntelliJ 插件到插件市场」、「发布前检查/审查」、「统一 git 作者信息、修正 IDEA 插件供应商 vendor 显示成项目名的问题」、「版本号怎么升、打 tag 发 Release」、「软件里加关于/联系作者模块、关于页面显示作者邮箱和反馈渠道」时使用。适用于 Gradle/Maven/Node/Python 等常见工程类型，支持一次选择多个国内外平台。"
---

# Easy Publish Check · AI 项目统一发布（Multi-platform Release）

## 概述

为大量 AI 辅助开发的项目提供一条统一、可重复的发布流水线，解决两类典型问题：

1. **身份不统一**：Git 提交作者姓名邮箱混乱；IDEA 插件市场页供应商（vendor）显示成
   项目代号（如 `aitools`）而非发布人真实姓名/邮箱；各清单 author 信息缺失。
2. **发布流程不统一**：README 缺失、版本号各文件不一致、CHANGELOG 没写、
   多平台（GitHub/GitLab/Gitee/Gitea/JetBrains）重复手工操作且容易遗漏。
3. **软件内缺少统一的「关于 / 联系作者」入口**：用户在软件里找不到作者、邮箱与
   反馈渠道；需要按项目技术栈生成关于模块并写入发布人联系方式。

脚本全部仅依赖 **Python 3.8+ 标准库 + Git**，无第三方依赖，跨 Windows/macOS/Linux。
下文 `<skill>` 表示本技能目录（即 SKILL.md 所在目录），命令示例按实际路径替换。

## 资源地图

| 文件 | 职责 |
|---|---|
| `scripts/profile.py` | 发布人全局档案（姓名邮箱一次录入，跨项目记忆于 `~/.easy-publish-check/profile.json`） |
| `scripts/preflight.py` | 发布前自动审查（身份、版本、文档、关于/联系入口、卫生、密钥扫描、插件 vendor） |
| `scripts/sync_identity.py` | 统一写入 Git 身份、plugin.xml vendor、package.json author、pom.xml developers |
| `scripts/bump_version.py` | 提交记录分析、语义化版本判定与同步、CHANGELOG 日期转换 |
| `scripts/publish_git.py` | 多平台 remote 配置、打附注 tag、逐平台独立推送、Release 页链接 |
| `scripts/publish_jetbrains.py` | Gradle 插件检测、构建校验、JetBrains Marketplace 上传或手动 zip 兜底 |
| `references/platforms.md` | 五大平台地址格式、认证、Gradle 两代插件配置、失败排查 |
| `references/checklist.md` | 完整审查清单（自动/人工分工）与放行规则 |
| `references/versioning.md` | 语义化版本、提交约定、tag 规则 |
| `references/about-module.md` | 「关于/联系作者」模块按技术栈（IDEA/Vue/React/Electron/CLI/Python/README）的生成模板 |
| `assets/` | README、CHANGELOG、profile 模板 |

## 工作流总览（9 个阶段，严格按序）

```
阶段0 身份 → 1 项目识别 & 平台多选 → 2 仓库地址确认 → 3 README
→ 4 关于/联系作者模块 → 5 版本 & 迭代内容 → 6 身份统一 & 发布前审查
→ 7 构建验证 → 8 确认后发布 → 9 Release 说明 & 验证
```

- 每完成一个阶段简要汇报，再进入下一阶段；FAIL 项未修复不得跳过。
- 提问要**批量**（每条消息最多 4 个问题），给出编号选项；用户已答的不再追问。
- 全程使用用户所用语言；命令在项目目录下执行，脚本路径用完整路径。
- **禁止**：force push、把 token 写进项目文件、未经确认创建远端仓库或上传市场、
  跳过审查直接推送。

## 阶段 0：发布人身份（全局只问一次）

```bash
python "<skill>/scripts/profile.py" get
```

- 退出码 3（无档案或缺字段）：一次性向用户收集并保存——
  **必填**：发布人姓名、邮箱；
  **可选**：个人主页、GitHub/GitLab/Gitee 用户名、自建 Gitea 地址、
  JetBrains 供应商名称（必须与市场 Vendor Profile 一致，默认用姓名）、
  默认协议（如 MIT）、默认分支（如 main）。

  ```bash
  python "<skill>/scripts/profile.py" set --name "姓名" --email "a@b.com" --vendor-url "https://..." --gitee-user "xxx" --jetbrains-vendor "姓名"
  ```

- 已存在：回显 `姓名 <邮箱>` 请用户确认；变更用 `profile.py set` 覆盖对应字段。
- 档案存于用户主目录，**与具体项目无关**，所有项目复用。

## 阶段 1：项目识别与平台多选

1. 定位项目根（脚本自动取 git 根目录），探测工程类型
   （gradle / intellij 插件 / maven / node / python）。
2. 用一道多选题让用户勾选发布平台（可多选，国内外不限）：
   ① GitHub ② GitLab（含自建）③ Gitee ④ Gitea（自建）⑤ JetBrains Marketplace。
3. 读 `.easy-publish.json`（项目内、自动 gitignore）复用既往配置；
   没有则进入阶段 2 收集。

## 阶段 2：每个平台的仓库地址

- 对每个**已选 Git 平台**逐一询问仓库地址（优先 SSH，如
  `git@gitee.com:name/repo.git`；自建站问主机名）。可一条消息列出多个平台请用户一次给齐。
- 明确告知：远端空仓库需用户先在平台网页创建好，脚本不代为建仓；
  如需代建（GitHub 可用 gh API），必须另行征得明确同意。
- 仅配置不推送，先把目标记忆下来：

  ```bash
  python "<skill>/scripts/publish_git.py" --setup-only --save --remote github=git@github.com:name/repo.git --remote gitee=git@gitee.com:name/repo.git
  ```

## 阶段 3：项目介绍 README（缺失则多轮问答生成）

先看项目是否已有合格 README（preflight 会判安装/使用/许可证章节）。
**缺失或明显不合格**时，参照 `assets/README.template.md`，分批向用户提问，一批 ≤4 个：

1. 一句话定位（是什么、给谁用、解决什么问题）；
2. 3–5 个核心功能点；运行环境/前置要求（JDK/Node/Python 版本等）；
3. 安装方式、快速开始的真实命令（结合项目代码核对，不能编造命令/参数）；
4. 配置项、FAQ、开源协议（默认取档案里的 license）。

据此生成 **README.md 写入项目根**；是 IDEA 插件还要同步准备：

- `plugin.xml` 的 `<description>`（HTML/CDATA，市场简介，≥40 字符）；
- 插件图标、市场截图、分类标签（提醒用户准备，脚本不生成图标）。

## 阶段 4：「关于 / 联系作者」模块（缺失则生成）

1. 先按 `references/about-module.md` 的探测规则扫描项目（preflight 会做同样检查）：
   IDEA 插件找 About Action/设置页，前端找 About 路由/页面/菜单，Electron 找
   About 面板，CLI 找 `--about`，无界面项目看 README 联系章节；向用户汇报结果。
2. 缺失时与用户确认（一批 ≤4 问）：是否生成、入口位置（按技术栈给默认推荐）、
   展示哪些联系方式（默认姓名、邮箱、主页、Issues、许可证；微信/QQ/手机仅在
   用户主动提供时加入并提示会随发行包公开）、产品显示名。
3. 按技术栈套用 `references/about-module.md` 模板生成并**完成入口注册**：
   - IDEA 插件：`AboutAction.kt/java` + plugin.xml 注册到 HelpMenu（硬性要求，
     preflight 对插件缺失该入口判 FAIL）；
   - Vue/React：About 页面 + 路由 + 菜单/页脚链接；Electron：About 面板/菜单；
   - Node/Python CLI：`--about` 输出；无界面项目：README「联系作者」章节。
4. 联系方式一律取自全局档案与已确认仓库地址，**禁止编造**；版本号运行时动态读取。
   生成结果在阶段 7 构建验证，阶段 6 审查时「关于/联系」检查项须转为 PASS。

## 阶段 5：本版本迭代内容与版本号迭代

1. 跑自动分析（不写文件）：

   ```bash
   python "<skill>/scripts/bump_version.py" --level auto --json
   ```

2. 向用户展示：当前版本、建议级别（major/minor/patch）及依据
   （feat/fix 数量、是否含 BREAKING CHANGE）、提交清单；请用户确认级别或指定版本号。
3. 与用户确认**本版本迭代内容**（优先用户口述，其次用提交分类摘要，
   写成面向用户的价值描述而非 commit 原文），先填入 `CHANGELOG.md` 的
   `[Unreleased]` 段落（没有 CHANGELOG 就用 `assets/CHANGELOG.template.md` 创建）。
4. 用户确认后执行迭代（自动把 Unreleased 转成 `[X.Y.Z] - 日期` 并同步所有清单）：

   ```bash
   # 自动判定
   python "<skill>/scripts/bump_version.py" --level minor
   # 或用户指定
   python "<skill>/scripts/bump_version.py" --set 1.5.0
   ```

5. IDEA 插件：把同样内容以 HTML 写入 `<change-notes>`（或 Gradle 接线的 changes.html）。

## 阶段 6：身份统一与发布前审查（核心修正环节）

1. **先预览**计划，展示给用户，确认后加 `--apply` 写入：

   ```bash
   python "<skill>/scripts/sync_identity.py"            # 预览
   python "<skill>/scripts/sync_identity.py" --apply    # 写入
   ```

   自动修正：Git 仓库级 `user.name/email`；plugin.xml `<vendor email/url>姓名</vendor>`
   （**vendor 必须是真实发布人，不能是产品名/项目代号**）；package.json author；
   pom.xml developers。
2. Gradle DSL 里的 vendor（build.gradle / build.gradle.kts 的
   `publishPlugin` / `intellijPlatform.pluginConfiguration`）形态多变，
   按 `references/platforms.md` 第 7 节模板**手工修改并向用户展示改动**。
3. 跑发布前审查：

   ```bash
   python "<skill>/scripts/preflight.py"
   ```

   按 `references/checklist.md` 的放行规则处理：FAIL 必须修复后重跑；
   WARN 汇总后一次性告知，由用户决定修复还是接受。重点核对：
   插件 vendor、关于/联系作者入口、版本一致性、密钥扫描、CHANGELOG 与 change-notes。

## 阶段 7：构建验证（发布前最后一道关口）

- IDEA 插件（同时完成 buildPlugin + verifyPlugin，产出 zip）：
  ```bash
  python "<skill>/scripts/publish_jetbrains.py" --build-only
  ```
- Node：`npm ci && npm run build && npm test`；
  Maven：`mvn clean package`；Python：`python -m build` 或项目既定方式。
- 构建/测试失败必须先修复，不得带故障发布。是否执行耗时构建先征得用户同意。

## 阶段 8：最终确认后发布

1. 把版本/文档/关于模块的改动提交（若阶段 5 未用 `--commit`）：
   `git add -A && git commit -m "chore(release): vX.Y.Z"`。
2. 展示**发布计划摘要**请用户最终确认：平台、各平台仓库地址、版本、tag（`vX.Y.Z`）、
   本版本要点；确认后执行。
3. Git 多平台推送（自动打附注 tag、逐平台独立推送、输出 Release 页链接）：

   ```bash
   python "<skill>/scripts/publish_git.py" --remote github=git@github.com:name/repo.git --remote gitee=git@gitee.com:name/repo.git
   ```

   已配置过的项目直接无参运行即可（读 `.easy-publish.json`）。
   单平台失败不影响其它平台，报告失败平台并可单独重跑
   （同命令或 `git push <remote> 分支 --follow-tags`）。
4. JetBrains 发布：token 只走环境变量（提醒用户在**当前终端**注入，
   页面 <https://plugins.jetbrains.com/author/me/tokens> 生成）；确认环境就绪后：

   ```bash
   python "<skill>/scripts/publish_jetbrains.py" --apply            # stable
   python "<skill>/scripts/publish_jetbrains.py" --apply --channel beta
   ```

   无法配置 token / CI 环境时，用 `--build-only` 产出的
   `build/distributions/*.zip` 到 <https://plugins.jetbrains.com/plugin/manage> 手动上传。

## 阶段 9：Release 说明与发布后验证

- publish_git 输出各平台 Release 新建页链接，把阶段 5 的迭代内容粘贴进去
  （Gitee 叫「发行版」）；附件按平台规则上传，**发布内容各平台保持一致**。
- 验证：`git ls-remote --tags <remote>` 确认 tag 已同步；
  JetBrains 在管理页确认「待审核」状态（首次 1–3 工作日）。
- 向用户交付：各平台仓库/Release 链接、Marketplace 链接、版本与变更摘要。

## 命令速查

| 目的 | 命令 |
|---|---|
| 查看/初始化发布人档案 | `python <skill>/scripts/profile.py get`（或 `init`） |
| 配置平台不推送 | `python publish_git.py --setup-only --save --remote gitee=git@gitee.com:u/r.git` |
| 版本分析（不写） | `python bump_version.py --level auto --json` |
| 版本同步 + CHANGELOG | `python bump_version.py --level minor` |
| 统一身份（预览/写入） | `python sync_identity.py`（加 `--apply` 写入） |
| 发布前审查 | `python preflight.py` |
| 构建校验 IDEA 插件 | `python publish_jetbrains.py --build-only` |
| 多平台推送 | `python publish_git.py` |
| 上传插件市场 | `python publish_jetbrains.py --apply [--channel beta]` |

## 安全与边界

- 凭据：只使用本机 SSH Key / Git 凭据管理器 / 环境变量；**绝不**打印、保存、
  写死 token/password；含 token 的配置文件必须 gitignore。
- Git：禁止 `push --force` 与移动已推送的 tag；non-fast-forward 先
  `git pull --rebase` 与用户确认。
- 真实性：README 示例、命令、版本、仓库地址必须来自项目实际或用户陈述，不得编造；
  不能确保正确的命令先说明再执行。
- 确认点：身份覆盖、版本级别、最终发布计划、市场上传、远端创建——先给计划后执行。
- 国内网络：Gitee/GitHub 推送可能间歇失败，按平台独立重试，并向用户说明。
