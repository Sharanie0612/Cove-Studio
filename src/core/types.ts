import type { ResultLayout } from '../framework/contracts';

export type Values = Record<string, string | number>;
export interface Field {
  id: string;
  label: string;
  type: 'text' | 'password' | 'number' | 'select';
  placeholder?: string;
  required?: boolean;
  secret?: boolean;
  advanced?: boolean;
  default?: string | number;
  min?: number;
  max?: number;
  span?: number;
  options?: { value: string; label: string }[];
  showWhen?: { field: string; equals?: string; notEquals?: string };
}
export interface Manifest {
  sdkVersion: number;
  id: string;
  name: string;
  subtitle?: string;
  description: string;
  version: string;
  author: string;
  category: string;
  icon: string;
  color: string;
  permissions: string[];
  commands: string[];
  localization?: {
    defaultLocale: 'zh-CN' | 'en-US';
    messages: Partial<Record<'zh-CN' | 'en-US', Record<string, string>>>;
  };
  ai?: { tools: { name: string; readOnly: boolean }[] };
  compatibility?: {
    minHostVersion?: string;
    maxHostVersion?: string;
    capabilities?: string[];
  };
  compatibilityStatus?: { supported: boolean; reasons: string[] };
  enabled?: boolean;
  builtin?: boolean;
  customRuntime?: boolean;
  runtime?: {
    activity?: WorkActivity;
    running: boolean;
    connected: boolean;
    memoryBytes: number;
    pid?: number | null;
    message?: string;
  };
  ui: {
    surface: 'terminal' | 'form' | 'mcp' | 'web';
    result?: ResultLayout;
    fields: Field[];
    connection?: { connect: string; disconnect: string };
    web?: {
      entry: string;
      tools: {
        name: string;
        command: string;
        description: string;
        readOnly: boolean;
        parameters: Record<string, unknown>;
      }[];
    };
    job?: { snapshot: string; cancel: string };
    profiles?: {
      list: string;
      scan: string;
      save: string;
      remove: string;
      restore?: string;
    };
    terminal?: { write: string; resize: string; dataEvent: string };
    actions: { command: string; label: string; variant?: string }[];
    empty?: { title: string; description: string };
    status?: { idle: string; connected: string };
    confirmations?: {
      code: string;
      title: string;
      description: string;
      confirmLabel: string;
      details: { key: string; label: string }[];
      payload: Record<string, { fromDetail: string }>;
    }[];
  };
}
export interface ToolEvent {
  pluginId: string;
  event: string;
  time: number;
  data: {
    connected?: boolean;
    message?: string;
    text?: string;
    size?: number;
    [key: string]: unknown;
  };
}
export interface Catalog {
  capabilities?: string[];
  tools: Manifest[];
  available?: Manifest[];
  issues: { folder: string; error: string }[];
  hostVersion: string;
  sdkVersion: number;
  dataPath?: string;
  pluginsPath?: string;
  packaged?: boolean;
  windowState?: { maximized: boolean };
}
export interface Reply {
  ok: boolean;
  result?: unknown;
  error?: string;
  code?: string;
  details?: Record<string, string>;
}
export interface HostApi {
  plugin_view_open(id: string): Promise<Reply>;
  plugin_view_close(ticket: string): Promise<Reply>;
  plugin_view_call(ticket: string, name: string, args: Record<string, unknown>): Promise<Reply>;
  set_locale(locale: string): Promise<Reply>;
  catalog(): Promise<Catalog>;
  invoke(id: string, command: string, payload: Record<string, unknown>): Promise<Reply>;
  drain_events(): Promise<ToolEvent[]>;
  plugin_action(id: string, action: string, confirmed?: boolean): Promise<Reply>;
  plugin_diagnostics(id: string): Promise<Reply>;
  inspect_plugin_package(): Promise<Reply>;
  install_plugin(ticket: string): Promise<Reply>;
  configure_plugin_runtime(id: string): Promise<Reply>;
  open_plugins_folder(): Promise<Reply>;
  rescan_plugins(): Promise<Reply>;
  window_action(action: string, confirmed?: boolean): Promise<Reply>;
  resize_window(edge: string): Promise<Reply>;
  prepare_plugin_export(id?: string): Promise<Reply>;
  save_plugin_export(ticket: string): Promise<Reply>;
  export_plugin_starter(): Promise<Reply>;
  assistant_state(): Promise<Reply>;
  assistant_allow(plugins: string[]): Promise<Reply>;
  assistant_decide(ticket: string, approve: boolean): Promise<Reply>;
  assistant_bridge(): Promise<Reply>;
  assistant_check(): Promise<Reply>;
  mcp_clients(): Promise<Reply>;
  mcp_install(client: string): Promise<Reply>;
  mcp_restore(ticket: string): Promise<Reply>;
  mcp_manage(client: string, enabled: boolean): Promise<Reply>;
  mcp_connection(client: string, enabled: boolean): Promise<Reply>;
  export_dsh_plugin(id: string): Promise<Reply>;
}
export interface AssistantTool {
  name: string;
  description: string;
  readOnly: boolean;
  pluginId: string;
  pluginName: string;
  command: string;
}
export interface ToolApproval {
  id: string;
  owner: string;
  pluginName: string;
  description: string;
  arguments: Record<string, unknown>;
  redactedCount?: number;
}
export interface AssistantState {
  enabled?: boolean;
  clients?: string[];
  tools: AssistantTool[];
  selected: string[];
  pending: ToolApproval[];
  audit: {
    id: string;
    owner?: string;
    pluginName: string;
    readOnly: boolean;
    ok: boolean;
    time: number;
  }[];
}
export interface Profile {
  id: string;
  name: string;
  values: Values;
  source?: string;
  sourceLabel?: string;
  readOnly?: boolean;
  blockedReason?: string;
  sourcePath?: string;
  editIssue?: string;
  revision?: string;
  backupId?: string;
}
export interface ProfileList {
  profiles: Profile[];
  issues: string[];
  sourceFile?: string;
}
export interface PackagePreview {
  ticket: string;
  manifest: Manifest;
  sha256: string;
  fileCount: number;
  sizeBytes: number;
  previousVersion?: string;
  requirements: string;
}
export interface ExportPreview {
  ticket: string;
  manifest: Manifest;
  fileCount: number;
  sizeBytes: number;
  expandedBytes: number;
  files: string[];
  excluded: string[];
  sha256: string;
  fileName: string;
}
declare global {
  interface Window {
    pywebview?: { api: HostApi };
  }
}

export interface WorkActivity {
  connected: boolean;
  background: boolean;
  invoking: boolean;
  active: boolean;
}
export interface WorkProtection {
  needsConfirmation?: boolean;
  connections: number;
  backgroundTasks: number;
  commands: number;
  activePlugins: number;
}
export interface RuntimeDiagnostic {
  id: string;
  phase: string;
  exitCode: number | null;
  time: number;
  records: {
    kind: string;
    type?: string;
    module?: string;
    file?: string;
    line?: number;
    function?: string;
    command?: string;
  }[];
}
