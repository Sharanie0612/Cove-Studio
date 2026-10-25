import { t } from '../core/i18n.ts';
export const getTestPrompt = () =>
  t(
    '请调用 Cove 的 cove_tools，列出当前已授权的工具并告诉我实际结果。如果列表为空，也请如实说明；不要执行写操作。',
  );

export interface HarnessGuide {
  open: string;
  check: string;
  command?: string;
}
export const getHarnessGuides = (): Record<string, HarnessGuide> => ({
  codex: {
    open: t(
      'Cove 已保存并启用本机 Codex 配置。正常启动 Codex 后，在本地任务中直接要求使用 Cove 工具。首次接入前已打开的 Codex，需重新加载 MCP 或重新打开一次。',
    ),
    check: t(
      '桌面版设置 → MCP 服务器检查 cove；CLI 用 /mcp。若项目配置或组织策略覆盖用户配置，需在对应环境允许 Cove。旧版直接工具入口升级到固定入口后，已有会话需重新加载一次。',
    ),
    command: '/mcp',
  },
  'claude-code': {
    open: t('在本机终端中退出旧的 Claude Code 会话，重新运行 claude，再进入你的项目。'),
    check: t('输入 /mcp，找到 cove，查看连接状态和工具。若显示需要信任或启用，按客户端提示完成。'),
    command: '/mcp',
  },
  cursor: {
    open: t(
      '重启 Cursor，在侧边栏打开 Customize → MCPs，找到 cove。旧版入口位于 Cursor Settings 的 MCP 或 Tools & Integrations。',
    ),
    check: t(
      '确认 cove 已启用、工具列表可见，再打开 Agent 对话；在对话顶部的工具列表中保持 Cove 工具开启。',
    ),
  },
  'deepseek-harness': {
    open: t('停止旧的 dsh 服务，在同一台 Windows 电脑重新运行 dsh web，然后打开它显示的网页地址。'),
    check: t(
      '新建任务，让 Agent 调用 Cove 工具。此连接加载全局 cordis.patch.yml；若使用自定义 DSH_HOME，需要与 Cove 启动时一致。',
    ),
    command: 'dsh web',
  },
  zcode: {
    open: t('重新打开 ZCode，进入 Settings → MCP Servers，在已配置的服务中找到 cove。'),
    check: t(
      '启用 cove，确认工具加载，再回到 ZCode Agent 新建对话。如果没有出现，检查是否使用了另一套用户目录。',
    ),
  },
  workbuddy: {
    open: t('重新打开 WorkBuddy，进入左侧「插件」→「MCP 服务器」，在列表中找到 cove。'),
    check: t(
      '在服务详情中启用或重新加载 cove，确认工具可用，再新建对话。部分新版入口名为「连接器」，可从该入口管理自定义 MCP。',
    ),
  },
  trae: {
    open: t(
      '在 TRAE 的本地运行环境中打开「设置 → MCP → 添加 → 手动添加」。复制下方配置，粘贴并确认；也可合并到「原始配置（JSON）」中。',
    ),
    check: t('在 MCP 列表中启用 cove，并在当前智能体中添加这个 MCP 服务，再开启本地任务对话。'),
  },
});
