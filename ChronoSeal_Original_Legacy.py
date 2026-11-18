import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import json, threading, os, subprocess, queue, copy
from chronoseal.pipeline import Pipeline, Cancelled
from chronoseal.settings import load,save,executable
from chronoseal.logging_bundle import SessionLogger
from chronoseal.startup import startup_check, write_startup_report
from chronoseal.provider_bootstrap import bootstrap_providers, BootstrapError
from chronoseal.provider_catalog import apply_profile
from chronoseal.tk_support import init_root
from chronoseal.embed_options import (DEFAULT_EMBED_POSITION, EmbedOptionError,
                                      resolve_embed_options, summary_text)
from chronoseal import branding

def _brand_font(widget,size=10,weight=None,role='ui'):
 return branding.FontBook(widget).font(size,weight,role=role)

BASE=Path(__file__).resolve().parent; CFG_PATH=BASE/'config'/'config.json'
# Operator-facing text for the two option dialogs. The language follows the shell
# that opens them: the legacy window is Bulgarian, the page-based desktop is English.
EMBED_TEXT={'bg':{'error_title':'ChronoSeal — PDF вграждане','embed_title':'ChronoSeal — PDF вграждане','embed_heading':'Вграждане на PDF в отчета','embed_check':'Вгради PDF страниците и оригинала като приложение','position':'Позиция спрямо хеш отчета','before':'Преди отчета','after':'След отчета (по подразбиране)','pdf_label':'PDF за вграждане (COMBO)','pdf_choose':'PDF…','single_hint':'При SINGLE вход (един PDF файл) се вгражда самият входен файл, независимо от това поле.','preview':'Какво ще се получи','other_hint':'Останалите опции са в „Отчет…“ на началния екран.','ok':'OK','cancel':'Отказ','report_title':'ChronoSeal — опции на отчета','report_heading':'Останали опции на отчета','explanation':'ERLAEUTERUNG.pdf като страници в отчета (когато файлът е наличен)','recursive':'Включи подпапките (при папка)','folder':'Запази отчета и доказателствата в друга папка','browse':'Browse…'},'en':{'error_title':'ChronoSeal — PDF embedding','embed_title':'ChronoSeal — PDF embedding','embed_heading':'Embed a PDF in the report','embed_check':'Embed the PDF pages and keep the original as an attachment','position':'Position relative to the hash report','before':'Before report','after':'After report (default)','pdf_label':'PDF to embed (COMBO)','pdf_choose':'PDF…','single_hint':'With a SINGLE input (one PDF file) the input file itself is embedded, whatever this field holds.','preview':'What the run will produce','other_hint':'The remaining options live in "Report options…" on the run page.','ok':'OK','cancel':'Cancel','report_title':'ChronoSeal — report options','report_heading':'Remaining report options','explanation':'ERLAEUTERUNG.pdf as pages in the report (when the file is present)','recursive':'Include subfolders (folder input)','folder':'Save the report and evidence in a different folder','browse':'Browse'}}
class App(tk.Tk):
 embed_language='bg'

 def __init__(self, *, auto_bootstrap=True):
  init_root(self); self._main_thread=threading.get_ident(); self._uiq=queue.Queue(); self._closed=False; self.after(20,self._pump_ui); self.title('ChronoSeal — Windows RFC3161 Control Center'); self.geometry('1040x760'); self.minsize(900,650)
  self.cfg=load(CFG_PATH); self.target=tk.StringVar(value=''); self.mode=tk.StringVar(value='combined'); self.rec=tk.BooleanVar(value=False); self.custom_output=tk.BooleanVar(value=False); self.output_folder=tk.StringVar(value=''); self.status=tk.StringVar(value='Ready'); self.file_filters=[]; self.cancel=threading.Event(); self.session=None; self.last_result=None; self.startup_ready=False
  self._configure_enterprise_theme(); self._ui(); self._install_windows_editing(); self.go.config(state='disabled')
  if auto_bootstrap:self.status.set('Startup check…'); self.after(150,self.startup_bootstrap)
 def _configure_enterprise_theme(self):
  # Presentation-only styling; no change to report/TSA/verification operations.
  # Every colour and font comes from chronoseal.branding (single source of truth).
  style=ttk.Style(self)
  if 'clam' in style.theme_names():style.theme_use('clam')
  B=branding.PALETTE; fonts=branding.FontBook(self)
  bg=B['background']; panel=B['primary']; fg=B['ink']; accent=B['accent']
  self.configure(background=bg)
  style.configure('.',font=fonts.font(10))
  style.configure('TFrame',background=bg)
  style.configure('TLabel',background=bg,foreground=fg)
  style.configure('TCheckbutton',background=bg,foreground=fg)
  style.map('TCheckbutton',background=[('active',bg)],foreground=[('active',fg)])
  style.configure('TNotebook',background=bg,borderwidth=0)
  style.configure('TNotebook.Tab',background=panel,foreground=B['rail_text'],padding=(20,11))
  style.map('TNotebook.Tab',background=[('selected',accent)],foreground=[('selected',B['on_accent'])])
  style.configure('TButton',background=panel,foreground=B['rail_text'],padding=(12,9),borderwidth=0)
  style.map('TButton',background=[('active',B['primary_hover'])],foreground=[('active',B['rail_text_strong'])])
  style.configure('Accent.TButton',background=accent,foreground=B['on_accent'],font=fonts.font(10,'bold'),padding=(12,13))
  style.map('Accent.TButton',background=[('active',B['accent_hover'])],foreground=[('active',B['on_accent'])])
  style.configure('TEntry',fieldbackground=B['surface_alt'],foreground=B['body'],padding=6)
  style.configure('TProgressbar',background=accent,troughcolor=B['trough'])

 def _install_windows_editing(self):
  # Native Windows editing semantics for every editable Entry/Text/Combobox.
  def select_all(w):
   try:
    if isinstance(w,(tk.Text,tk.Listbox)): w.tag_add('sel','1.0','end-1c') if isinstance(w,tk.Text) else w.selection_set(0,'end')
    else: w.selection_range(0,'end'); w.icursor('end')
   except Exception: pass
   return 'break'
  def evt(name):
   def f(e):
    try:e.widget.event_generate(name)
    except Exception:pass
    return 'break'
   return f
  for cls in ('TEntry','Entry','TCombobox','Text'):
   self.bind_class(cls,'<Control-a>',lambda e:select_all(e.widget),add='+'); self.bind_class(cls,'<Control-A>',lambda e:select_all(e.widget),add='+')
   self.bind_class(cls,'<Control-c>',evt('<<Copy>>'),add='+'); self.bind_class(cls,'<Control-C>',evt('<<Copy>>'),add='+')
   self.bind_class(cls,'<Control-v>',evt('<<Paste>>'),add='+'); self.bind_class(cls,'<Control-V>',evt('<<Paste>>'),add='+')
   self.bind_class(cls,'<Control-x>',evt('<<Cut>>'),add='+'); self.bind_class(cls,'<Control-X>',evt('<<Cut>>'),add='+')
   self.bind_class(cls,'<Control-Insert>',evt('<<Copy>>'),add='+'); self.bind_class(cls,'<Shift-Insert>',evt('<<Paste>>'),add='+'); self.bind_class(cls,'<Shift-Delete>',evt('<<Cut>>'),add='+')
   self.bind_class(cls,'<Button-3>',self._edit_context,add='+')
 def _edit_context(self,e):
  w=e.widget; m=tk.Menu(self,tearoff=0)
  def gen(x):
   try:w.event_generate(x)
   except Exception:pass
  m.add_command(label='Cut',command=lambda:gen('<<Cut>>')); m.add_command(label='Copy',command=lambda:gen('<<Copy>>')); m.add_command(label='Paste',command=lambda:gen('<<Paste>>')); m.add_separator(); m.add_command(label='Select all',command=lambda:self._select_widget_all(w))
  try:m.tk_popup(e.x_root,e.y_root)
  finally:m.grab_release()
  return 'break'
 def _select_widget_all(self,w):
  try:
   if isinstance(w,tk.Text):w.tag_add('sel','1.0','end-1c');w.mark_set('insert','end-1c');w.see('insert')
   else:w.selection_range(0,'end');w.icursor('end')
  except Exception:pass
 def _copy_text_widget(self,w,all_text=False):
  try:text=w.get('1.0','end-1c') if all_text else w.get('sel.first','sel.last')
  except Exception:text=w.get('1.0','end-1c')
  self.clipboard_clear();self.clipboard_append(text);self.update_idletasks()
 def _copyable_error(self,title,text):
  d=tk.Toplevel(self);d.title(title);d.geometry('850x560');d.transient(self)
  box=tk.Text(d,wrap='word');box.pack(fill='both',expand=True,padx=10,pady=10);box.insert('1.0',text);box.focus_set()
  b=ttk.Frame(d);b.pack(fill='x',padx=10,pady=(0,10));ttk.Button(b,text='Copy selected',command=lambda:self._copy_text_widget(box,False)).pack(side='left');ttk.Button(b,text='Copy all',command=lambda:self._copy_text_widget(box,True)).pack(side='left',padx=5);ttk.Button(b,text='Close',command=d.destroy).pack(side='right')
  d.bind('<Escape>',lambda e:d.destroy());d.grab_set()
 def _pump_ui(self):
  # Main-thread executor: workers only enqueue; Tk is touched here exclusively.
  try:
   while True:
    fn,box=self._uiq.get_nowait()
    try:box['r']=fn()
    except BaseException as e:box['e']=e
    if 'ev' in box:box['ev'].set()
  except queue.Empty:pass
  if not self._closed:self.after(20,self._pump_ui)
 def destroy(self):
  self._closed=True; super().destroy()
 def _post(self,fn):
  # Fire-and-forget marshal to the Tk main thread.
  if threading.get_ident()==self._main_thread:return fn()
  self._uiq.put((fn,{}))
 def _call_main(self,fn):
  # Run fn on the Tk main thread and return its result (or re-raise); callable from any thread.
  if threading.get_ident()==self._main_thread:return fn()
  box={'ev':threading.Event()}; self._uiq.put((fn,box))
  while not box['ev'].wait(0.1):
   if self._closed:raise RuntimeError('Application closed')
  if 'e' in box:raise box['e']
  return box.get('r')
 def startup_bootstrap(self):
  self.go.config(state='disabled'); self.startup_ready=False; cfg0=copy.deepcopy(self.cfg)
  def job():
   try:
    report,cfg=startup_check(BASE,cfg0,True,self.write); save(CFG_PATH,cfg); rp=write_startup_report(BASE,report); self._post(lambda:self._startup_done(report,rp,cfg))
   except Exception as e:self._post(lambda e=e:self._startup_failed(e))
  threading.Thread(target=job,daemon=True).start()
 def _startup_done(self,report,rp,cfg=None):
  if cfg is not None:self.cfg=cfg
  self.v_node.set((self.cfg.get('tools') or {}).get('node','')); self.v_ssl.set((self.cfg.get('tools') or {}).get('openssl',''))
  if report['blockers']:
   self.startup_ready=False; self.status.set('SETUP REQUIRED'); self.go.config(state='disabled'); self.diag.delete('1.0','end'); self.diag.insert('end',json.dumps(report,indent=2,ensure_ascii=False)); messagebox.showerror('ChronoSeal — Setup required','Startup qualification BLOCKED:\n\n'+'\n'.join(report['blockers'])+'\n\nReport: '+str(rp))
  else:
   self.startup_ready=True; self.status.set('Ready — startup qualification PASS'); self.go.config(state='normal'); self.write('[STARTUP] qualification PASS')
   if report['actions']:messagebox.showinfo('ChronoSeal','Startup repair completed automatically:\n\n'+'\n'.join(report['actions'])+'\n\nChronoSeal is ready.')
 def _startup_failed(self,e):self.startup_ready=False; self.status.set('STARTUP FAILED'); self.go.config(state='disabled'); messagebox.showerror('ChronoSeal',f'Startup self-check failed:\n\n{e}')
 def _ui(self):
  self.nb=ttk.Notebook(self); self.nb.pack(fill='both',expand=True,padx=8,pady=8); self.run_tab=ttk.Frame(self.nb,padding=12); self.set_tab=ttk.Frame(self.nb,padding=12); self.diag_tab=ttk.Frame(self.nb,padding=12); self.nb.add(self.run_tab,text='Run'); self.nb.add(self.set_tab,text='Settings'); self.nb.add(self.diag_tab,text='Diagnostics & Logs')
  f=self.run_tab; ttk.Label(f,text='Input source, folder, or already generated PDF').pack(anchor='w'); r=ttk.Frame(f); r.pack(fill='x',pady=(2,8)); ttk.Entry(r,textvariable=self.target).pack(side='left',fill='x',expand=True); ttk.Button(r,text='File…',command=self.file).pack(side='left',padx=3); ttk.Button(r,text='Folder…',command=self.folder).pack(side='left')
  m=ttk.Frame(f); m.pack(fill='x'); self.mode_label=ttk.Label(m,text='Report type: automatic (File → SINGLE / Folder → COMBO)'); self.mode_label.pack(side='left'); self.rec_check=ttk.Checkbutton(m,text='Recursive (folders only)',variable=self.rec); self.rec_check.pack(side='left',padx=18)
  o=ttk.Frame(f); o.pack(fill='x',pady=(7,0)); ttk.Checkbutton(o,text='Save in another folder (default: working folder)',variable=self.custom_output).pack(side='left'); ttk.Entry(o,textvariable=self.output_folder).pack(side='left',fill='x',expand=True,padx=6); ttk.Button(o,text='Browse…',command=lambda:self._dir(self.output_folder)).pack(side='left')
  e=ttk.Frame(f); e.pack(fill='x',pady=(7,0)); ev=self._embed_vars(); ttk.Checkbutton(e,text='Вгради PDF в отчета',variable=ev['enabled']).pack(side='left'); ttk.Entry(e,textvariable=ev['path']).pack(side='left',fill='x',expand=True,padx=6); ttk.Button(e,text='PDF…',command=self._choose_embed_pdf).pack(side='left'); ttk.Radiobutton(e,text='преди',value='before',variable=ev['position']).pack(side='left',padx=(10,0)); ttk.Radiobutton(e,text='след',value='after',variable=ev['position']).pack(side='left'); ttk.Button(e,text='Вграждане…',command=self._embed_dialog).pack(side='left',padx=(10,0)); ttk.Button(e,text='Отчет…',command=self._report_options_dialog).pack(side='left',padx=(6,0))
  ttk.Label(f,textvariable=ev['summary']).pack(anchor='w',pady=(3,0))
  self.go=ttk.Button(f,text='ONE BUTTON — REPORT → RFC3161 → FINAL VERIFY → EVIDENCE',command=self.start,style='Accent.TButton'); self.go.pack(fill='x',pady=(12,4)); self.stop=ttk.Button(f,text='Stop / Cancel',command=self.cancel_run,state='disabled'); self.stop.pack(fill='x'); self.pb=ttk.Progressbar(f,maximum=100); self.pb.pack(fill='x',pady=(10,2)); ttk.Label(f,textvariable=self.status).pack(anchor='w'); self.log=tk.Text(f,height=25,wrap='none',background=branding.PALETTE['console_bg'],foreground=branding.PALETTE['console_fg'],insertbackground=branding.PALETTE['on_accent'],font=_brand_font(self,10,role='mono'),relief='flat'); self.log.pack(fill='both',expand=True,pady=(6,0)); lb=ttk.Frame(f); lb.pack(fill='x',pady=(4,0)); ttk.Button(lb,text='Copy selected',command=lambda:self._copy_text_widget(self.log,False)).pack(side='left'); ttk.Button(lb,text='Copy all log',command=lambda:self._copy_text_widget(self.log,True)).pack(side='left',padx=5); self._settings_ui(); self._diag_ui()
 def _row(self,parent,label,var,browse=None):
  x=ttk.Frame(parent); x.pack(fill='x',pady=3); ttk.Label(x,text=label,width=25).pack(side='left'); ttk.Entry(x,textvariable=var).pack(side='left',fill='x',expand=True); ttk.Button(x,text='Browse…',command=browse).pack(side='left',padx=4)
 def _settings_ui(self):
  f=self.set_tab; g=self.cfg.get('generator',{}); p=self.cfg.get('rfc3161',{}); tools=self.cfg.get('tools',{}); archive=self.cfg.get('archive',{}); self.v_gen=tk.StringVar(value=g.get('package_dir','')); self.v_node=tk.StringVar(value=tools.get('node','')); self.v_ssl=tk.StringVar(value=tools.get('openssl','')); self.v_surl=tk.StringVar(value=(p.get('start') or [{}])[0].get('url','')); self.v_scert=tk.StringVar(value=';'.join((p.get('start') or [{}])[0].get('trust_root_files',[]))); self.v_turl=tk.StringVar(value=(p.get('stop') or [{}])[0].get('url','')); self.v_tcert=tk.StringVar(value=';'.join((p.get('stop') or [{}])[0].get('trust_root_files',[]))); self.v_archive_enabled=tk.BooleanVar(value=archive.get('enabled',True)); self.v_archive_dir=tk.StringVar(value=archive.get('directory','ChronoSeal_Archive')); self.v_archive_db=tk.StringVar(value=archive.get('database','ChronoSeal_Archive\\chronoseal_archive.sqlite3'))
  ttk.Label(f,text='Windows integration, report archive and independent TSA trust',font=_brand_font(self,11,'bold')).pack(anchor='w',pady=(0,8)); ttk.Checkbutton(f,text='Archive each sealed report, manifest, log and evidence in a numbered folder and SQLite database',variable=self.v_archive_enabled).pack(anchor='w',pady=(0,4)); self._row(f,'Report archive folder',self.v_archive_dir,lambda:self._dir(self.v_archive_dir)); self._row(f,'SQLite archive database',self.v_archive_db,lambda:self._database_file(self.v_archive_db)); self._row(f,'Hash generator package',self.v_gen,lambda:self._dir(self.v_gen)); self._row(f,'Node.js / node.exe',self.v_node,lambda:self._exe(self.v_node)); self._row(f,'OpenSSL / openssl.exe',self.v_ssl,lambda:self._exe(self.v_ssl)); ttk.Separator(f).pack(fill='x',pady=10); cat=list((self.cfg.get('provider_catalog') or {}).keys()); self.v_sprofile=tk.StringVar(value=(p.get('start') or [{}])[0].get('name','FreeTSA')); self.v_tprofile=tk.StringVar(value=(p.get('stop') or [{}])[0].get('name','DigiCert')); pr=ttk.Frame(f); pr.pack(fill='x',pady=3); ttk.Label(pr,text='START provider preset',width=25).pack(side='left'); ttk.Combobox(pr,textvariable=self.v_sprofile,values=cat,state='readonly').pack(side='left',fill='x',expand=True); ttk.Button(pr,text='Apply',command=lambda:self.apply_provider('start')).pack(side='left',padx=4); pr2=ttk.Frame(f); pr2.pack(fill='x',pady=3); ttk.Label(pr2,text='STOP provider preset',width=25).pack(side='left'); ttk.Combobox(pr2,textvariable=self.v_tprofile,values=cat,state='readonly').pack(side='left',fill='x',expand=True); ttk.Button(pr2,text='Apply',command=lambda:self.apply_provider('stop')).pack(side='left',padx=4); self._row(f,'START TSA URL',self.v_surl,lambda:None); self._row(f,'START trust cert(s)',self.v_scert,lambda:self._certs(self.v_scert)); self._row(f,'STOP TSA URL',self.v_turl,lambda:None); self._row(f,'STOP trust cert(s)',self.v_tcert,lambda:self._certs(self.v_tcert)); b=ttk.Frame(f); b.pack(fill='x',pady=12); ttk.Button(b,text='Auto-detect Windows tools',command=self.autodetect).pack(side='left'); ttk.Button(b,text='Save settings',command=self.save_settings).pack(side='left',padx=6); ttk.Button(b,text='Run preflight',command=self.preflight_only).pack(side='left'); ttk.Button(b,text='Bootstrap TSA trust',command=self.bootstrap_trust).pack(side='left',padx=6); ttk.Label(f,text='Trust certificates must be approved certificates/chains for the external TSA. ChronoSeal does not generate production TSA certificates.',wraplength=900).pack(anchor='w',pady=8)
 def _diag_ui(self):
  f=self.diag_tab; ttk.Label(f,text='Diagnostics and complete log package',font=_brand_font(self,11,'bold')).pack(anchor='w'); self.diag=tk.Text(f,height=28,background=branding.PALETTE['console_bg'],foreground=branding.PALETTE['console_fg'],insertbackground=branding.PALETTE['on_accent'],font=_brand_font(self,10,role='mono'),relief='flat'); self.diag.pack(fill='both',expand=True,pady=8); b=ttk.Frame(f); b.pack(fill='x'); ttk.Button(b,text='Refresh diagnostics',command=self.diagnostics).pack(side='left'); ttk.Button(b,text='Open latest log folder',command=self.open_logs).pack(side='left',padx=5); ttk.Button(b,text='Open evidence folder',command=self.open_evidence).pack(side='left'); ttk.Button(b,text='Copy selected',command=lambda:self._copy_text_widget(self.diag,False)).pack(side='left',padx=5); ttk.Button(b,text='Copy all',command=lambda:self._copy_text_widget(self.diag,True)).pack(side='left')
 def _embed_vars(self):
  # One shared state for every surface: the run page row, the PDF-embedding
  # dialog and the Report-from-Files page read and write the same variables,
  # so a choice made in one window is what the next run actually uses.
  if getattr(self,'_embed_state',None) is None:
   self._embed_state={'enabled':tk.BooleanVar(master=self,value=False),'path':tk.StringVar(master=self,value=''),'position':tk.StringVar(master=self,value='after'),'explanation':tk.BooleanVar(master=self,value=False),'summary':tk.StringVar(master=self,value='')}
   for key in ('enabled','path','position'):self._embed_state[key].trace_add('write',lambda *_a:self._sync_embed_summary())
   self.rec.trace_add('write',lambda *_a:self._sync_embed_summary())
   self.target.trace_add('write',lambda *_a:self._sync_embed_summary())
  return self._embed_state
 def _choose_embed_pdf(self):
  x=filedialog.askopenfilename(title='PDF за вграждане',filetypes=[('PDF','*.pdf'),('All files','*.*')])
  if x:self._embed_vars()['path'].set(x)
 def _embed_selection(self):
  # Non-raising view of the shared state: a half-finished choice is reported in
  # the summary line instead of interrupting the operator with an error box.
  st=self._embed_vars()
  try:
   return resolve_embed_options(enabled=bool(st['enabled'].get()),position=st['position'].get(),path=st['path'].get(),target=self.target.get(),file_list=bool(getattr(self,'file_selection',None)),recursive=bool(self.rec.get()),language=self.embed_language)
  except EmbedOptionError as e:
   return {'enabled':True,'position':st['position'].get() or DEFAULT_EMBED_POSITION,'report_type':'','source':None,'error':str(e)}
 def _sync_embed_summary(self):
  # Read-back published on every page: report type, position and the PDF name.
  st=self._embed_vars(); r=self._embed_selection(); text=r.get('error') or summary_text(r,self.embed_language)
  try:st['summary'].set(text)
  except tk.TclError:pass
  return r
 def _resolve_embed(self):
  # Strict variant used by the run: raises ValueError with the operator message.
  st=self._embed_vars(); r=self._embed_selection()
  if r.get('error'):raise ValueError(r['error'])
  return {'explanation':bool(st['explanation'].get()),'source_pdf':r['source_pdf'],'pdf':r['pdf'],'position':r['position'],'report_type':r['report_type']}
 def _embed_dialog(self):
  # One dialog, one subject: what is embedded and where it goes. The report-wide
  # switches moved to _report_options_dialog, so neither window needs scrolling.
  T=EMBED_TEXT.get(self.embed_language,EMBED_TEXT['bg'])
  st=self._embed_vars(); d=tk.Toplevel(self); d.title(T['embed_title']); d.transient(self); d.geometry('760x370'); d.columnconfigure(0,weight=1)
  snap=(st['enabled'].get(),st['path'].get(),st['position'].get())
  def cancel():
   st['enabled'].set(snap[0]); st['path'].set(snap[1]); st['position'].set(snap[2]); self._sync_embed_summary(); d.destroy()
  def apply():
   r=self._sync_embed_summary()
   if r.get('error'):messagebox.showerror(T['error_title'],r['error'],parent=d); return
   d.destroy()
  b=ttk.Frame(d,padding=16); b.pack(fill='both',expand=True); b.columnconfigure(1,weight=1); row=0
  ttk.Label(b,text=T['embed_heading'],font=_brand_font(self,11,'bold')).grid(row=row,column=0,columnspan=3,sticky='w',pady=(0,12)); row+=1
  ttk.Checkbutton(b,text=T['embed_check'],variable=st['enabled']).grid(row=row,column=0,columnspan=3,sticky='w'); row+=1
  ttk.Label(b,text=T['position']).grid(row=row,column=0,sticky='w',pady=6)
  pos=ttk.Frame(b); pos.grid(row=row,column=1,columnspan=2,sticky='w'); before_radio=ttk.Radiobutton(pos,text=T['before'],value='before',variable=st['position']); before_radio.pack(side='left'); after_radio=ttk.Radiobutton(pos,text=T['after'],value='after',variable=st['position']); after_radio.pack(side='left',padx=14); row+=1
  ttk.Label(b,text=T['pdf_label']).grid(row=row,column=0,sticky='w')
  path_entry=ttk.Entry(b,textvariable=st['path']); path_entry.grid(row=row,column=1,sticky='ew',padx=8); path_choose=ttk.Button(b,text=T['pdf_choose'],command=self._choose_embed_pdf); path_choose.grid(row=row,column=2); row+=1
  # Same rule as the run page: before the PDF is enabled these three controls
  # have nothing to act on, so they are shown but not offered.
  if hasattr(self,'_gate'):self._gate(st['enabled'],(before_radio,after_radio,path_entry,path_choose))
  ttk.Label(b,text=T['single_hint'],wraplength=700).grid(row=row,column=0,columnspan=3,sticky='w',pady=(4,10)); row+=1
  ttk.Separator(b).grid(row=row,column=0,columnspan=3,sticky='ew',pady=8); row+=1
  ttk.Label(b,text=T['preview'],font=_brand_font(self,10,'bold')).grid(row=row,column=0,columnspan=3,sticky='w'); row+=1
  ttk.Label(b,textvariable=st['summary'],wraplength=700,foreground=branding.PALETTE['muted']).grid(row=row,column=0,columnspan=3,sticky='w',pady=(2,0)); row+=1
  ttk.Label(b,text=T['other_hint'],wraplength=700,foreground=branding.PALETTE['muted']).grid(row=row,column=0,columnspan=3,sticky='w',pady=(10,0)); row+=1
  act=ttk.Frame(b); act.grid(row=row,column=0,columnspan=3,sticky='e',pady=(16,0)); ttk.Button(act,text=T['ok'],command=apply).pack(side='right'); ttk.Button(act,text=T['cancel'],command=cancel).pack(side='right',padx=8)
  d.bind('<Escape>',lambda e:cancel()); d.grab_set(); return d
 def _report_options_dialog(self):
  # Report-wide switches, separated from the embedding dialog that used to hold
  # everything in one window: ERLAEUTERUNG pages, subfolders and the output folder.
  T=EMBED_TEXT.get(self.embed_language,EMBED_TEXT['bg'])
  st=self._embed_vars(); d=tk.Toplevel(self); d.title(T['report_title']); d.transient(self); d.geometry('760x430'); d.columnconfigure(0,weight=1)
  snap=(st['explanation'].get(),self.rec.get(),self.custom_output.get(),self.output_folder.get())
  def cancel():
   st['explanation'].set(snap[0]); self.rec.set(snap[1]); self.custom_output.set(snap[2]); self.output_folder.set(snap[3]); d.destroy()
  b=ttk.Frame(d,padding=16); b.pack(fill='both',expand=True); b.columnconfigure(1,weight=1); row=0
  ttk.Label(b,text=T['report_heading'],font=_brand_font(self,11,'bold')).grid(row=row,column=0,columnspan=3,sticky='w',pady=(0,12)); row+=1
  ttk.Checkbutton(b,text=T['explanation'],variable=st['explanation']).grid(row=row,column=0,columnspan=3,sticky='w'); row+=1
  ttk.Checkbutton(b,text=T['recursive'],variable=self.rec).grid(row=row,column=0,columnspan=3,sticky='w'); row+=1
  ttk.Checkbutton(b,text=T['folder'],variable=self.custom_output).grid(row=row,column=0,columnspan=3,sticky='w'); row+=1
  folder_entry=ttk.Entry(b,textvariable=self.output_folder); folder_entry.grid(row=row,column=0,columnspan=2,sticky='ew',pady=(4,0)); folder_browse=ttk.Button(b,text=T['browse'],command=lambda:self._dir(self.output_folder)); folder_browse.grid(row=row,column=2); row+=1
  # The dialog previews the choice, so the folder is only editable when the
  # checkbox above it says the run will use it.
  if hasattr(self,'_gate'):self._gate(self.custom_output,(folder_entry,folder_browse))
  act=ttk.Frame(b); act.grid(row=row,column=0,columnspan=3,sticky='e',pady=(16,0)); ttk.Button(act,text=T['ok'],command=d.destroy).pack(side='right'); ttk.Button(act,text=T['cancel'],command=cancel).pack(side='right',padx=8)
  d.bind('<Escape>',lambda e:cancel()); d.grab_set(); return d
 def _sync_input_mode(self):
  p=Path(self.target.get()).expanduser() if self.target.get() else None
  if p and p.is_file(): self.mode.set('single'); self.rec.set(False); self.mode_label.config(text='Report type: SINGLE (file selected)'); self.rec_check.config(state='disabled')
  elif p and p.is_dir(): self.mode.set('combined'); self.mode_label.config(text='Report type: COMBO (folder selected)'); self.rec_check.config(state='normal')
  else: self.mode_label.config(text='Report type: automatic (File → SINGLE / Folder → COMBO)'); self.rec_check.config(state='normal')
  self._sync_embed_summary()
 def file(self):
  x=filedialog.askopenfilename(); self.target.set(x or self.target.get()); self._sync_input_mode()
 def folder(self):
  x=filedialog.askdirectory(); self.target.set(x or self.target.get()); self._sync_input_mode()
 def _dir(self,var):x=filedialog.askdirectory(); var.set(x or var.get())
 def _exe(self,var):x=filedialog.askopenfilename(filetypes=[('Executable','*.exe'),('All files','*.*')]); var.set(x or var.get())
 def _database_file(self,var):
  x=filedialog.asksaveasfilename(defaultextension='.sqlite3',filetypes=[('SQLite database','*.sqlite3 *.sqlite *.db'),('All files','*.*')])
  var.set(x or var.get())
 def _certs(self,var):
  x=filedialog.askopenfilenames(filetypes=[('Certificates','*.pem *.cer *.crt'),('All files','*.*')]);
  if x:var.set(';'.join(x))
 def write(self,s):s=str(s); self._post(lambda:(self.log.insert('end',s+'\n'),self.log.see('end')))
 def prog(self,n,s):self._post(lambda:(self.pb.configure(value=n),self.status.set(f'{n}% — {s}')))
 def apply_provider(self,stage):
  try:
   name=self.v_sprofile.get() if stage=='start' else self.v_tprofile.get(); apply_profile(self.cfg,stage,name,allow_missing_endpoint=True); p=self.cfg['rfc3161'][stage][0]
   if stage=='start':self.v_surl.set(p.get('url',''));self.v_scert.set(';'.join(p.get('trust_root_files',[])))
   else:self.v_turl.set(p.get('url',''));self.v_tcert.set(';'.join(p.get('trust_root_files',[])))
   save(CFG_PATH,self.cfg); self.write(f'[PROFILE] {stage.upper()} = {name} ({p.get("url")})')
  except Exception as e:messagebox.showerror('ChronoSeal Provider Profile',str(e))
 def autodetect(self):self.v_node.set(executable('node',self.v_node.get()) or ''); self.v_ssl.set(executable('openssl',self.v_ssl.get()) or ''); self.diagnostics(); messagebox.showinfo('ChronoSeal','Windows tool detection completed. Review paths and Save settings.')
 def _sync_cfg(self):
  self.cfg.setdefault('tools',{})['node']=self.v_node.get().strip(); self.cfg['tools']['openssl']=self.v_ssl.get().strip(); self.cfg.setdefault('generator',{})['package_dir']=self.v_gen.get().strip(); p=self.cfg.setdefault('rfc3161',{}); p.setdefault('start',[{'name':'DFN'}]); p.setdefault('stop',[{'name':'DigiCert'}]); p['start'][0]['url']=self.v_surl.get().strip(); p['start'][0]['trust_root_files']=[x.strip() for x in self.v_scert.get().split(';') if x.strip()]; p['stop'][0]['url']=self.v_turl.get().strip(); p['stop'][0]['trust_root_files']=[x.strip() for x in self.v_tcert.get().split(';') if x.strip()]; archive=self.cfg.setdefault('archive',{}); archive['enabled']=self.v_archive_enabled.get(); archive['directory']=self.v_archive_dir.get().strip(); archive['database']=self.v_archive_db.get().strip(); save(CFG_PATH,self.cfg)
 def save_settings(self):self._sync_cfg(); messagebox.showinfo('ChronoSeal','Settings saved.')
 def save_settings_silent(self):self._sync_cfg()
 def diagnostics(self):
  self.save_settings_silent(); lines=[]
  for name,val in [('Python',os.sys.executable),('Node',executable('node',self.v_node.get())),('OpenSSL',executable('openssl',self.v_ssl.get())),('Generator package',self.v_gen.get() or None)]:lines.append(f'{name}: {val or "NOT FOUND / NOT SET"}')
  if self.target.get():
   try:
    self._sync_input_mode(); info,issues,w=Pipeline(BASE,self.cfg).preflight(self.target.get(),self.mode.get()); lines += ['','Preflight:',json.dumps(info,indent=2,ensure_ascii=False)]; lines += [f'BLOCKER: {x}' for x in issues]; lines += [f'WARNING: {x}' for x in w]
   except Exception as e:lines.append(f'Preflight error: {e}')
  self.diag.delete('1.0','end'); self.diag.insert('end','\n'.join(lines))
 def _bootstrap_trust_core(self,ssl_hint):
  # UI-free: no Tk access; returns (report,new_cfg) for the caller to apply on the main thread.
  sslbin=executable('openssl',ssl_hint)
  if not sslbin: raise BootstrapError('OpenSSL is required for TSA trust bootstrap')
  report,cfg=bootstrap_providers(BASE,copy.deepcopy(self.cfg),sslbin); save(CFG_PATH,cfg); return report,cfg
 def _apply_bootstrap_cfg(self,cfg):
  self.cfg=cfg; p=cfg.get('rfc3161',{}); self.v_scert.set(';'.join((p.get('start') or [{}])[0].get('trust_root_files',[]))); self.v_tcert.set(';'.join((p.get('stop') or [{}])[0].get('trust_root_files',[])))
 def bootstrap_trust(self, silent=False):
  self.save_settings_silent()
  if not executable('openssl',self.v_ssl.get()):
   if silent: raise BootstrapError('OpenSSL is required for TSA trust bootstrap')
   return messagebox.showerror('ChronoSeal','OpenSSL is required for TSA trust bootstrap.')
  try:
   report,cfg=self._bootstrap_trust_core(self.v_ssl.get()); self._apply_bootstrap_cfg(cfg)
   self.write('[TRUST] '+json.dumps(report,ensure_ascii=False))
   if not silent: messagebox.showinfo('ChronoSeal','TSA trust bootstrap PASS. Certificate chains were validated and saved locally.')
   return report
  except Exception as e:
   if silent: raise
   messagebox.showerror('ChronoSeal',f'TSA trust bootstrap BLOCKED:\n\n{e}')
 def preflight_only(self):
  self.save_settings_silent()
  if not self.target.get():return messagebox.showerror('ChronoSeal','Select input on the Run tab first.')
  self._sync_input_mode(); _,issues,_=Pipeline(BASE,self.cfg).preflight(self.target.get(),self.mode.get()); self.diagnostics(); messagebox.showinfo('ChronoSeal Preflight','PASS' if not issues else 'BLOCKED\n\n'+'\n'.join(issues))
 def start(self):
  if not self.startup_ready:return messagebox.showerror('ChronoSeal','Startup qualification has not passed. Resolve Setup/Diagnostics blockers first.')
  if not self.target.get():return messagebox.showerror('ChronoSeal','Select input first.')
  self._sync_input_mode()
  if self.custom_output.get() and not Path(self.output_folder.get()).expanduser().is_dir():return messagebox.showerror('ChronoSeal','Select an existing output folder.')
  try:embed=self._resolve_embed()
  except ValueError as exc:return messagebox.showerror('ChronoSeal — PDF вграждане',str(exc))
  self.include_explanation=embed['explanation']; self.include_source_pdf=embed['source_pdf']; self.embed_pdf=embed['pdf']; self.embed_position=embed['position']
  self.save_settings_silent(); self.log.delete('1.0','end'); self.pb['value']=0; self.cancel.clear(); self._run_args=(self.target.get(),self.mode.get(),self.rec.get(),self.include_explanation,self.include_source_pdf,self.output_folder.get().strip() if self.custom_output.get() else None,(getattr(self,'file_filters',[]) or []) if self.mode.get()=='combined' else [],(getattr(self,'file_selection',[]) or []),self.embed_pdf,self.embed_position); self._run_ssl=self.v_ssl.get(); self.go.config(state='disabled'); self.stop.config(state='normal'); threading.Thread(target=self.worker,daemon=True).start()
 def cancel_run(self):self.cancel.set(); self.status.set('Cancellation requested…')
 def worker(self):
  logroot=BASE/'logs'; self.session=SessionLogger(logroot,self.write); self.session.snapshot(BASE,self.cfg)
  try:
   pol=self.cfg.get('rfc3161',{}); need_trust=any(not (p.get('trust_root_files') or []) for stage in ('start','stop') for p in pol.get(stage,[]))
   if need_trust:
    self.session.write('[TRUST] Missing TSA trust material — automatic bootstrap started')
    report,cfg=self._bootstrap_trust_core(self._run_ssl); self._call_main(lambda:self._apply_bootstrap_cfg(cfg)); self.session.write('[TRUST] '+json.dumps(report,ensure_ascii=False)); self.session.write('[TRUST] automatic bootstrap PASS')
   result=Pipeline(BASE,self.cfg,self.session.write,self.session,self.prog,self.cancel).run(*self._run_args); self.last_result=result; self.session.write('FINAL PASS'); self._post(lambda:messagebox.showinfo('ChronoSeal','PASS\n\n'+result['final_pdf']))
  except Exception as e:
   self.session.error(e); title='CANCELLED' if isinstance(e,Cancelled) else 'BLOCKED'; self._post(lambda e=e,title=title:(self.status.set(title),self._copyable_error('ChronoSeal',f'{title}\n\n{e}\n\nFull log: {self.session.dir}')))
  finally:self._post(lambda:(self.go.config(state='normal' if self.startup_ready else 'disabled'),self.stop.config(state='disabled')))
 def open_logs(self):
  p=self.session.dir if self.session else BASE/'logs'; p.mkdir(parents=True,exist_ok=True); os.startfile(p) if os.name=='nt' else subprocess.Popen(['xdg-open',str(p)])
 def open_evidence(self):
  if not self.target.get():return
  t=Path(self.target.get()).expanduser(); p=(t if t.is_dir() else t.parent)/'ChronoSeal_Evidence'; p.mkdir(parents=True,exist_ok=True); os.startfile(p) if os.name=='nt' else subprocess.Popen(['xdg-open',str(p)])
def main():
 from chronoseal import i18n
 i18n.install()
 app=App()
 i18n.add_language_selector(app,app,side='top',anchor='e')
 app.mainloop()
if __name__=='__main__':main()
