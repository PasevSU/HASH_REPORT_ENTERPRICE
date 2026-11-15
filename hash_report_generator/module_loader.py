"""Declarative report-module loader. No executable plugins or hard-coded file list."""
from pathlib import Path
MODULE_DIR = Path(__file__).resolve().parent / 'modules'
PROFILE_DIR = Path(__file__).resolve().parent / 'report_profiles'
ALLOWED_TYPES = {'file_information','key_values','text','hash_table'}

def _read_all(folder):
    folder=Path(folder)
    if not folder.is_dir(): raise FileNotFoundError(folder)
    found={}
    from .js_rules import read_js_rules
    paths = sorted(folder.rglob('*.js'))
    for path, item in zip(paths, read_js_rules(folder, paths)):
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not item['id'].strip():
            raise ValueError(f'Invalid manifest: {path}')
        if item['id'] in found: raise ValueError(f'Duplicate id: {item["id"]}')
        found[item['id']]=item
    if not found: raise ValueError(f'No manifests in {folder}')
    return found

def load_modules(folder=None):
    modules=_read_all(folder or MODULE_DIR)
    for key,item in modules.items():
        if item.get('type') not in ALLOWED_TYPES: raise ValueError(f'Unsupported module type: {key}')
        if not isinstance(item.get('title'),str) or not item['title'].strip():
            raise ValueError(f'Missing title: {key}')
        fields=item.get('fields')
        if fields is not None and (
            not isinstance(fields,list)
            or not all(isinstance(field,str) and field.strip() for field in fields)
            or len(fields)!=len(set(fields))
        ):
            raise ValueError(f'Invalid fields in module: {key}')
    return modules

def load_profiles(folder=None,modules=None):
    profiles=_read_all(folder or PROFILE_DIR)
    available=modules if modules is not None else load_modules()
    for key,item in profiles.items():
        if not isinstance(item.get('title'),str) or not item['title'].strip():
            raise ValueError(f'Missing title: {key}')
        ids=item.get('modules')
        if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)):
            raise ValueError(f'Invalid module sequence: {key}')
        missing=set(ids)-available.keys()
        if missing: raise ValueError(f'Unknown modules in {key}: {sorted(missing)}')
    return profiles
