"""Shared frozen entry point; the worker executable has real pipe handles."""
import sys


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--installer-ui':
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        from toolbench.setup_ui import main
        sys.exit(main())
    elif len(sys.argv) > 1 and sys.argv[1] == '--mcp':
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        from toolbench.mcp_bridge import main
        main()
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "--plugin-mcp":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        from toolbench.plugin_mcp import main
        main()
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "--maintenance":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        from toolbench.maintenance import main
        sys.exit(main())
    elif len(sys.argv) > 1 and sys.argv[1] == "--worker":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        from toolbench.worker import main
    elif len(sys.argv) > 1 and sys.argv[1] == "--smoke":
        import json
        from pathlib import Path
        from toolbench.host import Host
        host = Host()
        result = {"catalog": host.catalog()}
        from toolbench.host import ROOT
        from toolbench.bridge import DesktopBridge, API_METHODS
        preview = host._prepare_export(ROOT / 'docs/templates/starter')
        starter = host._starter_bytes()
        starter_path = Path(sys.argv[2]).with_name('packaged-plugin-starter.zip')
        starter_path.write_bytes(starter)
        result['developer'] = {'exportFileCount': preview['fileCount'], 'starterBytes': len(starter),
                               'starterPath': str(starter_path),
                               'bridgeMethods': [name for name in API_METHODS if callable(getattr(DesktopBridge(host), name))]}
        host.close()
        Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        sys.exit(0)
    else:
        from toolbench.__main__ import main
    main()
