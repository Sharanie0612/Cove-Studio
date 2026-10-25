from toolbench.plugin_framework.policy import POLICY
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
import yaml
import time
from unittest.mock import patch
from toolbench.client_backups import MAX_PER_CLIENT, RETENTION_DAYS

from toolbench.connections import Connections
from toolbench.harness import client_profiles


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.connections = Connections(self.root / 'data', self.root / 'home')
        self.profiles = {item['id']:item for item in client_profiles(r'C:\Cove\Cove-worker.exe',['--mcp','--connection',r'C:\Cove\data\mcp-bridge.json'],{})}

    def tearDown(self):
        self.temp.cleanup()

    def test_codex_preserves_settings_comments_and_exact_undo(self):
        path=self.connections.path('codex');path.parent.mkdir(parents=True)
        original='# personal configuration\nmodel = "my-model"\n\n[mcp_servers.other]\ncommand="other" # keep this\n'
        path.write_text(original,encoding='utf-8')
        result=self.connections.install('codex',self.profiles['codex'])
        text=path.read_text(encoding='utf-8');parsed=tomllib.loads(text)
        self.assertEqual(parsed['model'],'my-model')
        self.assertEqual(parsed['mcp_servers']['other']['command'],'other')
        self.assertIn('# keep this',text)
        self.assertEqual(parsed['mcp_servers']['cove']['tool_timeout_sec'],int(POLICY.client))
        self.assertFalse(self.connections.install('codex',self.profiles['codex'])['changed'])
        self.connections.restore(result['backupId'])
        self.assertEqual(path.read_text(encoding='utf-8'),original)

    def test_connection_pause_survives_maintenance_and_preserves_client_config(self):
        self.connections.install('codex', self.profiles['codex'])
        path = self.connections.path('codex')
        before = path.read_bytes()
        self.connections.set_connection('codex', False)
        restarted = Connections(self.root / 'data', self.root / 'home')
        restarted.maintain(list(self.profiles.values()))
        self.assertFalse(restarted.client_allowed('codex'))
        self.assertTrue(restarted.client_allowed('cursor'))
        self.assertEqual(path.read_bytes(), before)
        client = restarted.catalog(list(self.profiles.values()), ['codex'])[0]
        self.assertTrue(client['paused'])
        self.assertTrue(client['configured'])
        self.assertFalse(client['connected'])
        restarted.set_connection('codex', True)
        self.assertTrue(restarted.client_allowed('codex'))
        self.assertEqual(path.read_bytes(), before)
        for client, enabled in [('invalid', True), ('codex', 'false')]:
            with self.assertRaises(ValueError): restarted.set_connection(client, enabled)

    def test_json_clients_preserve_other_servers_and_settings(self):
        for client in ('claude-code','cursor','workbuddy','zcode'):
            with self.subTest(client=client):
                path=self.connections.path(client);path.parent.mkdir(parents=True,exist_ok=True)
                original={"theme":"dark","mcpServers":{"other":{"command":"other"}},"mcp":{"servers":{"other":{"command":"other"}}}}
                path.write_text(json.dumps(original),encoding='utf-8')
                result=self.connections.install(client,self.profiles[client])
                parsed=json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(parsed['theme'],'dark')
                servers=parsed['mcp']['servers'] if client=='zcode' else parsed['mcpServers']
                self.assertEqual(servers['other']['command'],'other')
                self.assertEqual(servers['cove']['args'][-1],client)
                self.connections.restore(result['backupId'])
                self.assertEqual(json.loads(path.read_text(encoding='utf-8')),original)

    def test_dsh_preserves_js_tags_and_generates_real_patch(self):
        path=self.connections.path('deepseek-harness');path.parent.mkdir(parents=True)
        original="# existing DSH patch\n- insert:\n    - id: existing\n      name: '@example/tool'\n      config:\n        home: !!js process.cwd()\n"
        path.write_text(original,encoding='utf-8')
        result=self.connections.install('deepseek-harness',self.profiles['deepseek-harness'])
        text=path.read_text(encoding='utf-8')
        self.assertTrue(text.startswith(original.rstrip()))
        self.assertEqual(text.count('id: cove-mcp'),1)
        yaml.compose(text)
        self.assertFalse(self.connections.install('deepseek-harness',self.profiles['deepseek-harness'])['changed'])
        self.connections.restore(result['backupId'])
        self.assertEqual(path.read_text(encoding='utf-8'),original)

    def test_bad_config_and_concurrent_changes_are_not_overwritten(self):
        path=self.connections.path('cursor');path.parent.mkdir(parents=True)
        path.write_text('{ broken',encoding='utf-8')
        with self.assertRaises(Exception):self.connections.install('cursor',self.profiles['cursor'])
        self.assertEqual(path.read_text(encoding='utf-8'),'{ broken')
        path.write_text('{}',encoding='utf-8')
        result=self.connections.install('cursor',self.profiles['cursor'])
        path.write_text('{"changed":true}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'其他程序'):self.connections.restore(result['backupId'])
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')),{'changed':True})

    def test_new_file_undo_and_manual_client_do_not_touch_unrelated_paths(self):
        path=self.connections.path('claude-code')
        result=self.connections.install('claude-code',self.profiles['claude-code'])
        self.assertTrue(path.exists());self.connections.restore(result['backupId']);self.assertFalse(path.exists())
        with self.assertRaises(ValueError):self.connections.install('trae',self.profiles['trae'])
        with self.assertRaises(ValueError):self.connections.path('../../escape')

    def test_managed_upgrade_preserves_other_changes_and_undo_stops_repair(self):
        first = self.connections.install('codex', self.profiles['codex'])
        path = self.connections.path('codex')
        path.write_text('model="personal"\n' + path.read_text(encoding='utf-8'), encoding='utf-8')
        upgraded = client_profiles(r'C:\Cove\versions\0.8.2\Cove-worker.exe', ['--mcp', '--connection', r'C:\Cove\data\mcp-bridge.json'], {})
        restarted = Connections(self.root / 'data', self.root / 'home')
        restarted.maintain(upgraded)
        parsed = tomllib.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(parsed['model'], 'personal')
        self.assertIn('0.8.2', parsed['mcp_servers']['cove']['command'])
        self.assertTrue(restarted.catalog(upgraded)[0]['managed'])
        self.assertFalse(restarted.catalog(upgraded)[0]['needsRepair'])
        # Undo cannot erase intervening changes, even if Cove itself upgraded.
        with self.assertRaises(ValueError): restarted.restore(first['backupId'])

    def test_managed_does_not_reenable_user_disabled_or_replaced_entry(self):
        self.connections.install('codex', self.profiles['codex'])
        path = self.connections.path('codex')
        content = path.read_text(encoding='utf-8').replace('enabled = true', 'enabled = false')
        path.write_text(content, encoding='utf-8')
        self.connections.maintain(list(self.profiles.values()))
        self.assertEqual(path.read_text(encoding='utf-8'), content)
        self.assertTrue(self.connections.catalog(list(self.profiles.values()))[0]['needsRepair'])
        self.assertIn('暂停', self.connections.issues['codex'])

    def test_opt_out_and_undo_persist_across_restart(self):
        result = self.connections.install('codex', self.profiles['codex'])
        self.connections.manage('codex', False)
        restarted = Connections(self.root / 'data', self.root / 'home')
        self.assertFalse(restarted.catalog(list(self.profiles.values()))[0]['managed'])
        restarted.maintain(client_profiles('new-command', [], {}))
        self.assertIn('Cove-worker.exe', self.connections.path('codex').read_text(encoding='utf-8'))
        restarted.restore(result['backupId'])
        restarted.maintain(list(self.profiles.values()))
        self.assertFalse(self.connections.path('codex').exists())

    def test_codex_keeps_client_tool_policies_on_explicit_repair(self):
        path = self.connections.path('codex'); path.parent.mkdir(parents=True)
        path.write_text('[mcp_servers.cove]\ncommand="old"\nenabled=false\ndefault_tools_approval_mode="prompt"\ndisabled_tools=["cove_write"]\n', encoding='utf-8')
        self.connections.install('codex', self.profiles['codex'])
        server = tomllib.loads(path.read_text(encoding='utf-8'))['mcp_servers']['cove']
        self.assertTrue(server['enabled'])
        self.assertEqual(server['default_tools_approval_mode'], 'prompt')
        self.assertEqual(server['disabled_tools'], ['cove_write'])

    def test_backups_are_bounded_per_client_and_latest_undo_is_exact(self):
        path = self.connections.path('cursor')
        path.parent.mkdir(parents=True)
        original = b'{"unrelatedKey":"private-test-value"}\r\n'
        path.write_bytes(original)
        profile = dict(self.profiles['cursor'])
        latest_before = original
        for index in range(MAX_PER_CLIENT + 3):
            latest_before = path.read_bytes()
            profile['server'] = {**profile['server'], 'command': f'candidate-{index}'}
            result = self.connections.install('cursor', profile)
        records = list(self.connections.data_dir.glob('*.json'))
        self.assertEqual(len(records), MAX_PER_CLIENT)
        self.connections.restore(result['backupId'])
        self.assertEqual(path.read_bytes(), latest_before)
        self.assertFalse(self.connections.backups.path(result['backupId']).exists())

    def test_retention_expires_known_backups_but_preserves_unrelated_files(self):
        result = self.connections.install('cursor', self.profiles['cursor'])
        record = self.connections.backups.read(result['backupId'])
        record['time'] = time.time() - (RETENTION_DAYS + 1) * 86400
        self.connections.backups.write(result['backupId'], record)
        unrelated = self.connections.data_dir / 'my-notes.json'
        unrelated.write_text('{"keep":true}')
        damaged = self.connections.data_dir / ('f' * 32 + '.json')
        damaged.write_text('not a valid backup')
        restarted = Connections(self.root / 'data', self.root / 'home')
        self.assertFalse(restarted.backups.path(result['backupId']).exists())
        self.assertTrue(unrelated.exists())
        self.assertTrue(damaged.exists())
        self.assertTrue(self.connections.path('cursor').exists())

    def test_racing_save_preserves_external_change_and_discards_unused_backup(self):
        path = self.connections.path('cursor')
        path.parent.mkdir(parents=True)
        path.write_text('{}')
        write_backup = self.connections.backups.write
        def concurrent_write(ticket, record):
            write_backup(ticket, record)
            path.write_text('{"external":true}')
        with patch.object(self.connections.backups, 'write', side_effect=concurrent_write):
            with self.assertRaisesRegex(ValueError, '发生变化'):
                self.connections.install('cursor', self.profiles['cursor'])
        self.assertEqual(path.read_text(), '{"external":true}')
        self.assertEqual(list(self.connections.data_dir.glob('*.json')), [])

    def test_oversize_configuration_is_rejected_before_backup(self):
        path = self.connections.path('cursor')
        path.parent.mkdir(parents=True)
        path.write_bytes(b' ' * 2_000_001)
        with self.assertRaisesRegex(ValueError, '过大'):
            self.connections.install('cursor', self.profiles['cursor'])
        self.assertFalse(self.connections.data_dir.exists())

    def test_merged_configuration_must_remain_small_enough_to_undo(self):
        path = self.connections.path('codex')
        path.parent.mkdir(parents=True)
        original = b'#' + b'x' * 1_999_998 + b'\n'
        path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, '合并后的配置过大'):
            self.connections.install('codex', self.profiles['codex'])
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(self.connections.data_dir.exists())

    def test_cleanup_failure_does_not_misreport_a_successful_save(self):
        from toolbench.client_backups import ClientBackups
        with patch.object(ClientBackups, 'prune', return_value=False):
            restarted = Connections(self.root / 'data', self.root / 'home')
            result = restarted.install('cursor', self.profiles['cursor'])
        self.assertTrue(result['changed'])
        self.assertTrue(restarted.catalog(list(self.profiles.values()))[0]['backupCleanupPending'])
        self.assertTrue(restarted.path('cursor').exists())
        restarted.restore(result['backupId'])
        self.assertFalse(restarted.path('cursor').exists())

    def test_inaccessible_legacy_backup_cleanup_is_best_effort(self):
        self.connections.data_dir.mkdir(parents=True)
        with patch('toolbench.client_backups.protect_private', side_effect=PermissionError('locked')):
            restarted = Connections(self.root / 'data', self.root / 'home')
        self.assertTrue(restarted.backup_cleanup_pending)

    def test_undo_succeeds_even_when_the_used_backup_is_temporarily_locked(self):
        path = self.connections.path('cursor')
        path.parent.mkdir(parents=True)
        original = b'{"personal":"keep"}\r\n'
        path.write_bytes(original)
        result = self.connections.install('cursor', self.profiles['cursor'])
        with patch.object(self.connections.backups, 'remove', side_effect=PermissionError('locked')):
            restored = self.connections.restore(result['backupId'])
        self.assertTrue(restored['restored'])
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(self.connections.backup_cleanup_pending)
        self.assertNotIn('cursor', self.connections._managed())
