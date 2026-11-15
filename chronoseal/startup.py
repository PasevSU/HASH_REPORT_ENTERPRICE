from pathlib import Path
import os, shutil, subprocess, json, importlib.util, sys
from .settings import executable, node_version

MIN_NODE=(22,12,0)

def _run(cmd,cwd,timeout=180):
    p=subprocess.run(cmd,cwd=str(cwd),capture_output=True,text=True,timeout=timeout,
                     stdin=subprocess.DEVNULL,
                     creationflags=(subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
    return p.returncode,(p.stdout or '')+(p.stderr or '')

# Additive dependency guard: the legacy startup and stamping pathways remain intact.
# All installations target the interpreter that is running the GUI, not PATH's python.
PYTHON_REQUIREMENTS = {
    'fitz': 'PyMuPDF>=1.24',
    'pypdf': 'pypdf>=5',
    'reportlab': 'reportlab>=4',
    'cryptography': 'cryptography>=42',
}

def ensure_python_dependencies(base, auto_install=True, log=lambda s: None, allow_network=True):
    base = Path(base)
    result = {'interpreter': sys.executable, 'required': PYTHON_REQUIREMENTS,
              'before': {}, 'after': {}, 'actions': [], 'blockers': []}
    for module in PYTHON_REQUIREMENTS:
        result['before'][module] = importlib.util.find_spec(module) is not None
    missing = [module for module, ok in result['before'].items() if not ok]
    if missing and auto_install and not allow_network:
        # One repair policy for every entry point: an evidence tool must not pull
        # code from PyPI unless the operator explicitly opted into network repair.
        log('[STARTUP] Missing Python packages: ' + ', '.join(missing)
            + ' — automatic installation is disabled (repair.allow_network is false).')
    if missing and auto_install and allow_network:
        packages = [PYTHON_REQUIREMENTS[module] for module in missing]
        cmd = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
               '--no-input', '--only-binary=:all:', *packages]
        log('[STARTUP] Repairing Python packages: ' + ', '.join(missing))
        try:
            rc, output = _run(cmd, base, 300)
            result['actions'].append({'command': 'python -m pip install',
                                      'packages': packages, 'exit_code': rc,
                                      'output_tail': output[-2500:]})
            if rc != 0:
                result['blockers'].append('Python dependency repair failed: ' + ', '.join(missing))
        except (OSError, subprocess.TimeoutExpired) as exc:
            result['blockers'].append('Python dependency repair exception: ' + str(exc))
        importlib.invalidate_caches()
    for module in PYTHON_REQUIREMENTS:
        result['after'][module] = importlib.util.find_spec(module) is not None
        if not result['after'][module]:
            msg = 'Missing required Python module: ' + module
            if auto_install and not allow_network and not result['before'][module]:
                msg += (' — automatic installation is disabled (repair.allow_network is false); '
                        'run Install_Windows.bat')
            if msg not in result['blockers']: result['blockers'].append(msg)
    # Import in a separate process to detect native DLL and wheel ABI errors.
    if not result['blockers']:
        code = 'import fitz,pypdf,reportlab,cryptography; print("PYTHON_IMPORT_PASS")'
        try:
            rc, output = _run([sys.executable, '-c', code], base, 60)
            result['import_test'] = {'exit_code': rc, 'output_tail': output[-1200:]}
            if rc != 0: result['blockers'].append('Python native import verification failed')
        except (OSError, subprocess.TimeoutExpired) as exc:
            result['blockers'].append('Python native import verification exception: ' + str(exc))
    return result

def startup_check(base,cfg,auto_install=True,log=lambda s:None):
    base=Path(base); report={'schema':'chronoseal.startup/v1','checks':{},'actions':[],'blockers':[],'warnings':[]}
    node=executable('node',(cfg.get('tools') or {}).get('node'))
    ssl=executable('openssl',(cfg.get('tools') or {}).get('openssl'))
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm') or shutil.which('npm')
    report['checks']['python']=os.sys.executable
    repair_cfg = cfg.get('repair') or {}
    allow_network = bool(repair_cfg.get('allow_network', False))
    py=ensure_python_dependencies(base,auto_install,log,allow_network=allow_network)
    report['checks']['python_dependencies']=py
    report['blockers'].extend(py['blockers'])
    report['actions'].extend(py['actions'])
    report['checks']['node']=node
    report['checks']['npm']=npm
    report['checks']['openssl']=ssl
    if node:
        v=node_version(node); report['checks']['node_version']='.'.join(map(str,v)) if v else None
        if not v or v<MIN_NODE: report['blockers'].append('Node.js >=22.12.0 is required.')
        cfg.setdefault('tools',{})['node']=node
    else: report['blockers'].append('Node.js was not found. Install Node.js >=22.12.0, then restart ChronoSeal.')
    if ssl: cfg.setdefault('tools',{})['openssl']=ssl
    else: report['warnings'].append('OpenSSL was not found. RFC3161 stamping may work, but certificate diagnostics will be incomplete.')
    # Only attempt dependency repair when Node itself is usable.
    if node and not any('Node.js >=' in x for x in report['blockers']):
        from . import selfheal
        # One repair policy for every entry point: verify on disk, restore the
        # hash-pinned vendored copy offline, and only then consider the registry.
        if repair_cfg.get('enabled', True):
            state = selfheal.node_package_state(base)
            report['checks']['pdf_rfc3161_state_before'] = state['state']
            if state['state'] != 'OK':
                log('[STARTUP] pdf-rfc3161 %s -> self-heal' % state['state'].lower())
                healed = selfheal.repair_node_package(base, log=log, allow_network=allow_network)
                report['checks']['pdf_rfc3161_repair'] = healed
                if healed['action'] != 'none':
                    report['actions'].append('selfheal: ' + healed['action'])
        else:
            report['checks']['pdf_rfc3161_state_before'] = selfheal.node_package_state(base)['state']
        rc,out=_run([node,'--input-type=module','-e',"import('pdf-rfc3161').then(()=>process.exit(0)).catch(()=>process.exit(9))"],base,30)
        report['checks']['pdf_rfc3161_import_before']=(rc==0)
        if rc!=0:
            npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm') or shutil.which('npm')
            if auto_install and allow_network and npm:
                log('[STARTUP] pdf-rfc3161 missing/broken -> running npm install...')
                report['actions'].append('npm install')
                rc2,out2=_run([npm,'install','--no-audit','--no-fund'],base,240)
                report['checks']['npm_install_exit']=rc2
                report['checks']['npm_install_output_tail']=out2[-4000:]
                if rc2!=0: report['blockers'].append('Automatic npm install failed. See startup log.')
                else:
                    rc3,out3=_run([node,'--input-type=module','-e',"import('pdf-rfc3161').then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(9)})"],base,30)
                    report['checks']['pdf_rfc3161_import_after']=(rc3==0)
                    if rc3!=0: report['blockers'].append('pdf-rfc3161 still cannot be imported after npm install.')
            elif not allow_network:
                report['blockers'].append('pdf-rfc3161 is unavailable and automatic repair is limited to the vendored copy '
                                          '(repair.allow_network is false). Run Install_Windows.bat to install it from the vendor tree.')
            elif not npm: report['blockers'].append('pdf-rfc3161 is unavailable and npm was not found for automatic repair.')
            else: report['blockers'].append('pdf-rfc3161 is unavailable.')
        else: report['checks']['pdf_rfc3161_import_after']=True
    return report,cfg

def write_startup_report(base,report):
    p=Path(base)/'logs'/'startup_latest.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); return p
