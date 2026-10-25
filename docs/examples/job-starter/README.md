# Background job example / 后台任务示例

Requires Cove 0.11.0+ and Python 3.11+. No dependencies, hardware, network or file writes are needed by the example task.

From a Cove source checkout:

```powershell
.venv\Scripts\python.exe docs/examples/job-starter/dev.py
.venv\Scripts\python.exe scripts/package_plugin.py docs/examples/job-starter
```

Import the resulting `.cove-plugin` through the Plugins page, open the card and run the task. Increase the batch count to try **Stop**. The developer starter downloaded from Cove includes this independent project at `examples/job-starter`, with its SDK and packaging scripts. Run `python -S dev.py` inside that folder.

`BackgroundJob(context)` manages one current task per plugin. `start(callback, total=..., message=...)` promptly returns a running snapshot. The callback receives `JobControl`: use `update(completed=..., message=...)` for progress, `check_cancelled()` between work units and `wait(seconds)` for an interruptible wait. Return a JSON object with result fields such as `message`, `files`, `warnings`, or `instructions`; an optional `state: "partial"` reports partial completion. Omit `total` when it is unknown. `revision` is managed by the helper and increases within this worker lifetime.

Bind `snapshot()` and `cancel()` through the existing `ui.job` manifest entry. Events remain `job` with `data.result`, plus `activity` with `active: true/false`. A cancellation request keeps the state `running` and the activity guard active until the callback actually exits. `cancel()` is idempotent. `close(timeout=1)` requests cancellation and waits for a bounded duration; call it from `Tool.close()`.

需要 Cove 0.11.0+、Python 3.11+。示例只在内存中处理文本，不访问网络或硬件，也不生成文件。可在源码工程直接运行上面的命令；独立开发时，从 Cove 下载完整示例，在自带的 `examples/job-starter` 目录运行 `python -S dev.py`。该目录包含独立 SDK 和打包脚本，可单独复制到其他位置。

每个插件使用一个 `BackgroundJob`。它负责互斥、快照、递增 revision、进度事件和活动保护；业务代码只需实现回调。在工作单元之间检查取消，真实网络或设备调用仍须设置超时。取消不是强制中断：只有回调退出后才变成 `cancelled` 并解除活动保护。`close()` 等待超时也不会谎报工作已经停止。

此 helper 不保存任务历史、不回滚业务写入、不终止外部进程。需要这些行为时由插件显式实现。普通异常仅展示异常类型，避免泄露内部参数；需要给用户具体提示时使用 `CommandError`。请勿在 `CommandError` 中放入秘密值。旧 SDK v1 插件无需迁移，也不需要添加新的必需能力。
