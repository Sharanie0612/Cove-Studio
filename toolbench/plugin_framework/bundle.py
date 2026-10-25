"""The SDK file inventory shared by source, frozen and portable exports."""
SDK_FILES = (
    '__init__.py', 'sdk.py', 'manifest.py', 'contracts.py', 'packages.py',
    'distribution.py', 'protocol.py', 'plugin_mcp.py', 'worker.py',
)


def sdk_files(root):
    return [*(root / name for name in SDK_FILES),
            *sorted((root / 'plugin_framework').glob('*.py'))]
