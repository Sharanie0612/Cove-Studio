# Cove Studio 外观

设置中将显示模式（浅色、深色、跟随系统）与配色方案分开管理。

| 方案 | 设计 |
| --- | --- |
| Cove（默认） | 接近白色的页面、纯白卡片和浅灰侧栏，仅用低饱和雾霾蓝强调操作与选中态；深色使用中性深灰与雾蓝强调。 |
| VS Code | 中性黑白底色，蓝色交互强调。 |
| GitHub | 中性底色，蓝色链接与绿色主要操作。 |
| 暖纸 | 暖白或茶褐背景，低亮度棕色强调。 |

VS Code、GitHub 方案是适配 Cove 布局的独立配色，不是对第三方主题文件的完整导入。原始参考：

- Microsoft VS Code（MIT）：[Light Modern](https://github.com/microsoft/vscode/blob/main/extensions/theme-defaults/themes/light_modern.json)、[Dark Modern](https://github.com/microsoft/vscode/blob/main/extensions/theme-defaults/themes/dark_modern.json)。
- GitHub / Primer（MIT）：[GitHub theme mappings](https://github.com/primer/github-vscode-theme/blob/main/src/theme.js)、[color definitions](https://github.com/primer/github-vscode-theme/blob/main/src/colors.js)。

0.12.9 起，Cove 浅色方案使用 #FAFBFC 页面、#FFFFFF 卡片、#F3F5F7 窗口框架，以及 #536F94 雾蓝强调色。0.12.0 起，新安装默认使用 Cove；已保存的方案、自定义颜色和显示模式继续保留。设置中可随时选择 Cove。0.12.4 起，标题栏与侧栏共用框架底色，页面通过圆角内沿衔接，卡片以轻边线与阴影区分层次。导航折叠按钮固定在标题栏左侧。所有界面共用圆角令牌和 `motion.css` 的动效时长，并支持减少动态效果。

## 字体与排版

0.12.9 的通用插件图标采用黑白灰中性色阶，保留 Hello 风格的圆润曲线。终端以深浅面区分外壳与提示符，芯片分出引脚和内核，文件夹使用前后叠层，MCP 使用清晰的双链接轮廓；通过细微投影、底沿和边缘高光表现轻微层次。所有图标颜色均为中性灰，独立于界面强调色；深色界面使用浅色图形和深灰底板。卡片中的图标为 52px，列表中的图标为 40px，插件管理卡片中的图标为 44px。插件卡片统一使用内边距和固定图标列，使图标与名称、版本和详情入口对齐。侧栏采用同一笔画粗细的导航图标，收放按钮使用方向明确的竖线与箭头。应用标志与第三方客户端标志保持各自身份。

采用接近 macOS 应用的排版节奏：26px 页面标题、15px 工具标题、14px 正文、13px 说明、12px 辅助文字，常规与半粗字重形成层级。保留白底与蓝色操作，正文使用中性深色，降低卡片边框的存在感。

Apple 平台优先使用系统字体；Windows 随应用离线包含 Inter 与 Noto Sans SC 的 OFL 字体子集，内部族名为 Cove Sans Latin / Cove Sans CJK。安装器仅在自身进程中加载同一套静态字体，不向操作系统安装字体。未包含的生僻字回退到系统字体；终端与代码继续使用等宽字体。

原始作者、许可、固定来源提交及校验和在 `assets/fonts/`。`scripts/build_fonts.py` 可重新生成字体；日常产品构建直接使用仓库中的字体文件，不联网获取字体。不分发 Apple 的 San Francisco 或苹方文件。

## 自定义

可以基于任一预设创建自定义方案。浅色和深色分别保存页面、卡片、侧栏、强调色四个颜色；其余文字、边框、按钮、选中态和终端颜色由同一套规则生成。按钮文字根据实际底色选择深浅色。正文与三种底色对比不足时，编辑器会提示调整底色。

只接收 #RRGGBB 格式的颜色。无效值不会注入 CSS；损坏或来自旧版本的存储会回退到有效默认值。重置自定义只影响用户主动选择的自定义方案，不删除连接、插件或终端记录。

## 实现

- `src/core/appearance.ts`：预设、输入归一化、对比度与完整颜色令牌。
- `src/core/useAppearance.ts`：旧模式迁移、跟随系统、本机持久化与主题应用。
- `src/components/AppearancePicker.tsx`：方案预览与自定义编辑器。
- `src/components/SettingsDialog.tsx`：独立滚动区域与固定完成按钮。
- `src/framework/surfaces/TerminalSurface.tsx`：更改现有 xterm 实例的主题，不重建实例或连接。

启动时在 React 挂载前应用颜色，避免先显示默认蓝色再切换。存储键为 `toolbench:appearance-v1`；旧 `toolbench:theme` 仅在首次迁移时读取。浏览器不允许持久化时仍可即时预览。
