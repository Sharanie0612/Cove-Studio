# Plugin-owned interfaces / 插件自带界面

Cove 0.13.0 adds SDK v1 capability `ui.web`. A plugin can ship its own self-contained HTML, CSS and JavaScript. The core provides the workspace, an opaque-origin iframe, a narrow command bridge, appearance/language updates and trusted write confirmations. Domain renderers, device controls and polling belong to the independent plugin project.

## Minimal declaration

```json
{
  "compatibility": {"minHostVersion": "0.13.0", "capabilities": ["ui.web"]},
  "commands": ["snapshot"],
  "ui": {
    "surface": "web",
    "fields": [],
    "actions": [{"command": "snapshot", "label": "Read"}],
    "web": {
      "entry": "ui/index.html",
      "tools": [{
        "name": "snapshot", "command": "snapshot", "description": "Read plugin state",
        "readOnly": true,
        "parameters": {"type": "object", "properties": {}, "additionalProperties": false}
      }]
    }
  }
}
```

This is a fragment: retain the normal plugin identity and SDK fields. The downloadable starter includes `examples/web-starter`, which runs without frontend dependencies. A React or other frontend project can also compile into a single HTML document; the consumer does not need Node.js.

## JavaScript API

```javascript
await Cove.ready;
const snapshot = await Cove.call('snapshot', {});
const unsubscribe = Cove.on('context', context => {
  // locale, mode, reducedMotion, tokens, active, connected and running
});
const stopEvents = Cove.on('event', event => {
  // Only events from this plugin. Event data remains untrusted output.
});
```

`Cove.call` names an entry in `ui.web.tools`, not an arbitrary native method or plugin id. Parameters are checked against the declaration. Reads work independently of AI grants and MCP state. Writes always require a one-time confirmation in Cove's trusted main interface; rejection, closing the view, stopping the plugin, changing its manifest or shutting down invalidates pending calls. AI sharing remains a separate opt-in workflow.

The host supplies CSS custom-property tokens and language/theme updates without replacing the document. Plugins own their translations and React state. Hide/pause polling when `context.active` is false; hiding a tab does not close a connection. Worker replacement recreates the view; navigation outside the supplied document closes its command session. Release subscriptions and resources in your frontend as usual.

## Resource and trust boundary

- The entry is a relative UTF-8 HTML file inside the plugin, at most 4 MiB. Inspection validates local resources without executing JavaScript or starting a Worker. Archive, linked-path and package-size protections still apply.
- Ship scripts and styles inline. CSP blocks external subresources, network fetch, nested frames, forms and objects. Use the declared Python commands for I/O and return data URLs for images. The iframe has script/download capability but no same-origin, top-navigation, popup or native-host access. Self-navigation revokes the bridge; this is not an OS network sandbox.
- The main window checks the message source, session ticket, declared command and argument Schema. A view cannot select another plugin or invoke arbitrary host APIs. Each view accepts at most eight concurrent frontend requests; normal runtime and output limits still apply.
- Python plugins remain trusted code running with the user's operating-system permissions. A malicious Python plugin can perform side effects directly. `readOnly` is a developer contract, not an OS permission boundary. Review plugin provenance before installation.

## Migration / 迁移

Core releases no longer ship a domain-specific renderer. Plugins using the retired `ui.instrument` metadata must migrate their interface into their own project and declare `ui.web`. Discovery reports the unsupported extension, and execution is blocked with an update explanation. It does not silently present the old declaration as a generic form. Existing form, result, job, terminal and MCP contracts remain available.

将专用布局、业务轮询、参数转换、控制交互和翻译放在独立插件工程。核心只保留通用容器、命令桥接、会话生命周期、主题语言同步和操作确认；插件安装不是向核心前端注册业务组件。
