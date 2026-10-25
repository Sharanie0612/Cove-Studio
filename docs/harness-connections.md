# MCP 连接

先从左侧 **智能体工具** 选择共享插件并保存，再从 **工作台 → MCP 连接** 点击客户端的 **一键接入**。Cove 保存配置、开启自动维护并执行本机协议自检，Codex 配置明确设为启用。首次接入前已打开的客户端需重新加载一次，客户端要求的信任确认仍在客户端完成。之后 Cove 启动即提供服务，重启 Cove 或增减授权无需反复配置。MCP 可停用、不可删除；停用后停止 AI 访问，保留共享选择和 工具会话。

| 客户端 | 自动配置位置 | 格式 |
| --- | --- | --- |
| Codex | CODEX_HOME/config.toml 或 ~/.codex/config.toml | mcp_servers.cove TOML |
| Claude Code | ~/.claude.json | mcpServers JSON |
| Cursor | ~/.cursor/mcp.json | mcpServers JSON |
| DeepSeek Harness | DSH_HOME/cordis.patch.yml 或 ~/.dsh/cordis.patch.yml | patch-list insert YAML |
| ZCode | ~/.zcode/cli/config.json | mcp.servers JSON |
| WorkBuddy | ~/.workbuddy/mcp.json | mcpServers JSON |
| TRAE | 设置 → MCP → 手动添加 | JSON 导入，由客户端管理存储 |

接入后留在 Cove 页面，可直接复制试用消息；问号打开详情，包含自动维护开关和按需展开的排查方法。实际路径和配置折叠在「高级配置与安装命令」中；Codex 与 Claude Code 也提供 PowerShell 安装命令。已有 cove 项时更新该项，不重复追加；保留其他服务和设置。JSONC 的原始注释保存在备份，合并后输出标准 JSON。

撤销备份按原字节保存，可能包含其他服务的密钥；备份未加密，使用本机账户文件权限保护。启动和配置保存后清理超过 30 天或每客户端最近 5 份之外的已识别备份，成功撤销后删除对应记录。清理失败时保留文件并在客户端详情提示，下一次维护重试；不会因为清理失败把已成功保存的连接报告成失败。外部修改依旧阻止自动撤销。MCP 令牌同样使用私密文件权限；这不能隔离同一账户下的恶意进程。所有已连接的 MCP 客户端共享当前插件授权，只读工具也可能读取敏感输出。

## 固定入口与动态授权

默认只向客户端注册 3 个稳定工具，避免客户端缓存空列表或在每次会话加载全部插件参数 schema：

| 入口 | 用法 |
| --- | --- |
| cove_tools | 可传 query 搜索工具摘要；传 tool 精确名称读取参数 schema。每次读取当前授权。 |
| cove_read | 传 tool 和 arguments 调用只读工具；拒绝写工具。 |
| cove_write | 传 tool 和 arguments 发起操作；保留 Cove 的单次参数确认。 |

AI 应先发现工具并读取 schema，再按读写分类调用。新插件授权后，原有 Codex 本地任务可再次发现，不需要更新会话工具列表。结果保留波形数组和截图，不截断科学数据。旧版直接工具适配器仍兼容，切换到新入口时需让旧客户端重新加载一次。插件自己的独立 MCP 导出保持原有工具格式。

“已配置”只说明客户端文件中存在 Cove 条目。“已连接”表示该客户端启动的适配器进程仍在线。卡片状态不推断模型是否可用。

一键接入会执行真实 STDIO 初始化、固定入口发现和 cove_tools 调用。卡片“检查连接”可重复自检。自检不调用模型，也不会冒充目标客户端已经连接。随后让目标客户端“调用 Cove 的 cove_tools 列出当前授权目录”，验证实际插件结果。

## 客户端里怎么操作

保持 Cove 打开；以下步骤适用于同机 Windows 本地客户端。云端任务、WSL 和远程环境不直接复用此本地命令。

| 客户端 | 在客户端完成的操作 |
| --- | --- |
| Codex | Cove 已保存 enabled=true；首次已有会话重新加载 MCP 或重新打开一次。之后正常启动 Codex，在本地任务直接调用。/mcp 或设置 → MCP 服务器仅供排查。项目配置和组织策略可能覆盖用户配置。 |
| Claude Code | 重启 claude，会话中输入 /mcp，确认 cove 已连接并显示工具。 |
| Cursor | 重启，打开 Customize → MCPs；旧版为 Cursor Settings 的 MCP / Tools & Integrations。启用 cove，在 Agent 对话工具列表确认工具开启。 |
| DeepSeek Harness | 停止旧服务，重新运行 dsh web，打开网页新建任务。使用与 Cove 相同的 DSH_HOME。 |
| ZCode | 重启 → Settings → MCP Servers → 找到并启用 cove → 新建 Agent 对话。 |
| WorkBuddy | 重启 → 插件 → MCP 服务器 → 启用或重新加载 cove → 新建对话。新版也可从连接器管理自定义 MCP。 |
| TRAE | 设置 → MCP → 本地 → 添加 → 手动添加 → 粘贴 Cove 配置；启用服务，并添加到当前智能体，再打开本地任务。 |

在目标客户端对话框发送：

> 请调用 Cove 的 cove_tools，列出当前已授权的工具并告诉我实际结果。如果列表为空，也请如实说明；不要执行写操作。

首次可以返回「未连接」，这依然是一次有效的读取。成功的依据是对话中出现实际工具结果，并且 Cove 的「最近的工具调用」中出现对应记录。仅看到普通文字回答不足以证明调用成功。

如果没有 cove，在 Cove 点击修复连接；发现结果为空时，在 Cove 选择并保存共享插件；连接报错时展开排查方法。AI 对话仍需客户端自己的模型登录或配置。

## 权限与会话

只提供勾选插件的 ai.tools。写工具绑定不可变参数快照，在 Cove 中单次确认后执行；拒绝、超时或撤销授权后不执行。调用记录在页面下方按需展开。

各客户端使用同一个桌面会话。切换页面保留桥接，退出 Cove 后停止。配置不包含桥接令牌或模型 Key；不要分享数据目录。生成的命令面向同机 Windows 本地环境。

## 配置保护

合并前保存原文件字节；保存与撤销检查并发修改，不覆盖客户端随后产生的新设置。配置损坏、DSH 手动重复服务和不完整托管块会拒绝自动修改，可打开详情手动处理。

自动维护仅处理用户点击一键接入后登记的客户端，在 Cove 启动时更新旧版运行路径。比较 Cove 条目的签名，而非整个文件，其他服务和个人设置可自由更改。若 Cove 条目被手动修改、停用、删除或切换配置目录，暂停自动更新并提示修复；不会静默重新启用。详情可关闭自动维护；成功撤销会同时移除维护登记。自动维护不能强制第三方客户端刷新当前任务，也不能绕过组织策略或远程环境限制。

## 官方参考

- [Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Claude Code](https://code.claude.com/docs/en/mcp)
- [Cursor](https://prod.cursor.com/help/customization/mcp)
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)
- [ZCode](https://zcode.z.ai/en/docs/mcp-services)
- [WorkBuddy](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide)
- [TRAE](https://docs.trae.cn/ide_add-mcp-servers)

配置结构已按官方文档实现；实际协议与 DSH 工具链有自动化联调。七款客户端各自的登录后模型任务需要相应客户端环境。

