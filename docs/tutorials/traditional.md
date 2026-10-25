# 传统插件开发

## 1. 准备你的项目

下载示例，先让它运行起来。

先安装 Python 3.11 或更新版本。点击右上角“下载示例”，解压到一个独立文件夹，在该文件夹打开终端。开发表单插件不需要安装 Node.js 或编写前端。

```
python --version
python doctor.py
python dev.py
python dev.py greet name=Cove
```

最后一条命令应输出 {"message": "你好，Cove！"}。dev.py 会读取清单并调用同一个 Tool 类，不需要先安装插件。若提示找不到 Python，请先完成 Python 安装并重新打开终端。

`python doctor.py` 检查清单、兼容性、Python 3.11+ 与依赖安装信息，不加载插件或安装依赖。默认优先选择项目 `.venv`，也可用 `python doctor.py --python "C:\path\to\python.exe"` 指定环境；它不会读取 Cove 中保存的解释器设置。报告中的 `partial` 表示版本约束等项目尚未验证。若选择了独立环境，用该解释器运行 `dev.py` 才能验证同一个环境中的实际命令。

项目已经包含 manifest.json、plugin.py、doctor.py、dev.py 和 package.py。sdk 文件夹是开发运行时，打包时会排除。你的业务代码放在 plugin.py，资源放在项目内部。

## 2. 描述插件与界面

一份清单，连接身份、表单和命令。

manifest.json 的 id 是插件的永久身份。你自己的项目应改成独立 id，例如 community.text-helper。commands 声明可调用方法；字段 id 要与 Python 参数一致；actions.command 必须出现在 commands 中。

```
{
  "$schema": "./sdk/plugin-manifest.schema.json",
  "sdkVersion": 1,
  "id": "community.hello",
  "name": "Hello 工具",
  "description": "一个无需编写前端代码的 Python 插件示例。",
  "version": "0.1.0",
  "author": "Community",
  "category": "示例",
  "icon": "terminal",
  "color": "blue",
  "permissions": [],
  "commands": [
    "greet"
  ],
  "ui": {
    "surface": "form",
    "fields": [
      {
        "id": "name",
        "label": "姓名",
        "type": "text",
        "default": "开发者",
        "required": true
      }
    ],
    "actions": [
      {
        "command": "greet",
        "label": "打个招呼",
        "variant": "primary"
      }
    ]
  },
  "ai": {
    "tools": [
      {
        "name": "greet",
        "command": "greet",
        "description": "生成一条问候语。",
        "readOnly": true,
        "parameters": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string",
              "minLength": 1,
              "maxLength": 80
            }
          },
          "required": [
            "name"
          ],
          "additionalProperties": false
        }
      }
    ]
  }
}
```

ui.surface=form 使用 Cove 的原生表单与结果面板。字段可使用 text、password、number、select。密码字段声明 secret:true，不放默认密码。ai.tools 是 MCP 契约；表单参数和工具参数都要与同一个方法保持一致。每次改完清单，运行 python dev.py，先确认可以通过校验。

## 3. 实现 Python 功能

只写功能，不用复制一套界面。

```
from toolbench.sdk import Plugin


class Tool(Plugin):
    def greet(self, name="开发者"):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("姓名需要 1–80 个字符")
        return {"message": f"你好，{name.strip()}！"}
```

Tool 必须继承 Plugin。方法名与清单一致，返回 JSON 可序列化的数据。不要在结果中放 API Key、密码或私钥。数据文件保存在 self.context.data_dir，不能写回插件源码目录。用 close() 释放线程、网络连接和文件句柄。

```
python dev.py greet name=Cove
python dev.py greet name=
```

第一条得到正常问候，第二条应报“姓名需要 1–80 个字符”。失败输入也必须有明确结果。耗时任务应及时返回并用 context.emit 或 context.status 发送状态，避免阻塞界面。

## 4. 让 AI 客户端使用插件

同一份命令，支持 Cove 与 DSH。

示例的 ai.tools 已把 greet 声明为只读 MCP 工具。parameters 使用 JSON Schema，并关闭 additionalProperties；可接受参数必须与方法签名一致。只读工具不会改变外部状态，但仍可能读取敏感数据。发包、执行命令和修改文件等行为必须 readOnly:false，Cove 会完整展示非秘密参数并等待单次确认；被遮盖的字段会明确标记，批准后仍使用原始值执行。

在 Cove 安装插件后，在左侧“智能体工具”勾选你的插件并保存授权，再从“工作台 → MCP 连接”接入客户端。让客户端调用问候工具并传入 name=Cove。你应同时在客户端看到问候结果，在 Cove 的调用记录中看到真实执行。

```
python -m pip install -r requirements-dev.txt
python setup_dsh.py
```

第二条命令生成包含当前绝对路径的 cove.dsh.yml，并打印 dsh web --patch 命令。运行打印的命令，即可由 DeepSeek Harness 通过官方 dsh-mcp-client 加载同一插件。独立模式仅公开只读工具；需要当前工具会话或写操作确认时，在 Cove 的 MCP 页面连接 DSH。

## 5. 测试、打包与安装

验证产物，而不只验证源码。

```
python dev.py greet name=Cove
python package.py
```

exports 文件夹会生成 .cove-plugin 和 -dsh.zip 两种产物。Cove 包包含业务代码和资源，排除 SDK、虚拟环境、用户数据和开发脚本。打开 Cove → 插件 → 导入插件，选择 .cove-plugin，核对来源并导入，再运行一次。

解压 -dsh.zip，在新的目录执行 python -m pip install -r requirements.txt，再执行 python setup_dsh.py，按输出运行 DSH。不要把开发目录中的 .local 或凭据复制给其他人。包需要额外依赖时，在 requirements.txt 中声明，并提供 vendor 或独立 Python 环境。

验收四件事：正常输入成功；错误输入给出清晰错误；MCP 未授权时不可见；重新打开 Cove 后插件仍可用。测试写工具还必须确认拒绝操作不会改变目标状态。

## 6. 维护与下一步

让插件可以长期迭代。

更新保留 id、提升 version。不要随意改 MCP 工具名或参数含义，否则旧客户端和会话会失效。新增参数优先提供默认值；数据升级要可恢复。安装升级只替换代码，用户数据保留。

终端部件通过清单绑定输入、输出、尺寸和连接状态，并由插件实现 close()。需要适配 DSH 时优先复用 ai.tools 与独立 MCP 出口；在真实任务证明有必要后，再编写 Cordis 原生服务适配层。

发布前在干净目录安装实际产物，记录 Python 版本、依赖和兼容的 Cove / DSH 版本。随包提供功能说明、示例输入、权限说明和常见失败的处理方式。
