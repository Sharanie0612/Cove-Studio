# Declarative results / 声明式结果

This plugin returns ordinary Python dictionaries. Cove renders the cards, table,
pagination, empty state and theme. No React, HTML or custom host registration is needed.
It only processes the text supplied to it, with no file or network access.

插件只负责统计和校验输入。布局由 `manifest.json` 的 `ui.result` 声明：
`fields` 选择结果对象的顶层键，`table.key` 选择对象数组，`columns` 选择每行的键。
名称与单位为普通文本，不能注入 HTML。可选格式为 `text`、`number`、`json`。
表格每页 50 行，可翻页查看全部记录；没有声明 `ui.result` 的旧插件仍显示原始结果。

需要 Cove 0.11.0 和 `ui.result` capability。下载的开发包已包含完整 SDK 和运行脚本。
在本示例目录运行：

```powershell
python -S dev.py analyze "text=Hello Cove hello plugins"
python -S doctor.py
python -S package.py
```

在源码仓库中可运行：

```powershell
.venv\Scripts\python.exe scripts\check_plugin.py docs\examples\result-starter
.venv\Scripts\python.exe scripts\package_plugin.py docs\examples\result-starter
```

在 Cove 的插件页检查并导入生成的 `.cove-plugin`，从工作台打开“文本报告”。
要适配自己的工具，替换 `analyze` 的业务逻辑、字段和结果键；不修改 Cove 核心。
若增加写文件或设备控制行为，应重新声明 AI 工具的读写属性。
