# 版本号规则与自动迭代

## 1. 语义化版本（Semantic Versioning 2.0）

格式：`MAJOR.MINOR.PATCH`，如 `1.4.2`。

| 级别 | 何时递增 | 举例 |
|---|---|---|
| MAJOR（主版本） | 不兼容的破坏性变更：删除/改名公开 API、配置格式不兼容、最低 IDE 版本大跨越 | `1.4.2 → 2.0.0` |
| MINOR（次版本） | 向后兼容的新功能、新命令、新配置项 | `1.4.2 → 1.5.0` |
| PATCH（补丁） | 向后兼容的缺陷修复、文案/性能优化、文档修正 | `1.4.2 → 1.4.3` |

- 正式版前可用预发布标记：`0.3.0-beta.1`、`1.0.0-rc.1`（需用 `--set` 指定）。
- `0.x.y` 阶段 API 不保证稳定；首个对外版本建议直接 `1.0.0`。
- **同版本号一旦发布到 JetBrains Marketplace 即不可重复上传**，必须递增。

## 2. 自动级别判定（Conventional Commits）

`bump_version.py --level auto` 分析「上个 tag..HEAD」的提交标题：

| 提交特征 | 级别 |
|---|---|
| 含 `BREAKING CHANGE`，或 `feat!: ...` / `fix(scope)!: ...` | major |
| `feat:` / `feat(scope):` | minor |
| `fix:`、`perf:`、`refactor:`、`docs:`、`chore:`、`test:`、`ci:`、`build:` 及其它 | patch |
| 没有任何提交 / 无法解析 | patch（并提示与用户确认） |

脚本只做**建议**，必须把判定结果与依据（feat/fix 数量、破坏性变更）展示给用户确认；
用户可以用 `--level` 或 `--set X.Y.Z` 覆盖。

## 3. 版本号同步位置

脚本把新版本写入所有「当前已含版本号」的清单，保持单一事实来源：

- `gradle.properties`（`pluginVersion` / `version`，IntelliJ 插件推荐放这里）
- `build.gradle` / `build.gradle.kts`（`version = '...'`）
- `package.json`（`version`）
- `pom.xml`（跳过 `<parent>` 后的项目自身 `<version>`）
- `META-INF/plugin.xml`（`<version>`；多数 Gradle 项目由构建注入，缺省时不注入）
- `pyproject.toml`（`[project] version`）、`setup.py`

不会向原本没有版本声明的文件凭空注入版本，避免破坏构建约定。

## 4. CHANGELOG 约定

遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)：

```markdown
## [Unreleased]
### Added / Changed / Fixed / Deprecated / Removed / Security

## [1.5.0] - 2026-10-06
### Added
- 新增 ...
### Fixed
- 修复 ...
```

bump 时自动把 `[Unreleased]` 转成 `[新版本] - 当天日期`，并补新的 Unreleased 占位。
**本版本迭代内容**的来源优先级：

1. 用户直接给出的要点；
2. 自上个 tag 以来的提交记录分类摘要（脚本输出 feat/fix 清单）；
3. 与用户多轮问答补充（面向用户的价值描述，而非只罗列 commit）。

IDEA 插件还需把同样内容转成 HTML 片段放入 `<change-notes><![CDATA[ ... ]]>`
（或 Gradle 接线的 changes.html），市场页「最新变化」读这里，不读 CHANGELOG.md。

## 5. Git tag 约定

- 统一打附注 tag：`v1.5.0`（带 `-m "Release v1.5.0"`），不要用轻量 tag。
- 发布顺序：版本号与 CHANGELOG 提交 → 打 tag → 逐平台推送分支与 tag。
- tag 已存在但指向错误提交时：本地未推送可 `git tag -d` 重打；
  **已推送到任何平台的 tag 禁止删除/移动**，改为递增新版本重新发布。
