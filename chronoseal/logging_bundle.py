from pathlib import Path
import json, platform, sys, os, subprocess, threading, datetime, hashlib, traceback

# This stdlib build exposes no ``windowsHide``; a hidden child needs CREATE_NO_WINDOW.
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0

class SessionLogger:
    def __init__(self, base_dir, ui_callback=None):
        ts=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.dir=Path(base_dir)/f'session_{ts}'
        self.dir.mkdir(parents=True,exist_ok=False)
        self.logfile=self.dir/'chronoseal.log'; self.commands=self.dir/'commands'; self.commands.mkdir()
        self.ui=ui_callback; self.lock=threading.Lock(); self.seq=0
        self.write('ChronoSeal session started')
    def write(self,msg,level='INFO'):
        line=f"{datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')} [{level}] {msg}"
        with self.lock:
            with self.logfile.open('a',encoding='utf-8') as f:f.write(line+'\n')
        if self.ui:self.ui(line)
    def command(self,args,cwd,returncode,stdout,stderr):
        with self.lock:self.seq+=1; n=self.seq
        rec={'args':[str(x) for x in args],'cwd':str(cwd),'returncode':returncode,'stdout':stdout,'stderr':stderr}
        (self.commands/f'{n:03d}.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
    def snapshot(self,root,config=None):
        def ver(cmd):
            try:
                q=subprocess.run(cmd,text=True,capture_output=True,timeout=10,
                                 stdin=subprocess.DEVNULL,creationflags=NO_WINDOW)
            except (OSError,subprocess.SubprocessError) as e:return f'UNAVAILABLE: {e}'
            # One probe per tool: tools print their version to stdout or stderr.
            return (q.stdout or '').strip() or (q.stderr or '').strip() or f'exit code {q.returncode}'
        tools=(config or {}).get('tools',{}); node=tools.get('node') or 'node'; ssl=tools.get('openssl') or 'openssl'; data={'time':datetime.datetime.now().astimezone().isoformat(),'platform':platform.platform(),'python':sys.version,'executable':sys.executable,'cwd':os.getcwd(),'app_root':str(root),'configured_tools':{'node':node,'openssl':ssl},'node':ver([node,'--version']),'openssl':ver([ssl,'version'])}
        (self.dir/'environment.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        return data
    def error(self,exc):
        (self.dir/'error.txt').write_text(''.join(traceback.format_exception(type(exc),exc,exc.__traceback__)),encoding='utf-8')
        self.write(f'{type(exc).__name__}: {exc}','ERROR')

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
