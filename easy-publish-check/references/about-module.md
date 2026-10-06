# 「关于 / 联系作者」模块生成参考

在工作流阶段 4 使用：先探测软件内是否已有「关于 / 联系作者」入口，缺失则按技术栈
生成，并把**全局档案中的发布人信息**写入。preflight 的「关于/联系」检查项与本文件
的探测规则一致。

## 目录

1. [交互提问清单](#1-交互提问清单)
2. [内容与隐私规则](#2-内容与隐私规则)
3. [IDEA/IntelliJ 插件（Kotlin / Java）](#3-ideaintellij-插件kotlin--java)
4. [Vue 前端](#4-vue-前端)
5. [React 前端](#5-react-前端)
6. [Electron 桌面应用](#6-electron-桌面应用)
7. [Node.js 命令行](#7-nodejs-命令行)
8. [Python（CLI / PyQt / Tkinter）](#8-pythoncli--pyqt--tkinter)
9. [通用兜底：README / ABOUT 文档](#9-通用兜底readme--about-文档)
10. [生成后的验证](#10-生成后的验证)

---

## 1. 交互提问清单

先扫描再提问，一批最多 4 个问题：

1. 汇报扫描结果（是否已存在 About 页面/Action/菜单/`--about`），问用户是否需要生成；
2. 入口位置（按栈给默认推荐，见下文各节标题）；
3. 展示哪些联系方式——默认：姓名、邮箱、个人主页、仓库 Issues、许可证；
   微信/QQ/手机号等**仅当用户主动提供时加入**，并提示会随发行包公开；
4. 产品显示名与一句话介绍（缺省时从 README / plugin.xml `<name>` 取）。

## 2. 内容与隐私规则

- 所有信息必须来自全局档案（`profile.py get`）与用户已确认的仓库地址，**禁止编造**。
- 版本号必须**运行时动态读取**（插件描述符 / package.json / `--version`），不要硬编码。
- 推荐字段：产品名、版本、一句话介绍、作者姓名、邮箱（`mailto:`）、主页、
  Issues/反馈地址、许可证；国内项目可中文为主、中英双语。
- 生成后必须完成入口注册（plugin.xml `<action>`、前端路由与菜单、CLI 参数），
  否则视为未完成；阶段 7 构建验证时一并编译。

## 3. IDEA/IntelliJ 插件（Kotlin / Java）

**推荐入口**：Help 菜单「关于 XXX」Action，弹窗展示；这是 preflight 对插件的硬性检查项。

`src/main/kotlin/com/example/xxx/AboutAction.kt`（包名与 plugin.xml 的 id 对齐）：

```kotlin
package com.example.xxx

import com.intellij.ide.plugins.PluginManagerCore
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.extensions.PluginId
import com.intellij.openapi.ui.Messages

class AboutAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val version = PluginManagerCore
            .getPlugin(PluginId.getId("com.example.xxx"))?.version ?: ""
        val info = """
            <html>
            <h3>MD Assistant&nbsp;$version</h3>
            <p>Markdown 文档助手：扫描、分类并与项目中的 Markdown 对话。</p>
            <hr/>
            作者：曹宇皓<br/>
            邮箱：<a href="mailto:cyuhao@example.com">cyuhao@example.com</a><br/>
            主页：<a href="https://gitee.com/cyuhao/md-assistant">gitee.com/cyuhao/md-assistant</a><br/>
            问题反馈：<a href="https://gitee.com/cyuhao/md-assistant/issues">提交 Issue</a><br/>
            许可证：MIT
            </html>
        """.trimIndent()
        Messages.showInfoMessage(info, "关于 MD Assistant")
    }
}
```

Java 版：

```java
package com.example.xxx;

import com.intellij.ide.plugins.IdeaPluginDescriptor;
import com.intellij.ide.plugins.PluginManagerCore;
import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.extensions.PluginId;
import com.intellij.openapi.ui.Messages;
import org.jetbrains.annotations.NotNull;

public class AboutAction extends AnAction {
    @Override
    public void actionPerformed(@NotNull AnActionEvent e) {
        IdeaPluginDescriptor plugin =
                PluginManagerCore.getPlugin(PluginId.getId("com.example.xxx"));
        String version = plugin != null ? plugin.getVersion() : "";
        String info = "<html><h3>MD Assistant&nbsp;" + version + "</h3>"
                + "作者：曹宇皓<br/>邮箱：<a href='mailto:cyuhao@example.com'>cyuhao@example.com</a><br/>"
                + "主页：<a href='https://gitee.com/cyuhao/md-assistant'>gitee.com/cyuhao/md-assistant</a><br/>"
                + "问题反馈：<a href='https://gitee.com/cyuhao/md-assistant/issues'>Issues</a><br/>"
                + "许可证：MIT</html>";
        Messages.showInfoMessage(info, "关于 MD Assistant");
    }
}
```

在 `src/main/resources/META-INF/plugin.xml` 注册到 Help 菜单：

```xml
<actions>
    <action id="MdAssistant.About"
            class="com.example.xxx.AboutAction"
            text="关于 MD Assistant"
            description="查看作者介绍与联系方式">
        <add-to-group group-id="HelpMenu" anchor="last"/>
    </action>
</actions>
```

> 备选入口：设置页（`Configurable` / `applicationConfigurable`）底部「作者与反馈」卡片，
> 适合还要放配置项的插件；不要与平台自带的 Help → About（IDE 关于）混淆命名。

## 4. Vue 前端

**推荐入口**：`/about` 路由 + 页脚/侧边栏菜单「关于 / 联系作者」。

`src/views/About.vue`（Vue 3 `<script setup>`）：

```vue
<template>
  <div class="about-page">
    <h2>关于 {{ product }}</h2>
    <p class="desc">一句话介绍本系统的用途与目标用户。</p>
    <ul class="contact">
      <li>作者：{{ author }}</li>
      <li>邮箱：<a :href="`mailto:${email}`">{{ email }}</a></li>
      <li>主页：<a :href="homepage" target="_blank" rel="noopener">{{ homepage }}</a></li>
      <li>问题反馈：<a :href="`${repo}/issues`" target="_blank" rel="noopener">提交 Issue</a></li>
      <li>版本：v{{ version }}　许可证：{{ license }}</li>
    </ul>
  </div>
</template>

<script setup>
import pkg from '../../package.json'
const product = 'XXX 系统'
const author = '曹宇皓'
const email = 'cyuhao@example.com'
const homepage = 'https://gitee.com/cyuhao/xxx'
const repo = 'https://gitee.com/cyuhao/xxx'
const license = pkg.license || 'MIT'
const version = pkg.version
</script>
```

路由与菜单：

```js
{ path: '/about', name: 'About',
  component: () => import('@/views/About.vue'),
  meta: { title: '关于 / 联系作者' } }
```

```html
<router-link to="/about">关于 / 联系作者</router-link>
```

Vue 2 / Element-UI 后台同理：新建 `views/About.vue`，在路由表与 Layout 菜单注册。

## 5. React 前端

**推荐入口**：`/about` 路由 + 页脚链接。

```tsx
import pkg from '../../package.json'

export default function About() {
  return (
    <div style={{ padding: 24 }}>
      <h2>关于 XXX 系统</h2>
      <p>一句话介绍。</p>
      <ul>
        <li>作者：曹宇皓</li>
        <li>邮箱：<a href="mailto:cyuhao@example.com">cyuhao@example.com</a></li>
        <li>主页：<a href="https://gitee.com/cyuhao/xxx" target="_blank" rel="noreferrer">gitee.com/cyuhao/xxx</a></li>
        <li>问题反馈：<a href="https://gitee.com/cyuhao/xxx/issues" target="_blank" rel="noreferrer">Issues</a></li>
        <li>版本：v{pkg.version}　许可证：{pkg.license || 'MIT'}</li>
      </ul>
    </div>
  )
}
```

```tsx
// react-router v6
{ path: '/about', element: <About /> }
```

## 6. Electron 桌面应用

**推荐入口**：应用菜单「关于 XXX」。跨平台最简方案 `setAboutPanelOptions`：

```js
const { app, Menu, shell } = require('electron')

app.setAboutPanelOptions({
  applicationName: 'XXX',
  applicationVersion: app.getVersion(),
  copyright: '作者：曹宇皓 <cyuhao@example.com>',
  credits: '主页 https://gitee.com/cyuhao/xxx\n问题反馈 https://gitee.com/cyuhao/xxx/issues\n许可证 MIT',
})

// 自定义菜单项（Windows/Linux 推荐，可放更多联系方式）
const template = [
  // ...其它菜单
  {
    label: '帮助',
    submenu: [
      { label: '关于 XXX', click: () => shell.openExternal('mailto:cyuhao@example.com?subject=关于 XXX') },
      { label: '问题反馈', click: () => shell.openExternal('https://gitee.com/cyuhao/xxx/issues') },
    ],
  },
]
Menu.setApplicationMenu(Menu.buildFromTemplate(template))
```

需要富文本展示（图标/可点击链接）时新建独立 About 窗口（`new BrowserWindow` 加载
`about.html`），内容字段同上。

## 7. Node.js 命令行

**推荐入口**：`--about`（与 `--version` 区分，输出完整联系信息）。

```js
const pkg = require('../package.json')

function printAbout() {
  console.log(`
${pkg.name}  v${pkg.version}
${pkg.description || ''}

作者：曹宇皓 <cyuhao@example.com>
主页：https://gitee.com/cyuhao/xxx
问题反馈：https://gitee.com/cyuhao/xxx/issues
许可证：${pkg.license || 'MIT'}
`)
}

if (process.argv.includes('--about')) {
  printAbout()
  process.exit(0)
}
```

同时在 README 输出同名段落，并在 `package.json` 保留 `author`、`license`、
`repository`、`bugs.url` 字段（sync_identity 已维护 author）。

## 8. Python（CLI / PyQt / Tkinter）

CLI（argparse）：

```python
ABOUT = """\
xxx  v{version}
一句话介绍。

作者：曹宇皓 <cyuhao@example.com>
主页：https://gitee.com/cyuhao/xxx
问题反馈：https://gitee.com/cyuhao/xxx/issues
许可证：MIT
"""

parser.add_argument("--about", action="store_true", help="关于与联系方式")
if args.about:
    print(ABOUT.format(version=__version__))
    raise SystemExit
```

PyQt5/6 弹窗（挂到「帮助 → 关于」菜单）：

```python
from PyQt6.QtWidgets import QMessageBox

def show_about(parent, version):
    QMessageBox.about(parent, "关于 XXX",
        f"<h3>XXX v{version}</h3>"
        "<p>作者：曹宇皓</p>"
        "<p>邮箱：<a href='mailto:cyuhao@example.com'>cyuhao@example.com</a><br>"
        "主页：<a href='https://gitee.com/cyuhao/xxx'>gitee.com/cyuhao/xxx</a><br>"
        "问题反馈：<a href='https://gitee.com/cyuhao/xxx/issues'>Issues</a><br>"
        "许可证：MIT</p>")
```

Tkinter 用 `tkinter.messagebox.showinfo("关于 XXX", 文本块)` 同理。

## 9. 通用兜底：README / ABOUT 文档

无界面项目（库、服务端、脚本）至少在 README.md 末尾增加章节：

```markdown
## 联系作者 / Contact

- 作者：曹宇皓
- 邮箱：cyuhao@example.com
- 主页：https://gitee.com/cyuhao/xxx
- 问题反馈：[Issues](https://gitee.com/cyuhao/xxx/issues)
- 许可证：[MIT](LICENSE)
```

也可在软件安装目录/帮助菜单放置 `ABOUT.md`（内容同上），由程序「关于」菜单项打开。

## 10. 生成后的验证

- IDEA 插件：`publish_jetbrains.py --build-only` 编译通过，沙箱 IDE 的 Help 菜单可见入口；
- 前端：`npm run build` 通过，路由可访问、菜单链接可见；
- Electron/桌面：启动应用确认关于菜单与弹窗；
- CLI：实际执行 `--about` 检查输出；
- 重新运行 `preflight.py`，「关于/联系」检查项转为 PASS。
