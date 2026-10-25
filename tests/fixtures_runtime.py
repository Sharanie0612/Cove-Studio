"""In-memory contract fixtures; never bundled or installed as application tools."""
import json
from pathlib import Path
APPROVAL = 'test.approval'
TERMINAL = 'test.terminal'

def write_approval_fixture(folder):
    """A disposable worker that records exactly what an approval executes."""
    folder.mkdir(parents=True)
    manifest = {
        'sdkVersion': 1, 'id': APPROVAL, 'name': '参数审阅测试', 'version': '1.0.0',
        'author': 'Cove tests', 'description': 'Disposable approval review fixture',
        'category': '测试', 'icon': 'terminal', 'color': 'blue', 'permissions': [],
        'commands': ['record', 'snapshot'],
        'ui': {'surface': 'form', 'fields': [], 'actions': [{'command': 'record', 'label': '记录参数'}]},
        'ai': {'tools': [{'name': 'record', 'command': 'record', 'description': '记录本次审阅的参数',
                         'readOnly': False, 'parameters': {'type': 'object', 'properties': {
                             'document': {'type': 'string'}, 'steps': {'type': 'array'},
                             'options': {'type': 'object'}},
                             'required': ['document', 'steps', 'options'], 'additionalProperties': False}}]}}
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (folder / 'plugin.py').write_text(
        'from toolbench.sdk import Plugin\n'
        'class Tool(Plugin):\n'
        ' def __init__(self,context):\n  super().__init__(context)\n  self.receipts=[]\n'
        ' def record(self,document,steps,options):\n'
        '  self.receipts.append({"document":document,"steps":steps,"options":options})\n'
        '  return {"recorded":len(self.receipts)}\n'
        ' def snapshot(self): return self.receipts\n', encoding='utf-8')

def write_terminal_fixture(folder):
    folder.mkdir(parents=True, exist_ok=True)
    fields = [
        {'id':'host','label':'测试地址','type':'text','required':True},
        {'id':'username','label':'测试用户名','type':'text','required':True},
        {'id':'password','label':'测试秘密','type':'password','secret':True},
        {'id':'port','label':'端口','type':'number','default':0,'min':0,'advanced':True},
        {'id':'auth','label':'认证方式','type':'select','default':'password','advanced':True,
         'options':[{'value':'password','label':'测试秘密'}]},
    ]
    manifest = {'sdkVersion':1,'id':TERMINAL,'name':'终端夹具','description':'内存中的部件契约测试，不连接外部服务。',
        'version':'1.0.0','author':'Cove tests','category':'测试','icon':'terminal','permissions':[],
        'commands':['connect','disconnect','write','resize','snapshot','apply','list_profiles','scan_profiles','save_profile','delete_profile'],
        'ui':{'surface':'terminal','fields':fields,'connection':{'connect':'connect','disconnect':'disconnect'},
              'terminal':{'write':'write','resize':'resize','dataEvent':'terminal'},
              'profiles':{'list':'list_profiles','scan':'scan_profiles','save':'save_profile','remove':'delete_profile'},
              'actions':[{'command':'connect','label':'连接测试','variant':'primary'}],
              'confirmations':[{'code':'CONFIRM_TEST_SESSION','title':'确认测试会话','description':'核对测试标记后继续。',
                'confirmLabel':'确认并连接','details':[{'key':'fingerprint','label':'测试标记'}],
                'payload':{'trust_fingerprint':{'fromDetail':'fingerprint'}}}]},
        'ai':{'tools':[
          {'name':'read','command':'snapshot','description':'Read fixture state','readOnly':True,'parameters':{'type':'object','properties':{},'additionalProperties':False}},
          {'name':'apply','command':'apply','description':'Record fixture value','readOnly':False,'parameters':{'type':'object','properties':{'value':{'type':'string'}},'required':['value'],'additionalProperties':False}}]}}
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (folder / 'plugin.py').write_text(TERMINAL_SOURCE, encoding='utf-8')
    return manifest

TERMINAL_SOURCE = r'''
from toolbench.sdk import Plugin
class Tool(Plugin):
 def __init__(self, context):
  super().__init__(context)
  self.connected=False;self.profiles=[];self.records=[]
 def connect(self, host='', port=0, username='', password='', auth='password', trust_fingerprint='', profile_id='', **kwargs):
  if trust_fingerprint != 'fixture':
   from toolbench.sdk import CommandError
   raise CommandError('Confirm fixture session','CONFIRM_TEST_SESSION',{'fingerprint':'fixture'})
  self.connected=True;self.context.status(True,'Connected');return self.snapshot()
 def disconnect(self):
  self.connected=False;self.context.status(False,'Disconnected');return self.snapshot()
 def snapshot(self): return {'connected':self.connected,'records':self.records}
 def apply(self,value): self.records.append(value);return {'recorded':value}
 def write(self,data): self.context.emit('terminal',text=data);return {'written':len(data)}
 def resize(self,cols=80,rows=24): return {'cols':cols,'rows':rows}
 def list_profiles(self): return {'profiles':self.profiles,'issues':[]}
 def scan_profiles(self): return self.list_profiles()
 def save_profile(self,profile):
  import uuid
  saved={'id':profile.get('id') or uuid.uuid4().hex,'name':profile.get('name') or 'Fixture','values':{k:v for k,v in profile.get('values',{}).items() if k!='password'}}
  self.profiles=[p for p in self.profiles if p['id']!=saved['id']]+[saved];return saved
 def delete_profile(self,profile_id,**kwargs):
  self.profiles=[p for p in self.profiles if p['id']!=profile_id];return {'removed':True}
 def close(self): self.connected=False
'''
