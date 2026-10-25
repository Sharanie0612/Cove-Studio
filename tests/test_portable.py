import asyncio
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import yaml

from toolbench.distribution import portable_archive
from toolbench.host import Host, ROOT


async def official_client(command, args, expected):
    params = StdioServerParameters(command=command, args=args)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=12)) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            if len(tools.tools) != expected:
                raise AssertionError(tools)
            tool = tools.tools[0]
            arguments = {'name':'Cove 你好'} if tool.name.endswith('_greet') else {}
            result = await session.call_tool(tool.name, arguments)
            if result.isError:
                raise AssertionError(result)
            return initialized.serverInfo.name, json.loads(result.content[0].text)


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT)
        self.root=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_downloaded_starter_builds_both_artifacts_and_dsh_uses_same_code(self):
        host=Host(data_dir=self.root/'data')
        try:
            with zipfile.ZipFile(io.BytesIO(host._starter_bytes())) as archive:
                archive.extractall(self.root/'starter')
        finally:host.close()
        project=self.root/'starter/cove-plugin-starter'
        result=subprocess.run([sys.executable,'-S',str(project/'dev.py'),'greet','name=Cove'],cwd=project,capture_output=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['message'],'你好，Cove！')
        result=subprocess.run([sys.executable,'-S',str(project/'package.py')],cwd=project,capture_output=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(list((project/'exports').glob('*.cove-plugin'))),1)
        archive=next((project/'exports').glob('*-dsh.zip'))
        with zipfile.ZipFile(archive) as source: source.extractall(self.root/'portable')
        portable=self.root/'portable'
        self.assertEqual((portable/'plugin/plugin.py').read_bytes(),(project/'plugin.py').read_bytes())
        setup=subprocess.run([sys.executable,str(portable/'setup_dsh.py')],cwd=portable,capture_output=True,encoding='utf-8',timeout=10)
        self.assertEqual(setup.returncode,0,setup.stderr)
        patch=yaml.safe_load((portable/'cove.dsh.yml').read_text(encoding='utf-8'))
        config=patch[0]['insert'][0]['config']
        self.assertEqual(patch[0]['insert'][0]['name'],'@deepseek-ai/dsh-mcp-client')
        name,result=asyncio.run(official_client(config['command'],[*config['args'],'--data',str(self.root/'portable-data')],1))
        self.assertEqual(name,'Cove')
        self.assertEqual(result['result']['message'],'你好，Cove 你好！')


