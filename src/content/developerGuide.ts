import { t } from '../core/i18n.ts';
export interface GuideBlock {
  kind: 'p' | 'code' | 'prompt';
  text: string;
}
export interface GuideChapter {
  title: string;
  subtitle: string;
  blocks: GuideBlock[];
}
export const traditional = (): GuideChapter[] => [
  {
    title: t('准备你的项目'),
    subtitle: t('下载示例，先让它运行起来。'),
    blocks: [
      {
        kind: 'p',
        text: t(
          '先安装 Python 3.11 或更新版本。点击右上角“下载示例”，解压到一个独立文件夹，在该文件夹打开终端。开发表单插件不需要安装 Node.js 或编写前端。',
        ),
      },
      {
        kind: 'code',
        text: 'python --version\npython dev.py\npython dev.py greet name=Cove',
      },
      {
        kind: 'p',
        text: t(
          '最后一条命令应输出 {"message": "你好，Cove！"}。dev.py 会读取清单并调用同一个 Tool 类，不需要先安装插件。若提示找不到 Python，请先完成 Python 安装并重新打开终端。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '项目已经包含 manifest.json、plugin.py、dev.py 和 package.py。sdk 文件夹是开发运行时，打包时会排除。examples/result-starter 演示统一统计卡片和表格，examples/job-starter 演示进度和取消；每个目录自带 SDK，可以独立复制运行。你的业务代码放在 plugin.py，资源放在项目内部。',
        ),
      },
    ],
  },
  {
    title: t('描述插件与界面'),
    subtitle: t('一份清单，连接身份、表单和命令。'),
    blocks: [
      {
        kind: 'p',
        text: t(
          'manifest.json 的 id 是插件的永久身份。你自己的项目应改成独立 id，例如 community.text-helper。commands 声明可调用方法；字段 id 要与 Python 参数一致；actions.command 必须出现在 commands 中。',
        ),
      },
      {
        kind: 'code',
        text: '{\n  "$schema": "./sdk/plugin-manifest.schema.json",\n  "sdkVersion": 1,\n  "id": "community.hello",\n  "name": "Hello 工具",\n  "description": "一个无需编写前端代码的 Python 插件示例。",\n  "version": "0.1.0",\n  "author": "Community",\n  "category": "示例",\n  "icon": "terminal",\n  "color": "blue",\n  "permissions": [],\n  "commands": [\n    "greet"\n  ],\n  "ui": {\n    "surface": "form",\n    "fields": [\n      {\n        "id": "name",\n        "label": "姓名",\n        "type": "text",\n        "default": "开发者",\n        "required": true\n      }\n    ],\n    "actions": [\n      {\n        "command": "greet",\n        "label": "打个招呼",\n        "variant": "primary"\n      }\n    ]\n  },\n  "ai": {\n    "tools": [\n      {\n        "name": "greet",\n        "command": "greet",\n        "description": "生成一条问候语。",\n        "readOnly": true,\n        "parameters": {\n          "type": "object",\n          "properties": {\n            "name": {\n              "type": "string",\n              "minLength": 1,\n              "maxLength": 80\n            }\n          },\n          "required": [\n            "name"\n          ],\n          "additionalProperties": false\n        }\n      }\n    ]\n  }\n}\n',
      },
      {
        kind: 'p',
        text: t(
          'ui.surface=form 使用 Cove 的原生表单与结果面板。字段可使用 text、password、number、select。密码字段声明 secret:true，不放默认密码。ai.tools 是 MCP 契约；表单参数和工具参数都要与同一个方法保持一致。每次改完清单，运行 python dev.py，先确认可以通过校验。',
        ),
      },
    ],
  },
  {
    title: t('实现 Python 功能'),
    subtitle: t('只写功能，不用复制一套界面。'),
    blocks: [
      {
        kind: 'code',
        text: 'from toolbench.sdk import Plugin\n\n\nclass Tool(Plugin):\n    def greet(self, name="开发者"):\n        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:\n            raise ValueError("姓名需要 1–80 个字符")\n        return {"message": f"你好，{name.strip()}！"}\n',
      },
      {
        kind: 'p',
        text: t(
          'Tool 必须继承 Plugin。方法名与清单一致，返回 JSON 可序列化的数据。不要在结果中放 API Key、密码或私钥。数据文件保存在 self.context.data_dir，不能写回插件源码目录。用 close() 释放线程、网络连接和文件句柄。',
        ),
      },
      {
        kind: 'code',
        text: 'python dev.py greet name=Cove\npython dev.py greet name=',
      },
      {
        kind: 'p',
        text: t(
          '第一条得到正常问候，第二条应报“姓名需要 1–80 个字符”。失败输入也必须有明确结果。耗时任务应及时返回并用 context.emit 或 context.status 发送状态，避免阻塞界面。',
        ),
      },
    ],
  },
  {
    title: t('让 AI 客户端使用插件'),
    subtitle: t('同一份命令，支持 Cove 与 DSH。'),
    blocks: [
      {
        kind: 'p',
        text: t(
          '示例的 ai.tools 已把 greet 声明为只读 MCP 工具。parameters 使用 JSON Schema，并关闭 additionalProperties；可接受参数必须与方法签名一致。只读工具不会改变外部状态。发包、执行命令和修改文件等行为必须 readOnly:false，Cove 会完整显示非秘密参数、明确遮盖敏感字段并等待单次确认。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '在 Cove 安装插件后，打开左侧智能体工具 授权你的插件，再从工作台打开 MCP 并按指引配置目标客户端。保存配置后，在目标客户端启动或重新加载 MCP 适配器，再调用问候工具并传入 name=Cove。你应同时在客户端看到问候结果，在 Cove 的调用记录中看到真实执行。',
        ),
      },
      {
        kind: 'code',
        text: 'python -m pip install -r requirements-dev.txt\npython setup_dsh.py',
      },
      {
        kind: 'p',
        text: t(
          '第二条命令生成包含当前绝对路径的 cove.dsh.yml，并打印 dsh web --patch 命令。运行打印的命令，即可由 DeepSeek Harness 通过官方 dsh-mcp-client 加载同一插件。独立模式仅公开只读工具；需要当前工具会话或写操作确认时，在 Cove 的 MCP 页面连接 DSH。',
        ),
      },
    ],
  },
  {
    title: t('测试、打包与安装'),
    subtitle: t('验证产物，而不只验证源码。'),
    blocks: [
      {
        kind: 'code',
        text: 'python dev.py greet name=Cove\npython package.py',
      },
      {
        kind: 'p',
        text: t(
          'exports 文件夹会生成 .cove-plugin 和 -dsh.zip 两种产物。Cove 包包含业务代码和资源，排除 SDK、虚拟环境、用户数据和开发脚本。打开 Cove → 插件 → 导入插件，选择 .cove-plugin，核对来源并导入，再运行一次。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '解压 -dsh.zip，在新的目录执行 python -m pip install -r requirements.txt，再执行 python setup_dsh.py，按输出运行 DSH。不要把开发目录中的 .local 或凭据复制给其他人。包需要额外依赖时，在 requirements.txt 中声明，并提供 vendor 或独立 Python 环境。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '验收四件事：正常输入成功；错误输入给出清晰错误；MCP 未授权时不可见；重新打开 Cove 后插件仍可用。测试写工具还必须确认拒绝操作不会改变目标状态。',
        ),
      },
    ],
  },
  {
    title: t('维护与下一步'),
    subtitle: t('让插件可以长期迭代。'),
    blocks: [
      {
        kind: 'p',
        text: t(
          '更新保留 id、提升 version。不要随意改 MCP 工具名或参数含义，否则旧客户端和会话会失效。新增参数优先提供默认值；数据升级要可恢复。安装升级只替换代码，用户数据保留。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '终端部件通过清单绑定输入、输出、尺寸和连接状态，并由插件实现 close()。需要适配 DSH 时优先复用 ai.tools 与独立 MCP 出口；在真实任务证明有必要后，再编写 Cordis 原生服务适配层。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '发布前在干净目录安装实际产物，记录 Python 版本、依赖和兼容的 Cove / DSH 版本。随包提供功能说明、示例输入、权限说明和常见失败的处理方式。',
        ),
      },
    ],
  },
];
export const vibe = (): GuideChapter[] => [
  {
    title: t('把需求交给 AI'),
    subtitle: t('给它一份能工作、能验证的起点。'),
    blocks: [
      {
        kind: 'p',
        text: t(
          '点击“下载示例”，解压后用你常用的 AI 编程工具打开整个目录。先运行 python dev.py 确认环境可用。把下面提示词的方括号内容改成真实需求，再发送给 AI。示例不是对话截图，而是可以直接运行、测试和打包的完整工程。',
        ),
      },
      {
        kind: 'prompt',
        text: t(
          '请在我提供的 Cove 示例项目中开发插件。先阅读 manifest.json、plugin.py、README-dev.md 和 sdk/plugin-manifest.schema.json，再修改源码。\n需求：\n- 名称：[插件名称]\n- id：[community.my-tool，使用独立且稳定的 id]\n- 要解决的问题：[描述真实场景]\n- 输入字段：[字段名、类型、必填与默认值]\n- 结果：[列出期望返回的数据]\n- 操作性质：[只读 / 会改变外部状态，请逐个说明]\n约束：\n1. 保持 Tool(Plugin) 和公开命令契约，业务写在 Python，不添加自定义 HTML/JS/CSS。\n2. manifest.commands、ui.actions、字段 id、ai.tools.command 与方法签名完全对应。\n3. MCP 参数写出完整 JSON Schema，additionalProperties:false；改变状态的操作 readOnly:false。\n4. 凭据不进入清单默认值、日志、结果或源码。用户数据写 self.context.data_dir。\n5. 先实现最小可运行版本，再验证。不要伪造运行成功、调用结果或兼容性。\n6. 说明修改了哪些文件，运行了哪些命令，哪些验收尚未完成。',
        ),
      },
    ],
  },
  {
    title: t('先做出最小版本'),
    subtitle: t('控制范围，比一次生成很多代码更可靠。'),
    blocks: [
      {
        kind: 'prompt',
        text: t(
          '先只完成一个主命令。列出输入、输出和失败条件，然后实现 manifest.json 与 plugin.py。复用现有 dev.py 与 package.py。将额外依赖写入 requirements.txt，但不要擅自安装不明来源的程序。完成后实际运行 python dev.py，并解释返回结果。遇到错误先修复，不要绕过清单校验，也不要用固定的成功字符串代替真实功能。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '先在本地命令行得到真实结果，再导入 Cove。不要接受只有代码、没有执行证据的交付。若 AI 无法执行命令，由你运行并把完整错误交回给它。',
        ),
      },
    ],
  },
  {
    title: t('让 AI 检查自己的产物'),
    subtitle: t('用失败场景检验，而不只点一次成功。'),
    blocks: [
      {
        kind: 'prompt',
        text: t(
          '请对当前插件做实际验收：1. 正常输入得到期望结果；2. 空值、非法格式、超长值和不存在资源给出清晰错误；3. 清单命令与实际方法一致；4. 输出可以 json.dumps；5. close() 释放资源；6. 不向结果和日志输出凭据。运行 dev.py，提供真实命令、退出码和结果。修复失败后重跑受影响的检查。需要访问真实主机或写入外部服务的测试先改用隔离的本机测试资源，不伪造远端验证结果。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '核对错误是否指向真实输入，而不是被 try/except 吞掉。涉及网络的功能还应测试超时和取消。',
        ),
      },
    ],
  },
  {
    title: t('同时接入 Cove 与 DSH'),
    subtitle: t('让兼容性成为验收的一部分。'),
    blocks: [
      {
        kind: 'prompt',
        text: t(
          '请为当前插件的适合自动化的命令补齐 ai.tools。用同一个 Python 方法，不复制业务实现。只读查询设 readOnly:true，改变状态的命令设 false，并明确参数 Schema。运行 python package.py，检查 .cove-plugin 和 -dsh.zip 内容没有 sdk、虚拟环境、用户数据或凭据。在干净目录解压 DSH 包，安装 requirements.txt，运行 setup_dsh.py 并检验生成的官方 dsh-mcp-client overlay。用 MCP 客户端完成 initialize、tools/list 和一次真实 tools/call。独立模式只公开只读工具；写操作走 Cove 桌面的单次确认。没有 DSH 环境时要明确说明，不声称已完成 DSH 会话联调。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '在 Cove 导入实际的 .cove-plugin，打开插件运行一次，再到智能体工具授权它。从工作台打开 MCP，按目标客户端指引保存配置、启动适配器并完成真实调用。两种产物应返回同样的业务结果。',
        ),
      },
    ],
  },
  {
    title: t('打包交付与迭代'),
    subtitle: t('一份可安装的产物，配上清晰的使用说明。'),
    blocks: [
      {
        kind: 'prompt',
        text: t(
          '请生成最终交付：1. 提升插件 version，保持 id 和既有工具名；2. 运行 package.py；3. 在隔离目录验证打包后的实际代码；4. 提供安装、示例输入、依赖、权限及故障排查说明；5. 列出 Cove GUI、MCP 和 DSH 三条路径的验证状态；6. 检查源码与产物均无密码、Key、个人路径或用户数据。不要把临时测试输出当作发布文件。最后报告工程目录、两个产物的绝对路径和仍未验证的项目。',
        ),
      },
      {
        kind: 'p',
        text: t(
          '功能增加时重复“小改动 → 实际运行 → 产物验收”。把已确认的输入输出写进 README，不让 AI 在每次迭代时重新猜测契约。',
        ),
      },
    ],
  },
];
