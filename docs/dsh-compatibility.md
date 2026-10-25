# Cove 与 DeepSeek Harness

MCP 是兼容边界。用户在 Cove 的 MCP 连接页保存 DeepSeek Harness 的客户端配置，按指南重载目标客户端，再分别验证适配器在线和工具调用成功。

通用 SDK 可为独立工程生成只读 MCP 服务和客户端配置。需要正在运行的 Cove 会话或经确认的写操作时，使用 Cove 桌面的 MCP 入口，授权与审批仍由 Cove 管理。高级配置默认折叠。

此核心仓库不随附业务工具，不要求安装 DeepSeek Harness。客户端与模型账号由用户自行选择。相关步骤见 [连接指南](harness-connections.md)和 [SDK](plugin-sdk.md)。
