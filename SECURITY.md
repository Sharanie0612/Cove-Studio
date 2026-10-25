# Security model

Cove trusts the local user account and plugins installed by that user. Separate processes and data folders provide lifecycle separation; they do not restrict operating-system permissions or isolate malicious processes running as the same user. Install only plugins whose source you trust.

- Package import inspects paths, sizes, manifests and immutable package bytes before extraction. It does not execute pip automatically.
- MCP clients connect through an authenticated loopback bridge. Plugin sharing is opt-in; writes require a one-time approval bound to the requested arguments. Approval review includes every non-secret argument without truncation; secret fields are explicitly marked as redacted and the original values are used when executing.
- The bridge token is stored locally and changes when a gateway starts. On Windows, private storage uses a protected owner/SYSTEM DACL; on other platforms it uses owner-only permissions. These controls do not authenticate individual applications running as the same user. All connected MCP clients currently share the selected plugin grants.
- Disabling MCP closes its gateway and cancels pending MCP operations while preserving business workers and saved grants.
- Client configuration is backed up byte-for-byte, including unrelated credentials present in the original file. Backups are access-controlled, not encrypted. Recognized Cove backups retain the latest five records per client for up to 30 days; maintenance runs on startup and after configuration changes, and a successful undo removes its record. Unrelated or malformed files are preserved. Cleanup failures retain records for a later retry and are shown in client details. Save/undo refuse to overwrite unrelated concurrent modifications.
- NDJSON readers bound allocation while reading: MCP input is limited to 128 KiB, and worker frames allow 16 MiB plus 64 KiB for the transport envelope. Limits count UTF-8 bytes, excluding line endings. An oversized frame terminates that transport session instead of executing a trailing fragment; raw rejected data is not written to diagnostics.
- Preview Windows executables are unsigned. A successful test or local malware scan is not a universal security guarantee.

## Reporting

Report potential vulnerabilities through [GitHub private vulnerability reporting](https://github.com/Sharanie0612/Cove-Studio/security/advisories/new). Avoid posting credentials, private hostnames, configuration files or a working exploit in a public issue. Ordinary bug reports should contain only sanitized reproduction steps and relevant versions.

Optional extensions and vendored libraries have their own provenance and licenses. See [publication preparation](docs/open-source.md).
