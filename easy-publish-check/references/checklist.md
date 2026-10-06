# 发布前审查清单（Pre-release Review）

严重级别：**FAIL**（必须修复才能发布）/ **WARN**（需用户确认）/ **PASS**。
标注「自动」的项目由 `scripts/preflight.py` 检查；标注「人工」的由 AI 助手
逐项核对或与用户确认。审查不通过不得进入发布步骤。

## 1. 发布人身份统一（本技能核心）

| 级别 | 检查项 | 方式 |
|---|---|---|
| FAIL | 已存在全局档案 `~/.easy-publish-check/profile.json`，含姓名、邮箱 | 自动 |
| FAIL | Git 生效身份（local 优先于 global）= 档案姓名/邮箱 | 自动 |
| FAIL | IDEA 插件 `<vendor>` 存在，且为真实姓名/公司名，**不是产品名、项目代号、aitools 之类占位名**，带 email | 自动 |
| FAIL | package.json `author` 与档案一致（存在时） | 自动 |
| WARN | pom.xml `<developers>` 含发布人姓名邮箱 | 自动 |
| WARN | build.gradle(.kts) 中 pluginConfiguration.vendor（2.x/1.x）与档案一致 | 人工 |
| WARN | 最近 20 条提交未混入其它作者身份 | 自动 |
| WARN | 版权头/License 声明年份与作者（如项目有版权头惯例） | 人工 |

修复统一走：`python scripts/sync_identity.py`（先预览，确认后加 `--apply`）。

## 2. 版本号与迭代内容

| 级别 | 检查项 | 方式 |
|---|---|---|
| FAIL | 所有清单版本号一致（gradle.properties / build.gradle / package.json / pom.xml / plugin.xml / pyproject.toml / setup.py） | 自动 |
| FAIL | 版本号符合语义化 `MAJOR.MINOR.PATCH` | 自动 |
| WARN | CHANGELOG.md 存在且包含本版本条目（Added/Changed/Fixed） | 自动 |
| WARN | plugin.xml `<change-notes>` 与 CHANGELOG 本版本内容一致（IDEA 市场“最新变化”） | 人工 |
| PASS | 版本级别判定合理：破坏性→major、新功能→minor、修复→patch | 人工确认 |
| WARN | 平台市场中该版本未发布过（同号不可重复上传 Marketplace） | 人工 |

## 3. 工程质量

| 级别 | 检查项 | 方式 |
|---|---|---|
| FAIL | 工作区干净，所有改动已提交 | 自动 |
| WARN | 本地无未推送提交 | 自动 |
| FAIL/WARN | 构建通过：Gradle `clean buildPlugin`、Maven `package`、npm `run build`、Python 打包检查 | 人工执行（publish_jetbrains --build-only 覆盖插件） |
| WARN | 测试通过（test/testPlugin），lint 无新增错误 | 人工 |
| WARN | IDEA 插件 `verifyPlugin` 通过、since-build 兼容范围正确、插件可在沙箱 IDE 启动 | 自动+人工 |

## 4. 文档与元数据

| 级别 | 检查项 | 方式 |
|---|---|---|
| FAIL | README.md 存在，包含安装、使用、许可证章节 | 自动 |
| WARN | README 内容与当前版本功能一致（截图/示例命令可运行、无过期参数） | 人工 |
| WARN | LICENSE 文件存在且年份/署名正确 | 自动+人工 |
| WARN | IDEA 插件 description ≥40 字符，说明做什么、给谁用、核心特性 | 人工 |
| WARN | 插件图标 40×40（建议配深色版），市场截图/分类/标签已准备 | 人工 |
| WARN | package.json 的 description/repository/keywords/license 完整 | 人工 |
| FAIL | IDEA 插件软件内存在「关于/联系作者」入口（Help 菜单 Action 或设置页），含发布人姓名、邮箱、主页/反馈渠道 | 自动 |
| WARN | Vue/React/Electron 应用存在关于页/关于菜单，且写入发布人联系方式 | 自动 |
| WARN | CLI 工具支持 `--about`，或 README 含「联系作者」章节；无界面项目至少有该章节 | 自动 |
| WARN | 关于模块中的版本号为运行时读取而非硬编码；未公开微信/手机等隐私信息（除非用户明确要求） | 人工 |

## 5. 安全与卫生

| 级别 | 检查项 | 方式 |
|---|---|---|
| FAIL | 无私钥、AWS/GitHub/GitLab Token 等硬编码密钥 | 自动 |
| WARN | 无疑似硬编码密码/API Key（人工确认） | 自动 |
| FAIL | `.env` 等敏感文件未被 Git 跟踪 | 自动 |
| WARN | node_modules/target/build/dist/.idea/*.iml 等产物未被跟踪 | 自动 |
| WARN | 无内网地址、内部域名、个人路径、调试用 localhost 配置残留在发行物中 | 人工 |
| WARN | `.gitignore` 覆盖构建产物、IDE 文件、本地配置（含 `.easy-publish.json`、含 token 的 gradle.properties） | 自动+人工 |
| WARN | 依赖无已知高危漏洞（npm audit / mvn versions / osv-scanner，按栈选用） | 人工 |

## 6. 发布目标与发布后验证

| 级别 | 检查项 | 方式 |
|---|---|---|
| WARN | 选定平台的远端仓库均已在网页创建、当前账号有推送权限 | 人工 |
| WARN | JetBrains Token 已注入当前终端环境变量（不入库） | 自动 |
| PASS | 每个平台分支与 tag 推送成功（publish_git 逐平台回报） | 自动 |
| PASS | tag 为附注 tag（annotated），命名 `vX.Y.Z` | 自动 |
| WARN | 各平台 Release 说明已填写（脚本输出直达链接），附件已上传 | 人工 |
| WARN | Marketplace 提交后状态为待审核；审核通过后页面信息正确 | 人工 |

## 审查结论规则

- 存在任一 **FAIL**：停止发布，输出问题与修复命令，修复后重新跑 preflight。
- 仅 **WARN**：汇总后一次性向用户说明，用户明确接受或选择修复后继续。
- 全部 PASS/WARN 已确认：展示「发布计划摘要」（平台、仓库地址、版本、tag、
  本版本迭代内容），用户最终确认后才执行推送/上传。
