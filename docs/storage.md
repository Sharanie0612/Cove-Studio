# Data location / 数据位置

Cove 0.13.2 stores desktop data in `<installation>/data` by default. Choosing `D:\Apps\Cove` therefore places installed plugins, connection profiles, diagnostics, client-configuration backups and the WebView profile/cache under `D:\Apps\Cove\data`. User-added plugin projects remain in `<installation>/plugins`. Data is outside versioned runtime folders, so upgrading or uninstalling program files preserves it.

The installer shows this path on its location page. Settings shows the actual active data directory, including any deferred migration. Explicit `TOOLBENCH_DATA_DIR` and programmatic `Host(data_dir=...)` take precedence; source development keeps the project-local `.local` directory. An unwritable installation does not silently create a new profile on C:.

## Existing installations

On first desktop startup, Cove can copy the previous `%LOCALAPPDATA%\Cove` profile into the selected installation's data directory. It checks for active older desktops/plugin workers or a live bridge, locks migration, checks file hashes before and after copying, and publishes the staged copy only after verification. An active legacy desktop/worker blocks the new startup with a translated notice instead of replacing its MCP bridge. Other copy failures, changed files or unsafe linked paths defer migration: Cove continues with the original profile only when no legacy instance is active, and Settings explains the pending destination. Empty folders are preserved. A nonempty destination is never merged or overwritten.

From 0.13.4, the stable launcher is recognized by its owned routing records and is excluded from desktop data ownership: it only waits for the real desktop. Desktop defaults are resolved from runtime version metadata, while explicit data overrides still take precedence. An inaccessible unrelated Python process does not imply a legacy Cove worker; known Cove processes and interpreters within the legacy tree remain conservatively protected. Regression checks include a real stable-entry first launch with a legacy draft and no data override.

Only host-owned interpreter paths located inside the old data tree are relocated. External interpreters, client configuration files and paths saved by a plugin or user keep their explicit values. The old profile stays as a backup; **this version does not automatically reclaim that existing C: space**. New writes use the selected destination after migration. Another installation does not reimport this already-claimed, potentially stale backup.

A small bridge descriptor and authorized-tool cache remain at the old path for already-running MCP adapters. They retain normal authorization, revocation and disconnect behavior. This compatibility metadata is not a second plugin/cache store. Do not delete the old directory while an older Cove installation or its adapter still relies on it.

## Temporary files and limits

The desktop's temporary directory and common plugin temporary/Python cache locations are scoped to its data directory. Worker `TEMP`, `TMP`, `TMPDIR`, `XDG_CACHE_HOME` and `PIP_CACHE_DIR` point there; new bytecode files are disabled. This only changes Cove process environments, not Windows settings. After a location is chosen, installation-progress scratch files and the silent engine’s extraction TEMP/TMP use a private temporary folder on that drive.

The installer's initial extraction and temporary WebView may still use the system TEMP directory before the user selects a destination; they are transient. Windows/WebView2 system components, desktop shortcuts, registry entries, third-party client configuration files and external Python installations keep their system/application-defined locations. Plugins remain trusted code and can choose other paths; this policy is not a filesystem sandbox. Standalone portable MCP plugins keep their own `--data` contract.

## 简体中文

安装版默认把主要长期数据保存在“安装目录\data”，插件导入、连接、日志、备份、浏览器缓存以及 Cove 子进程的常见临时文件随之放到用户选择的盘。首次迁移经过校验，原数据保留备份；旧实例仍在使用时提示正常退出后重试；无活动旧实例时的复制失败会继续使用原目录，并在设置中显示待迁移位置。已有数据不会因升级或卸载程序被删除。旧目录的备份暂不自动清理，因此不能把迁移成功表述为已经释放了原有 C 盘占用。
