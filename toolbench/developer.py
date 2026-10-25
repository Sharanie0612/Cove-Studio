"""Export previews, safe package saves and a self-contained developer starter."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import time
import uuid
import zipfile
from toolbench.packages import build_package, package_filename, write_bytes_atomic
from toolbench.dialogs import PLUGIN_SAVE_FILTERS, ZIP_FILTERS

class DeveloperApi:
    def export_dsh_plugin(self, plugin_id):
        try:
            import webview
            from toolbench.distribution import portable_archive
            if plugin_id not in self.plugins:
                raise ValueError('插件不存在')
            folder, manifest = self.plugins[plugin_id]
            content = portable_archive(folder)
            name = manifest['id'] + '-' + manifest['version'] + '-dsh.zip'
            chosen = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=name, file_types=ZIP_FILTERS)
            if not chosen:
                return {'ok': True, 'result': None}
            destination = Path(chosen[0])
            if destination.suffix.lower() != '.zip':
                destination = Path(str(destination) + '.zip')
            write_bytes_atomic(destination, content)
            return {'ok': True, 'result': {'path': str(destination)}}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def _prepare_export(self, folder: Path):
        package = build_package(folder)
        ticket = uuid.uuid4().hex
        self._export_tickets = {ticket: {'content': package['content'], 'time': time.monotonic(), 'name': package_filename(package['manifest'])}}
        return {'ticket': ticket, 'manifest': package['manifest'], 'fileCount': package['fileCount'], 'sizeBytes': len(package['content']),
                'expandedBytes': package['expandedBytes'], 'files': list(package['files']), 'excluded': package['excluded'],
                'sha256': hashlib.sha256(package['content']).hexdigest(), 'fileName': self._export_tickets[ticket]['name']}

    def prepare_plugin_export(self, plugin_id: str = ''):
        try:
            if plugin_id:
                if plugin_id not in self.plugins: raise ValueError('插件不存在')
                folder = self.plugins[plugin_id][0]
            else:
                import webview
                chosen = self._window.create_file_dialog(webview.FileDialog.FOLDER)
                if not chosen: return {'ok': True, 'result': None}
                folder = Path(chosen[0])
            return {'ok': True, 'result': self._prepare_export(folder)}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def _save_export(self, ticket: str, destination: Path):
        package = self._export_tickets.get(ticket)
        if not package or time.monotonic() - package['time'] > 600:
            raise ValueError('导出预览已过期，请重新打包')
        destination = Path(destination)
        if destination.suffix.lower() != '.cove-plugin': destination = Path(str(destination) + '.cove-plugin')
        write_bytes_atomic(destination, package['content'])
        self._export_tickets.pop(ticket, None)
        return {'path': str(destination), 'sizeBytes': len(package['content'])}

    def save_plugin_export(self, ticket: str):
        try:
            package = self._export_tickets.get(ticket)
            if not package: raise ValueError('导出预览已失效，请重新打包')
            import webview
            chosen = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=package['name'], file_types=PLUGIN_SAVE_FILTERS)
            if not chosen: return {'ok': True, 'result': None}
            return {'ok': True, 'result': self._save_export(ticket, Path(chosen[0]))}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def _starter_bytes(self):
        from toolbench.host import ROOT
        sdk = ROOT / 'sdk-runtime/toolbench' if (ROOT / 'sdk-runtime/toolbench').is_dir() else ROOT / 'toolbench'
        example = ROOT / 'docs/templates/starter'
        files = {p.name: p.read_bytes() for p in example.iterdir() if p.is_file()}
        from toolbench.plugin_framework.bundle import sdk_files
        for source in sdk_files(sdk):
            files['sdk/toolbench/' + source.relative_to(sdk).as_posix()] = source.read_bytes()
        files['sdk/plugin-manifest.schema.json'] = (ROOT / 'schemas/plugin-manifest.schema.json').read_bytes()
        files['sdk/LICENSE'] = (ROOT / 'LICENSE').read_bytes()
        # Each example is independently runnable after extraction, including with -S.
        # Share the inventory, not a runtime import of another example's business code.
        common = {name: content for name, content in files.items()
                  if name.startswith('sdk/') or name in {
                      'dev.py', 'doctor.py', 'package.py', 'serve.py', 'setup_dsh.py',
                      'requirements-dev.txt', '.coveignore'}}
        examples = ROOT / 'docs/examples'
        if examples.is_dir():
            for project in sorted(examples.iterdir()):
                if not project.is_dir() or not (project / 'manifest.json').is_file():
                    continue
                prefix = 'examples/' + project.name + '/'
                files.update({prefix + name: content for name, content in common.items()})
                files.update({prefix + p.relative_to(project).as_posix(): p.read_bytes()
                              for p in project.rglob('*') if p.is_file()
                              and not any(part.startswith('.') or part in {'__pycache__', 'node_modules'}
                                          for part in p.relative_to(project).parts)})
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items(): archive.writestr('cove-plugin-starter/' + name, content)
        return buffer.getvalue()

    def export_plugin_starter(self):
        try:
            import webview
            chosen = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename='cove-plugin-starter.zip', file_types=ZIP_FILTERS)
            if not chosen: return {'ok': True, 'result': None}
            destination = Path(chosen[0])
            if destination.suffix.lower() != '.zip': destination = Path(str(destination) + '.zip')
            write_bytes_atomic(destination, self._starter_bytes())
            return {'ok': True, 'result': {'path': str(destination)}}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}
