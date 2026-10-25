# 插件接入规范 · SDK v1

## 设计约定

插件提供能力与声明，宿主提供界面。插件不得为内置部件注入 HTML、CSS 或 JavaScript；所有插件共享表单、按钮、终端、通知、配色和无障碍行为。工具从工作台卡片进入，已打开工具保留在顶部标签栏，配置在居中面板中按需展开，结果或终端使用完整工作区；这些布局由宿主决定，插件无需更改业务逻辑。目前支持三类统一界面部件：

| surface | 工作台提供 | 插件实现 |
| --- | --- | --- |
| `form` | 配置表单、执行按钮、结构化结果视图 | 接收字段参数，返回 JSON 可序列化结果 |
| `terminal` | 配置表单、连接管理、交互终端、状态栏 | 连接、断开、输入、尺寸变化、终端输出事件 |
| `mcp`（宿主专用） | MCP 连接中心 | 核心 MCP 插件使用，普通插件选 form 或 terminal |

不在插件中复制整套界面。未来的串口、TCP/UDP、计算器部件应作为宿主 SDK 的扩展加入：先定义字段、动作、状态、输出和释放资源的契约，再由宿主实现通用部件。

## 最小目录

```text
plugins/projects/hello/
  manifest.json
  plugin.py
```

请从应用下载完整示例。仓库的模板在 `docs/templates/starter`；仅复制这个目录时需先在宿主工程中运行。唯一内置的 MCP 工程位于 `plugins/projects/mcp`，工作台默认仅预装 MCP，并扫描安装根目录 plugins/ 中的源码子目录及旧托管目录；分发时使用 `python scripts/package_plugin.py 插件目录` 生成 `.cove-plugin` 文件，在“插件”页导入即生效。无效插件进入错误列表，其余插件继续加载，无需修改前端注册表。

## manifest.json

可以添加 `"$schema": "./sdk/plugin-manifest.schema.json"` 获得编辑器补全与结构校验。宿主另做命令引用、字段引用和部件契约校验。

```json
{
  "sdkVersion": 1,
  "id": "community.hello",
  "name": "Hello 工具",
  "description": "无需前端代码的插件",
  "version": "0.1.0",
  "author": "Community",
  "category": "示例",
  "icon": "terminal",
  "color": "blue",
  "permissions": [],
  "commands": ["greet"],
  "ui": {
    "surface": "form",
    "fields": [
      {"id": "name", "label": "姓名", "type": "text", "default": "开发者", "required": true}
    ],
    "actions": [{"command": "greet", "label": "打个招呼", "variant": "primary"}]
  }
}
```

`id` 是稳定标识，匹配 `[a-z][a-z0-9.-]{1,63}`，不可与其他插件重复，也不能包含连续点、末尾点或 Windows 保留名称。`sdkVersion` 决定协议兼容性，`version` 是插件自己的版本。只有 `commands` 中声明的公开方法可被调用。v1 的 `ui.actions` 必须且只可包含一个主动作；断开、终端输入等辅助命令通过部件契约绑定。`icon` 可选 `terminal`、`plug`、`activity`、`circuit-board`、`file-chart-column`、`list-todo`、`folder`、`wrench` 或 `braces`；缺省或未知名称按界面能力回退，不执行插件代码。插件插画沿用 Cove 原 Logo 的黑白、圆润形体、镂空与轻微偏转；`color` 仍可作为元数据保留，插画保持自己的品牌墨色。

`permissions` 为能力说明，例如 `network.tcp`、`filesystem.read`；它们不是已强制执行的安全边界。不信任的代码应经过审查后再放入插件目录。

## 宿主兼容声明

旧 v1 清单可以省略此字段。新插件可按需要声明：

```json
"compatibility": {
  "minHostVersion": "0.9.0",
  "capabilities": ["ui.form", "ui.job", "ai.tools"]
}
```

可选 `maxHostVersion` 与 `minHostVersion` 都使用三段数字且包含边界；没有经过验证的最高版本不应随意填写。`capabilities` 为必需能力而非建议项，未知能力会显示原因并阻止桌面安装/启动和 AI 调用。

| 能力 | 含义 |
| --- | --- |
| `ui.form` / `ui.terminal` | 统一表单 / 交互终端 |
| `ui.result` | Cove 0.11.0 起的声明式结果卡片和分页表格 |
| `ui.profiles` | 持久配置管理 |
| `ui.job` / `ui.instrument` | 后台任务 / 仪器部件；两者不可同时绑定 |
| `ai.tools` / `host.tools` | AI 工具声明 / 插件调用宿主工具的契约 |
| `ui.mcp` | 内置 `dev.cove.mcp` 专用连接界面 |

新增部件需要宿主实现共享渲染器，声明能力不会自动创建前端。独立 portable MCP 不提供桌面界面，宿主版本范围用于 Cove 桌面兼容性判断。

在 Cove 仓库执行 `.venv\Scripts\python.exe scripts/check_plugin.py <源码目录或.cove-plugin文件>`，可在不执行插件代码的情况下检查结构与当前宿主兼容性。应用内导入仍需包预览；源码重扫不热更新已运行的模块，改代码后显式重启相应插件。

可选环境诊断使用 `scripts/check_plugin.py <源码目录> --doctor`；下载的完整示例也提供 `python doctor.py`。诊断报告实际选择的解释器、Python 版本与位数、依赖声明及已安装发行版元数据。诊断不导入插件、不安装依赖；不能验证的版本范围、环境标记或依赖来源会明确标为未验证。它不能替代真实 Worker、界面及安装包验收。

两种诊断入口均可加 `--python "C:\path\to\python.exe"`。显式指定优先，其次选择项目 `.venv`，最后使用当前 Python；独立命令不会读取 Cove 已保存的解释器设置。Python 低于 3.11 会报告错误。`status: partial` 表示仍有约束未验证，`installed` 只表示找到发行版元数据，不保证模块或原生 DLL 可以加载；环境探测子进程跳过 `.pth` 与 `sitecustomize`。安装版自带的 Cove-worker 不是通用 Python 命令，不能作为 `--python` 的目标。

## 表单字段

| 属性 | 约定 |
| --- | --- |
| `id` | Python 命令的关键字参数名，字母开头的小写字母、数字和下划线，不允许重复 |
| `label` | 工作台显示名称 |
| `type` | `text`、`password`、`number`、`select` |
| `default` | 初始值，字符串或数字 |
| `placeholder` | 输入提示 |
| `required` | 工作台提交前做必填校验，插件仍须独立验证参数 |
| `min` / `max` | 数字输入边界 |
| `span` | 在统一四列字段布局中占 1–4 列；默认 4，常见地址/端口组合使用 3 + 1 |
| `options` | select 选项，`[{"value":"key","label":"私钥"}]` |
| `secret` | 工作台不将该字段写入连接配置或最近使用数据；password 字段自动按此规则处理 |
| `advanced` | 为 true 时收进高级选项，常规界面只显示必要字段 |
| `showWhen` | 根据其他字段显示：`{"field":"auth","equals":"key"}` 或 `notEquals` |

提交只包含当前可见字段；插件应为条件字段设置 Python 默认参数。数字字段转换为数值，空字段仍为 `""`。所有内容按文本渲染，返回值不会当作 HTML 执行。

## Python 命令

### 统一结果界面（Cove 0.11.0）

普通 `form` 可选声明 `ui.result`。插件返回普通字典；宿主负责卡片、表格、空状态、分页和主题。此布局不能与 `job` / `instrument` 混用，并须在 `compatibility.capabilities` 中声明 `ui.result`。未声明结果布局的旧 v1 插件继续显示原始 JSON。

```json
"result": {
  "title": "检测结果",
  "fields": [{"key":"count", "label":"样本数", "format":"number"}],
  "table": {"key":"rows", "columns":[
    {"key":"name", "label":"名称"},
    {"key":"voltage", "label":"电压", "format":"number", "unit":"V"}
  ]}
}
```

Python 返回 `{"count":2,"rows":[{"name":"A","voltage":3.3}, ...]}`。键名是顶层属性名，不是路径或表达式。格式为 `text`、`number`、`json`；缺失值显示横线。最多 24 个卡片字段、12 列，每页 50 行，可翻页查看全部记录。文字按文本处理，不执行 HTML；只展示清单选定的字段。`title` 和表格的 `emptyText` 可选。

可运行示例在 `docs/examples/result-starter`，下载开发包也在 `examples/result-starter` 提供独立 SDK、运行和打包脚本。开发者替换业务命令和数据键即可，无需修改宿主。

### 后台任务 helper（Cove 0.11.0）

从 `toolbench.sdk` 导入 `BackgroundJob`，在插件构造时创建一个实例。主动作调用 `job.start(callback, total=..., message=...)` 立即返回快照；`ui.job` 继续绑定现有 `snapshot` 与 `cancel` 命令。回调用 `control.update(completed=..., message=...)` 上报进度，在工作单元之间调用 `control.check_cancelled()`，或用 `control.wait(seconds)` 可中断等待。返回可选 JSON 对象作为最终结果，状态默认为 `completed`，部分成功可指定 `partial`。总量未知时省略 `total`。

helper 统一发布 `job` 事件和 `activity` 状态，管理当前 Worker 生命周期内递增的 `revision`，防止并发启动和旧进度覆盖终态。`cancel()` 只请求合作式取消；回调实际退出后才解除活动保护。`Tool.close()` 调用 `job.close()` 有界等待，不能宣称强制停止未响应的外部操作。它不保存历史、不自动回滚写入或恢复进程退出前的任务。完整无硬件示例在 `docs/examples/job-starter`，下载开发包的同名目录可直接 `python -S dev.py`。

### 命令实现

```python
from toolbench.sdk import Plugin, CommandError

class Tool(Plugin):
    def greet(self, name="开发者"):
        if not name.strip():
            raise CommandError("请填写姓名", "NAME_REQUIRED")
        return {"message": f"你好，{name}！"}

    def close(self):
        # 释放线程、设备或连接；应可重复调用。
        pass
```

每条请求在工作进程中的独立线程执行，插件需要使用 `self.lock` 保护共享状态。终端输入由宿主按顺序提交；其他长任务应自行处理互斥。命令返回值须可 JSON 序列化；普通异常转为可读错误，`CommandError(message, code, details)` 可附带结构化错误码和详情。

普通命令的执行预算为 20 秒。命令通过 SDK 等待宿主时，该请求暂停普通执行计时；写操作审批最多 180 秒，SDK 桥接最多 220 秒，请求总期限为 245 秒，支持配置超时的客户端使用 250 秒。策略集中在 `toolbench/plugin_framework/policy.py`。等待审批不会按普通命令的 20 秒期限杀死调用方；调用方停止、退出或超时会取消其待审批写操作。长任务应后台执行，并用 `context.emit("activity", active=True/False)` 声明活动状态。

插件构造阶段的 SDK 回复也由独立协议读取线程处理。普通执行超时仍释放对应进程以阻止迟到的连接成功；其他插件不受影响。`print()` 重定向到 stderr，避免破坏协议。诊断只提取异常类型、缺少的模块、文件名、行号和退出码，不保留原始 stderr、异常消息、源代码或参数。可从插件详情的“运行诊断”查看。

## 仪器部件（Cove 0.7.3）

`form` 可声明 `ui.connection` 与 `ui.instrument`，以共享的仪器工作区显示波形、测量和 PNG 屏幕。`instrument` 必须完整绑定 `status`、`measure`、`waveform`、`screenshot`、`acquisition`、`timebase`、`channel`、`trigger`、`snapshot` 到已声明的命令。参数、结果与事件由共享部件契约定义。工作区订阅 `instrument` 事件 `{kind,result}`；结果携带采集时间，离开页面保留会话。AI 工具结果保留完整数组和图像，结果上限 16 MiB；截图 `{mime:"image/png",data_url:"data:image/png;base64,..."}` 经 MCP 作为标准 image 内容块返回。确认界面完整展示非秘密参数，秘密字段标记为 `[redacted]` 并显示遮盖数量；批准后仍使用原始值执行。当前 instrument 是示波器式领域契约，不能宣称已适用于所有仪器。

## 终端部件

在普通清单中增加：

```json
{
  "commands": ["connect", "disconnect", "write", "resize"],
  "ui": {
    "surface": "terminal",
    "connection": {"connect": "connect", "disconnect": "disconnect"},
    "terminal": {"write": "write", "resize": "resize", "dataEvent": "terminal"},
    "actions": [{"command": "connect", "label": "连接主机"}],
    "fields": [],
    "empty": {"title": "准备连接", "description": "填写连接信息后开始。"},
    "status": {"idle": "未连接", "connected": "已连接"}
  }
}
```

| 方法 / 事件 | 输入或输出 |
| --- | --- |
| connect | 接收可见表单参数；成功返回 `{"connected":true,"label":"用户名@主机"}` |
| disconnect | 不接收表单参数；返回 `{"connected":false}` |
| write | 参数 `data: str`，保留控制字符，禁止自行添加换行 |
| resize | 参数 `cols: int, rows: int`，传递字符单元尺寸 |
| `context.emit("terminal", text="...", size=123)` | 输出 UTF-8 解码后的终端字符；按流使用增量解码器 |
| `context.status(True, "连接说明")` | 同步工作台连接状态；远程关闭时必须发布 False |

`dataEvent`、命令名可以改变，只需清单和 Python 实现保持一致。插件无需导入 xterm；工作台自动实例化终端、处理输入排队、视图尺寸、字号和输出订阅。一个插件在 v1 中拥有一个工作区与一个当前连接；切换页面时保留，退出应用时释放。

SDK 还提供 `context.received(bytes)` / `context.sent(bytes)` 以及数据编码辅助函数，供后续收发部件使用；v1 界面尚未渲染通用数据流部件。

## 持久连接配置

可选的 `ui.profiles` 将四个已声明命令绑定到统一的连接管理界面：

```json
{"profiles":{"list":"list_profiles","scan":"scan_profiles","save":"save_profile","remove":"delete_profile"}}
```

list / scan 返回 `{"profiles":[{"id":"stable-id","name":"显示名称","values":{},"source":"workbench","readOnly":false}],"issues":[]}`。读取外部已有配置的条目可标记 `readOnly:true`；无法连接的配置附带 `blockedReason`，宿主会展示原因。scan 用于重新发现现有配置。

可选绑定 `restore:"restore_profile"`。编辑外部源配置时，list 返回 `revision`，save 接收完整条目，remove 接收 `profile_id` 和 `revision`；保存或删除返回 `backupId`，宿主展示撤销按钮，调用 restore 的 `{ticket:backupId}`。插件应比较版本再写入，并在撤销时检查修改后哈希，避免覆盖外部新内容。外部来源应由插件自行实现，并向宿主返回结构化状态。

save 接收 `profile` 对象，返回保存后的配置；remove 接收 `profile_id`。只存非秘密字段，持久化需要原子替换，并在插件锁内处理修改。readonly 条目保存时应创建副本，不能改写外部原文件。宿主在连接时额外提供 `profile_id`，供插件再次检查配置是否有效。配置存储由插件自行实现。

## 插件包与生命周期

应用内“开发指南”提供分步说明和独立示例项目，示例自带 SDK、`doctor.py`、`dev.py` 与 `package.py`。本地先执行 `python doctor.py` 查看环境诊断，再用报告中的解释器运行 `dev.py`，最后执行 `python package.py`；诊断与打包使用标准库，无需安装宿主依赖。也可直接在 Cove 的“插件 → 打包项目”选择源码目录。

“管理与详情 → 导出插件”会导出已安装的代码和资源，不包含数据目录或解释器。两种打包方式均先展示清单与排除项，确认后用文件保存对话框写出 `.cove-plugin`。图片、CSV、ZIP 资源和 vendor 可以随包分发；以插件根目录的 manifest 为入口，资源子目录允许包含自己的 manifest.json。

默认排除 Git、虚拟环境、缓存、`.env*`、私钥类文件、旧插件包和常见根目录运行配置。`.coveignore` 使用简单排除通配符（例如 `tests/`、`*.log`），不支持 `!` 反选。导出会拒绝符号链接和 Windows 目录联接；请检查清单后分享。

`.cove-plugin` 是单插件 ZIP，根目录或单个目录内包含 `manifest.json` 和 `plugin.py`。不能包含环境目录、符号链接、路径穿越、重复文件或 Windows 保留路径。压缩包最大 20 MB，解压后最大 50 MB、500 个文件。导入预览不执行代码，确认票据绑定已检查的原始字节，10 分钟后过期。安装不会自动执行 pip 或安装脚本。

插件运行、停止、重启、启停用与移除由宿主管理。数据目录独立于安装目录，更新与移除代码不删除配置。对长连接使用 `context.status`；其他后台任务应 `context.emit("activity", active=True)`，结束后发布 False，避免“释放空闲进程”中止仍在工作的插件。正在执行命令的进程也会保留。

## 声明式确认扩展

插件使用 `ui.confirmations` 把结构化错误码映射为统一对话框、详情字段和重试参数。宿主不判断具体业务身份。确认内容必须可核对，插件在重试时仍需验证实际状态；秘密字段只保存在会话内存中。

## 依赖、进程与数据

插件可声明自己的 `requirements.txt`。开发者或用户负责安装，宿主不自动下载或执行安装脚本。需要隔离依赖时：

```powershell
python -m venv plugins/projects/my-tool/.venv
plugins/projects/my-tool/.venv/Scripts/python.exe -m pip install -r plugins/projects/my-tool/requirements.txt
```

该环境需要 Python 3.11+。也可在插件详情中选择已经安装好依赖的 `python.exe`，或将兼容依赖随 `vendor/` 分发。宿主通过 `PYTHONPATH` 提供 SDK，无需插件再安装工作台包。未提供独立环境时，源码版使用宿主解释器，安装版使用自带的 Cove-worker。工作进程以宿主资源目录为工作目录；插件文件请相对 `__file__` 定位，持久数据请写入 `self.context.data_dir`。

协议使用 stdin/stdout 的 NDJSON：

```json
{"id":"请求标识","command":"write","payload":{"data":"ls\r"}}
{"id":"请求标识","ok":true,"result":{"bytes":3}}
{"event":"terminal","data":{"text":"README.md\r\n","size":11}}
{"id":"请求标识","ok":false,"error":"可读错误","code":"PLUGIN_ERROR","details":{}}
```

框架负责请求标识、路由与异常封装，插件只需实现方法与发布事件。工作进程异常退出会令待处理请求失败，其他插件保持运行。`close()` 在正常 stdin 关闭时调用；超时或强制终止时依靠进程退出释放操作系统资源。

## 接入验收

1. 清单可通过 `toolbench.host.validate_manifest`，字段和命令名一致。
2. 参数为空、非法、连接失败时能返回可读错误，插件不泄露秘密。
3. 连续连接、断开、再次连接不会残留设备句柄或后台任务。
4. 远程关闭会话后及时发布状态；终端中文字符不被拆坏。
5. 插件离开页面后可继续工作，关闭应用后资源释放。
6. 使用自己的虚拟环境时无需修改宿主。

契约验收案例见 `tests/test_contracts.py`。该规范与 UI 当前实现保持同步；新的部件类别需提升宿主能力，不通过任意 HTML 逃逸统一界面。


## AI 调试工具契约

一个普通 form / terminal 插件可以通过 `ai.tools` 公开稳定工具。它仍然在同一个工作进程内运行，AI 读取的是用户正在调试的那个会话。

```json
"ai": {
  "tools": [{
    "name": "snapshot",
    "command": "snapshot",
    "description": "读取当前设备调试状态和最近结果，不发送数据",
    "readOnly": true,
    "parameters": {
      "type": "object", "properties": {}, "required": [],
      "additionalProperties": false
    }
  }]
}
```

`snapshot` 同时必须存在于 `commands` 中，并由 Tool 实现。`parameters` 是 JSON Schema；宿主在执行前再次校验参数。名称只能使用小写字母、数字和下划线，必须以字母开头；同插件内不得重复。密码和 secret 字段不能作为 AI 工具参数。

用户在左侧“智能体工具”页面勾选插件并保存授权后，其工具才会向 MCP 客户端提供。客户端接入和连接诊断位于“工作台 → MCP 连接”。`readOnly: false` 的调用绑定不可变参数快照，等待 Cove 人工确认；拒绝、超时、撤销授权或退出 Cove都不会执行待确认操作。只有经过该桥接的 AI 调用受此确认流程约束；可信插件本身仍具备当前用户的 Python 权限，`readOnly` 是开发者声明，不是操作系统级沙箱。

## 独立 MCP 与 DeepSeek Harness

点击插件详情的“导出 DSH”，或运行示例的 `python package.py`。生成的 `-dsh.zip` 包含原样业务代码、轻量运行时、`serve.py`、依赖声明和 `setup_dsh.py`。解压后安装依赖，运行 setup_dsh.py，按打印出的命令启动 DSH。每个插件由稳定 id 派生独立的 DSH serverName，可同时加载多个插件。

独立服务只注册 `readOnly:true` 的工具，并在服务端再次拒绝写工具。它拥有独立数据目录，不会自动获得 Cove 当前工具会话；需要当前会话和经确认的写操作时，使用 Cove 桌面 MCP 连接。

具体路线、验证方式和后续 Cordis 服务适配边界见 [DSH 兼容架构](dsh-compatibility.md)。


## 活动工作与管理操作

连接、后台活动和执行中/等待审批的调用共同组成活动状态。退出、关闭标签、停止、重启和停用都必须经过相同确认；释放空闲进程跳过任何活动状态。更新代码或切换解释器前先结束活动工作。停止任一调用方会使其未执行的审批请求失效。外部配置条目可以返回 `sourceLabel`，由通用框架显示来源名称；旧外部来源仍由兼容适配器识别。

