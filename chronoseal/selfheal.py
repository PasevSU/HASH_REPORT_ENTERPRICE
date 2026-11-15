"""Self-provisioning: verify and repair everything the pipeline needs to run.

The pipeline must not depend on a human remembering to run an installer. Every
external dependency is verified deterministically on disk first, then repaired
from local material when possible:

* the Node package ``pdf-rfc3161`` is restored byte-for-byte from ``vendor/``,
  which is hash-pinned by ``CHRONOSEAL_PATCH_MANIFEST.json`` (no network needed);
* Python packages are only installed when the caller explicitly allows network
  access, because a legal-evidence tool must not pull code from PyPI silently.

Repairs are idempotent, never touch the vendored originals, and every action is
written to the session log so the machine's state stays auditable.
"""
from pathlib import Path
import importlib.util, json, os, shutil, subprocess, sys, tempfile

NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0

NODE_PACKAGE = 'pdf-rfc3161'
NODE_MANIFEST = 'CHRONOSEAL_PATCH_MANIFEST.json'
PYTHON_BASE_MODULES = ('fitz', 'pypdf', 'reportlab')
PYTHON_QUALIFIED_MODULES = ('cryptography', 'signxml', 'lxml', 'requests', 'certifi')


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def required_python_modules(cfg):
    """Modules the active configuration actually needs."""
    cfg = cfg or {}
    modules = list(PYTHON_BASE_MODULES)
    if (cfg.get('rfc3161') or {}).get('require_qualified_stop'):
        modules += PYTHON_QUALIFIED_MODULES
    return tuple(modules)


def missing_python_modules(cfg):
    return [name for name in required_python_modules(cfg) if importlib.util.find_spec(name) is None]


def _export_entry(package_dir):
    """The file a bare ``import('<package>')`` resolves to, or None."""
    try:
        meta = json.loads((Path(package_dir) / 'package.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    exports = meta.get('exports')
    if isinstance(exports, dict):
        root = exports.get('.', exports)
        if isinstance(root, str):
            return root
        if isinstance(root, dict):
            for key in ('import', 'node', 'default', 'require'):
                if isinstance(root.get(key), str):
                    return root[key]
    for key in ('module', 'main'):
        if isinstance(meta.get(key), str):
            return meta[key]
    return None


def verify_package_dir(package_dir, manifest=True):
    """Return ``(ok, problems)`` for a package copy.

    ``manifest=True`` also compares every file against the vendored hash list,
    which is what makes a repaired ``node_modules`` provably identical to the
    pinned distributable.
    """
    package_dir = Path(package_dir)
    problems = []
    if not (package_dir / 'package.json').is_file():
        return False, ['package.json is missing']
    entry = _export_entry(package_dir)
    if not entry:
        problems.append('package.json declares no importable entry point')
    elif not (package_dir / entry).is_file():
        problems.append(f'entry point {entry} is missing')
    if manifest:
        manifest_path = package_dir / NODE_MANIFEST
        if not manifest_path.is_file():
            problems.append(f'{NODE_MANIFEST} is missing')
        else:
            try:
                expected = json.loads(manifest_path.read_text(encoding='utf-8'))['files_sha256']
            except (OSError, ValueError, KeyError) as exc:
                problems.append(f'{NODE_MANIFEST} cannot be read: {exc}')
                expected = {}
            for name, digest in sorted(expected.items()):
                target = package_dir / name
                if not target.is_file():
                    problems.append(f'file is missing: {name}')
                elif _sha256(target) != digest:
                    problems.append(f'file was modified: {name}')
    return (not problems), problems


def node_package_state(root, package=NODE_PACKAGE):
    """Deterministic on-disk state of the Node dependency (no process spawn)."""
    root = Path(root)
    installed = root / 'node_modules' / package
    vendor = root / 'vendor' / package
    state = {'package': package, 'installed': str(installed), 'vendor': str(vendor),
             'state': 'MISSING', 'detail': 'not installed', 'repairable': False}
    vendor_ok = vendor.is_dir() and (vendor / 'package.json').is_file()
    if vendor_ok:
        vendor_ok, vendor_problems = verify_package_dir(vendor)
        state['vendor'] = str(vendor)
        state['repairable'] = vendor_ok
        state['vendor_detail'] = 'verified' if vendor_ok else '; '.join(vendor_problems[:4])
    if not installed.is_dir():
        state['detail'] = 'node_modules/%s does not exist' % package
        return state
    ok, problems = verify_package_dir(installed)
    if ok:
        state['state'] = 'OK'
        state['detail'] = 'verified against the vendored manifest'
        return state
    # An installed copy without our manifest is still usable if the entry point
    # exists; the hash pin only applies to copies we ship.
    if (installed / NODE_MANIFEST).is_file():
        state['state'] = 'BROKEN'
        state['detail'] = '; '.join(problems[:4])
    elif _export_entry(installed) and (installed / _export_entry(installed)).is_file():
        state['state'] = 'OK'
        state['detail'] = 'entry point present (unpinned copy)'
    else:
        state['state'] = 'BROKEN'
        state['detail'] = '; '.join(problems[:4])
    return state


def install_from_vendor(root, package=NODE_PACKAGE, log=print):
    """Copy the vendored package into ``node_modules`` after verifying both sides."""
    root = Path(root)
    vendor = root / 'vendor' / package
    target = root / 'node_modules' / package
    ok, problems = verify_package_dir(vendor)
    if not ok:
        log('SELF-HEAL: the vendored %s copy is not trustworthy (%s); not installing it.' % (package, '; '.join(problems[:3])))
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.%s-' % package, dir=str(target.parent)))
    try:
        copy = staging / package
        shutil.copytree(vendor, copy)
        if target.is_symlink() or (hasattr(os.path, 'isjunction') and os.path.isjunction(target)):
            os.unlink(target)
        elif target.exists():
            shutil.rmtree(target)
        os.replace(copy, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    ok, problems = verify_package_dir(target)
    if ok:
        log('SELF-HEAL: restored node_modules/%s from the vendored, hash-pinned copy.' % package)
    else:
        log('SELF-HEAL: restored node_modules/%s but verification failed: %s' % (package, '; '.join(problems[:3])))
    return ok


def npm_install(root, log=print, npm=None):
    """Fall back to the package manager (needs network)."""
    npm = npm or shutil.which('npm')
    if not npm:
        log('SELF-HEAL: npm was not found; cannot install %s from the registry.' % NODE_PACKAGE)
        return False
    try:
        log('> %s install --no-audit --no-fund' % npm)
        q = subprocess.run([npm, 'install', '--no-audit', '--no-fund'], cwd=str(root), stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=900, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        log('SELF-HEAL: npm install failed: %s' % exc)
        return False
    if q.returncode:
        log('SELF-HEAL: npm install failed (%s): %s' % (q.returncode, (q.stderr or q.stdout or '').strip()[-400:]))
        return False
    return node_package_state(root)['state'] == 'OK'


def repair_node_package(root, log=print, allow_network=False, npm=None, package=NODE_PACKAGE):
    """Make the Node dependency usable. Returns a report dict."""
    before = node_package_state(root, package)
    report = {'before': before['state'], 'action': 'none', 'after': before['state'], 'detail': before['detail']}
    if before['state'] == 'OK':
        return report
    if before['repairable'] and install_from_vendor(root, log=log):
        report['action'] = 'restored from vendor'
    elif allow_network:
        report['action'] = 'npm install'
        if not npm_install(root, log=log, npm=npm):
            report['action'] = 'npm install failed'
    else:
        log('SELF-HEAL: cannot repair node_modules/%s automatically (%s).'
            % (package, before.get('vendor_detail') or 'no usable vendored copy'))
    after = node_package_state(root)
    report['after'] = after['state']
    report['detail'] = after['detail']
    return report


def repair_python_packages(root, log=print, allow_network=False, cfg=None, python=None):
    """Install the missing Python packages, but only with explicit consent."""
    missing = missing_python_modules(cfg)
    report = {'missing': missing, 'action': 'none', 'after': missing}
    if not missing:
        return report
    requirements = next((c for c in (Path(root) / 'requirements-integration.txt',
                                     Path(root) / 'requirements.txt') if c.is_file()),
                        Path(root) / 'requirements-integration.txt')
    if not allow_network:
        report['action'] = 'reported (network installs are disabled)'
        return report
    if not requirements.is_file():
        report['action'] = 'reported (%s is missing)' % requirements.name
        return report
    python = python or sys.executable
    log('> %s -m pip install -r %s' % (python, requirements.name))
    try:
        q = subprocess.run([python, '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
                            '-r', str(requirements)], cwd=str(root), stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=1800, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        log('SELF-HEAL: pip install failed: %s' % exc)
        report['action'] = 'pip install failed'
        return report
    if q.returncode:
        log('SELF-HEAL: pip install failed (%s): %s' % (q.returncode, (q.stderr or q.stdout or '').strip()[-400:]))
        report['action'] = 'pip install failed'
        return report
    report['action'] = 'pip install -r %s' % requirements.name
    report['after'] = missing_python_modules(cfg)
    return report


def self_check(root, cfg=None, log=print, allow_network=False, repair=True):
    """Verify every dependency and repair what can be repaired locally."""
    root = Path(root)
    report = {'root': str(root), 'allow_network': bool(allow_network), 'actions': [], 'problems': []}
    node = node_package_state(root)
    if node['state'] != 'OK' and repair:
        result = repair_node_package(root, log=log, allow_network=allow_network)
        report['actions'].append({'dependency': 'node:%s' % NODE_PACKAGE, **result})
    node = node_package_state(root)
    report['node_package'] = node
    if node['state'] != 'OK':
        report['problems'].append('node:%s is %s (%s)' % (NODE_PACKAGE, node['state'].lower(), node['detail']))
    missing = missing_python_modules(cfg)
    if missing and repair:
        result = repair_python_packages(root, log=log, allow_network=allow_network, cfg=cfg)
        report['actions'].append({'dependency': 'python', **result})
        missing = result['after']
    report['missing_python'] = missing
    if missing:
        report['problems'].append('missing Python modules: ' + ', '.join(missing))
    report['ok'] = not report['problems']
    return report


def main(argv=None):
    """``python -m chronoseal.selfheal`` — verify and repair, exit 0/2."""
    import argparse
    parser = argparse.ArgumentParser(prog='python -m chronoseal.selfheal', description='Verify and repair ChronoSeal dependencies.')
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--config', default=None)
    parser.add_argument('--allow-network', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    root = Path(args.root)
    cfg = {}
    config_path = Path(args.config) if args.config else root / 'config' / 'config.json'
    if config_path.is_file():
        cfg = json.loads(config_path.read_text(encoding='utf-8'))
    lines = []
    report = self_check(root, cfg, lines.append, allow_network=args.allow_network)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for line in lines:
            print(line)
        for problem in report['problems']:
            print('BLOCKER: ' + problem)
        print('SELF-CHECK ' + ('PASS' if report['ok'] else 'BLOCKED'))
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
