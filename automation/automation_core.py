"""Independent job planner; imports the original pipeline only at execution."""
from pathlib import Path
import tempfile
import shutil
import hashlib
import json

MODES=('SINGLE_SELECTED','SINGLE_FOLDER','COMBO_FOLDER','COMBO_RECURSIVE','SINGLE_AND_COMBO','COMBO_SELECTED','SINGLE_AND_COMBO_SELECTED')

def plan(source, mode, selected=()):
    source=Path(source).expanduser().resolve()
    if not source.exists(): raise ValueError('Източникът не съществува: '+str(source))
    if mode not in MODES: raise ValueError('Непознат режим')
    if mode in ('COMBO_SELECTED','SINGLE_AND_COMBO_SELECTED'):
        if not source.is_dir(): raise ValueError('Изберете директория')
        paths=[Path(x).expanduser().resolve() for x in selected]
        if not paths: raise ValueError('Няма избрани файлове')
        if len(set(paths))!=len(paths): raise ValueError('Повтарящи се файлове')
        if any(not p.is_file() or p.parent!=source for p in paths):
            raise ValueError('Файловете трябва да са в избраната директория')
        return ([(p,'single',False) for p in paths] if mode=='SINGLE_AND_COMBO_SELECTED' else [])+[(tuple(paths),'combined',False)]
    if mode=='SINGLE_SELECTED':
        if not source.is_dir(): raise ValueError('Изберете директория')
        paths=[Path(x).expanduser().resolve() for x in selected]
        if not paths: raise ValueError('Няма избрани файлове')
        if len(set(paths))!=len(paths): raise ValueError('Повтарящи се файлове')
        if any(not p.is_file() or p.parent!=source for p in paths): raise ValueError('Файловете трябва да са в избраната директория')
        return [(p,'single',False) for p in paths]
    if mode=='SINGLE_FOLDER':
        if not source.is_dir(): raise ValueError('Изберете директория')
        paths=sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower()!='.pdf')
        if not paths: raise ValueError('Няма файлове за обработка')
        return [(p,'single',False) for p in paths]
    if mode=='COMBO_FOLDER':
        if not source.is_dir(): raise ValueError('Изберете директория')
        return [(source,'combined',False)]
    if mode=='COMBO_RECURSIVE':
        if not source.is_dir(): raise ValueError('Изберете директория')
        return [(source,'combined',True)]
    if mode=='SINGLE_AND_COMBO':
        if not source.is_dir(): raise ValueError('Изберете директория')
        paths=sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower()!='.pdf')
        return [(p,'single',False) for p in paths]+[(source,'combined',False)]
    raise ValueError('Неподдържан режим')

def execute(base, jobs, cancel_event, emit):
    from chronoseal.pipeline import Pipeline
    base=Path(base)
    cfg=json.loads((base/'config'/'config.json').read_text(encoding='utf-8'))
    results=[]
    for idx,(target,mode,recursive) in enumerate(jobs,1):
        if cancel_event.is_set():
            emit('STOP: отменени оставащите задачи');break
        emit(f'[{idx}/{len(jobs)}] START {target}')
        try:
            pipeline=Pipeline(base,cfg,log=emit,cancel_event=cancel_event)
            if isinstance(target,tuple):
                # The existing Pipeline has no selected-files argument. Stage byte-identical
                # copies in a private directory; record original paths and hashes for traceability.
                case_root=target[0].parent/'ChronoSeal_Selected_Cases'
                case_root.mkdir(exist_ok=True)
                staged=Path(tempfile.mkdtemp(prefix='selection_',dir=case_root))
                provenance=[]
                for original in target:
                    before=hashlib.sha256(original.read_bytes()).hexdigest()
                    copied=staged/original.name
                    shutil.copy2(original,copied)
                    after=hashlib.sha256(copied.read_bytes()).hexdigest()
                    if before!=after: raise RuntimeError('SOURCE_CHANGED: '+str(original))
                    provenance.append({'original':str(original),'staged_name':copied.name,'sha256':before})
                (staged/'selection-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
                # Do not put the provenance JSON in the scan directory: the generator
                # would otherwise hash it as if it were a selected source file.
                (staged/'selection-provenance.json').rename(case_root/(staged.name+'_provenance.json'))
                emit('SELECTED COMBO: запазени копия и отделен provenance manifest: '+str(staged))
                manifest=pipeline.run(str(staged),mode=mode,recursive=False,output_dir=str(target[0].parent))
                manifest=dict(manifest)
                manifest['selected_provenance']=provenance
            else:
                manifest=pipeline.run(str(target),mode=mode,recursive=recursive)
            results.append({'target':str(target),'status':'PASS','final_pdf':manifest.get('final_pdf'),'selected_provenance':manifest.get('selected_provenance',[])})
            emit(f'[{idx}/{len(jobs)}] PASS {manifest.get("final_pdf", "")}')
        except Exception as exc:
            results.append({'target':str(target),'status':'FAILED','error':str(exc)})
            emit(f'[{idx}/{len(jobs)}] FAILED {exc}')
            if cancel_event.is_set():break
    return results
