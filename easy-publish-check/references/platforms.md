# 多平台发布参考（GitHub / GitLab / Gitee / Gitea / JetBrains）

本文件在用户选定发布平台后按需阅读。脚本命令中的 `<skill>` 指本技能目录。

## 目录

1. [通用约定与凭据](#1-通用约定与凭据)
2. [GitHub](#2-github)
3. [GitLab（含自建）](#3-gitlab含自建)
4. [Gitee 码云](#4-gitee-码云)
5. [Gitea（自建）](#5-gitea自建)
6. [多远端策略](#6-多远端策略)
7. [JetBrains Marketplace（IDEA 插件库）](#7-jetbrains-marketplaceidea-插件库)
8. [常见失败排查](#8-常见失败排查)

---

## 1. 通用约定与凭据

- 远端仓库必须**先在平台网页创建好**（空仓库即可），脚本不代为建仓。
- 推送凭据只走本机机制：**SSH Key**（推荐）或 Git Credential Manager（HTTPS）。
  技能脚本不接收、不保存、不打印任何密码/令牌；令牌一律通过环境变量或被
  `.gitignore` 忽略的 `gradle.properties` 提供。
- 国内网络环境下 Gitee/GitHub 推送可能间歇超时，`publish_git.py` 对各平台
  **独立 try、互不阻断**，失败平台可随后单独重跑同一条命令。
- 统一用**平台名作为 remote 名**（github/gitlab/gitee/gitea），便于按平台重推。

### 仓库地址格式

| 平台 | SSH | HTTPS |
|---|---|---|
| GitHub | `git@github.com:用户名/仓库.git` | `https://github.com/用户名/仓库.git` |
| GitLab | `git@gitlab.com:用户名/仓库.git` | `https://gitlab.com/用户名/仓库.git` |
| Gitee | `git@gitee.com:用户名/仓库.git` | `https://gitee.com/用户名/仓库.git` |
| Gitea | `git@gitea.公司.com:用户名/仓库.git` | `https://gitea.公司.com/用户名/仓库.git` |

## 2. GitHub

- 全球站，Release 页：`https://github.com/<u>/<r>/releases/new?tag=vX.Y.Z`。
- SSH Key：Settings → SSH and GPG Keys；首次连接需确认主机指纹（yes）。
- 如需 API 建仓/发 Release：安装 `gh`（GitHub CLI）并 `gh auth login`；
  但默认流程不依赖它，网页创建空仓库 + 脚本推送即可。
- 建议在仓库 Settings 中补：Topics、About、官网链接、License 识别。

## 3. GitLab（含自建）

- SaaS：gitlab.com；自建示例：`gitlab.公司.com`。
- 自建站地址形如 `--remote gitlab=git@gitlab.公司.com:group/repo.git`，
  注意 SSH 端口非 22 时使用 `~/.ssh/config` 配置 Host 别名，不要把端口写进 remote。
- Release 页：`https://<host>/<u>/<r>/-/releases/new?tag_name=vX.Y.Z`。
- 自建站若是 HTTP 自签证书，HTTPS 推送需配置 `http.sslCAInfo` 或改用 SSH。

## 4. Gitee 码云

- 国内速度快；**必须先完成实名认证**，且仓库需先在网页手动创建。
- Release（发行版）页：`https://gitee.com/<u>/<r>/releases/new?tag_name=vX.Y.Z`。
- Gitee 的 Release 附件与说明在「发行版」标签页填写，与 tag 分开管理。
- 同一账号多机推送如遇 `not permitted`，检查 SSH 公钥是否绑定到 Gitee 账号。
- Gitee 对单仓库附件大小/仓库容量有免费额度限制，大文件走 Release 附件前先确认。

## 5. Gitea（自建）

- 地址完全由部署决定，发布前确认根地址（如 `https://gitea.example.com`）。
- Release 页：`https://<host>/<u>/<r>/releases/new?tag_name=vX.Y.Z`。
- 自建服务可能只在内网可达，发布前确认网络/VPN 已连通。

## 6. 多远端策略

推荐：**每个平台一个同名 remote**（脚本默认方式）。

```bash
git remote add github git@github.com:u/r.git
git remote add gitee  git@gitee.com:u/r.git
git push github main --follow-tags
git push gitee  main --follow-tags
```

备选：给 origin 追加多个 URL，一次 `git push` 全部推送（无法单独重推失败平台，
仅在网络稳定时使用）：

```bash
git remote set-url --add origin git@gitee.com:u/r.git
git remote -v
```

## 7. JetBrains Marketplace（IDEA 插件库）

### 7.1 供应商身份（重点，解决“vendor 显示成项目名”的问题）

- 注册并登录 <https://plugins.jetbrains.com>，在 Vendor Profile 中登记
  **真实个人姓名或公司名称**作为供应商名；插件市场展示的「供应商」取自
  `plugin.xml` 的 `<vendor>`，**严禁填产品名、项目代号（如 aitools）或占位名**。
- `<name>` 是插件产品名，`<vendor>` 是发布人，二者必须不同。
- `sync_identity.py --apply` 会把全局档案写入：

  ```xml
  <vendor email="you@example.com" url="https://...">你的真实姓名</vendor>
  ```

- 首次上传某插件的账号即成为该插件的所有者；插件 id 一旦发布不可更改。

### 7.2 plugin.xml 关键要素

路径：`src/main/resources/META-INF/plugin.xml`

```xml
<idea-plugin>
    <id>com.yourname.md-assistant</id>          <!-- 全局唯一，反向域名风格 -->
    <name>MD Assistant</name>                    <!-- 产品名 -->
    <vendor email="you@example.com" url="...">你的姓名</vendor>
    <description><![CDATA[
        市场页简介，支持 HTML，建议 40–3000 字符，写清做什么、给谁用、核心特性。
    ]]></description>
    <change-notes><![CDATA[
        <ul><li>本版本新增/修复内容</li></ul>
    ]]></change-notes>
    <idea-version since-build="232"/>
</idea-plugin>
```

- 图标：`src/main/resources/META-INF/pluginIcon.svg`（40×40）与
  `pluginIcon.svg` + `pluginIcon_dark.svg`（深色模式，可选）；市场列表还会用大图标。
- 兼容范围 `since-build`（如 232 = 2023.2）；不写 until-build 以兼容未来版本。

### 7.3 Gradle 配置：区分两代插件

**1.x（org.jetbrains.intellij，旧）** — `build.gradle`：

```groovy
plugins { id 'org.jetbrains.intellij' version '1.17.4' }
intellij { version = '2023.2' }
patchPluginXml {
    changeNotes = file('changes.html').text
    sinceBuild = '232'
}
publishPlugin {
    token = providers.gradleProperty("intellijPublishToken").getOrElse("")
    channels = [providers.gradleProperty("releaseChannel").getOrElse("stable")]
}
```

**2.x（org.jetbrains.intellij.platform，新）** — `build.gradle.kts`：

```kotlin
plugins { id("org.jetbrains.intellij.platform") version "2.1.0" }
intellijPlatform {
    pluginConfiguration {
        ideaVersion { sinceBuild = "232" }
        vendor {
            name = "你的姓名"
            email = "you@example.com"
            url = "https://..."
        }
        changeNotes = file("changes.html").readText()
    }
    publishing {
        token = providers.gradleProperty("intellijPlatformPublishingToken").getOrElse("")
    }
}
```

> Gradle DSL 形态多变，`sync_identity.py` 只可靠改写 plugin.xml / package.json /
> pom.xml；build.gradle(.kts) 中的 vendor 由 AI 助手按上面的模板手工修改并复核。

### 7.4 Token 与上传

- 生成 Token：<https://plugins.jetbrains.com/author/me/tokens>
  （权限选 Plugin Upload），复制后只存于环境变量：

  ```powershell
  # Windows PowerShell（当前会话）
  $env:ORG_GRADLE_PROJECT_INTELLIJ_PUBLISH_TOKEN = "pat-xxxx"
  ```
  ```bash
  # macOS / Linux
  export ORG_GRADLE_PROJECT_INTELLIJ_PUBLISH_TOKEN=pat-xxxx
  ```

- 命令：
  - 构建校验：`python <skill>/scripts/publish_jetbrains.py --build-only`
  - 正式发布：`python <skill>/scripts/publish_jetbrains.py --apply`
  - beta 渠道：`--apply --channel beta`（2.x 支持 `--channel`；1.x 需在
    publishPlugin 块接线 `releaseChannel` 属性）
- 兜底手动上传：构建产物 `build/distributions/*.zip`，到
  <https://plugins.jetbrains.com/plugin/manage> 选择插件 → Upload Plugin Update。
- 首次发布需人工审核（通常 1–3 个工作日），后续更新审核更快；beta 渠道不进正式列表。

## 8. 常见失败排查

| 现象 | 原因与处理 |
|---|---|
| `Permission denied (publickey)` | 本机公钥未绑定到对应平台账号，或没用对应 Host；`ssh -T git@github.com` / `git@gitee.com` 自测 |
| Gitee 推送超时 | 国内网络波动，单独重跑 `git push gitee <分支> --follow-tags`；确认仓库已建、已实名 |
| `remote ... already exists` 且地址变了 | publish_git 加 `--force-url`，或先 `git remote set-url` |
| `rejected (non-fast-forward)` | 远端有网页端改动，先 `git pull --rebase <remote> <分支>` 再推；**禁止 force push** |
| Marketplace 报 vendor 不合规 | vendor 必须是真实姓名/公司名，不能与插件同名；改 plugin.xml 后重新构建 |
| Marketplace 401/invalid token | Token 失效或环境变量未注入当前终端；重新生成并确认 `$env:`/`export` 在同一会话 |
| 上传提示版本已存在 | 同版本号不能重复上传；用 bump_version 递增后再发 |
