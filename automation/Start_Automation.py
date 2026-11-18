"""Separate automation window. Does not modify original ChronoSeal GUI."""
import sys,threading,queue,json,time
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(BASE))
from automation_core import plan, execute
from chronoseal import branding, i18n
i18n.install()

def bg(text):
 return i18n.translate(text,'bg')

class App:
 def __init__(self,root,parent=None):
  self.root=root;self.parent=parent
  if parent is None:
   root.title('ChronoSeal Automation');root.geometry('950x700')
  self.started_at=None;self.completed=0;self.total=0;self.failed=0
  self.source=tk.StringVar();self.mode=tk.StringVar(value='COMBO_FOLDER');self.state=tk.StringVar(value='Готов');self.events=queue.Queue();self.cancel=threading.Event();self.thread=None
  frm=ttk.Frame(parent if parent is not None else root,padding=12);frm.pack(fill='both',expand=True)
  ttk.Label(frm,text='AUTOMATIC REPORTS',style='WorkspaceTitle.TLabel').pack(anchor='w',pady=(0,5))
  ttk.Label(frm,text='Самостоятелен функционален блок · планиране, изпълнение, TSA и отчетност',style='Muted.TLabel').pack(anchor='w',pady=(0,14))
  self.summary_files=tk.StringVar(value='0 заредени файла')
  self.summary_bytes=tk.StringVar(value='0 B общ размер')
  self.summary_jobs=tk.StringVar(value='0 обработени задачи')
  cards=ttk.Frame(frm);cards.pack(fill='x',pady=(0,12))
  for title,var in [('ФАЙЛОВЕ',self.summary_files),('ОБЕМ',self.summary_bytes),('ИЗПЪЛНЕНИЕ',self.summary_jobs)]:
   card=ttk.LabelFrame(cards,text=title,style='Panel.TLabelframe');card.pack(side='left',fill='x',expand=True,padx=(0,8))
   ttk.Label(card,textvariable=var,style='Section.TLabel').pack(anchor='w',padx=10,pady=(6,8))
  r=ttk.Frame(frm);r.pack(fill='x');ttk.Label(r,text='Директория:').pack(side='left');ttk.Entry(r,textvariable=self.source).pack(side='left',fill='x',expand=True,padx=8);ttk.Button(r,text='Избери…',command=self.pick).pack(side='left')
  self.report_type=tk.StringVar(value='Комбиниран отчет')
  self.mode_display=tk.StringVar()
  self.mode=tk.StringVar()
  self.mode_labels={
   'COMBINED': {
    'Един общ отчет за всички файлове в избраната папка':'COMBO_FOLDER',
    'Един общ отчет за папката и всички подпапки':'COMBO_RECURSIVE',
    'Един общ отчет само за избрани файлове':'COMBO_SELECTED',
   },
   'INDIVIDUAL': {
    'Отделен отчет за всеки файл в избраната папка':'SINGLE_FOLDER',
    'Отделен отчет само за избраните файлове':'SINGLE_SELECTED',
   },
   'BOTH': {
    'Отделни отчети и един общ отчет за папката':'SINGLE_AND_COMBO',
    'Отделни отчети и един общ отчет само за избрани файлове':'SINGLE_AND_COMBO_SELECTED',
   },
  }
  self.categories={
   'Комбиниран отчет':'COMBINED',
   'Индивидуален отчет':'INDIVIDUAL',
   'Комбиниран и индивидуален отчет':'BOTH',
  }
  r=ttk.Frame(frm);r.pack(fill='x',pady=(12,5))
  ttk.Label(r,text='1. Вид на отчета:').pack(side='left')
  self.type_combo=ttk.Combobox(r,textvariable=self.report_type,values=[i18n.tr(x) for x in self.categories],state='readonly',width=49)
  self.type_combo.pack(side='left',padx=8,fill='x',expand=True)
  self.type_combo.bind('<<ComboboxSelected>>',self.on_category_change)
  r=ttk.Frame(frm);r.pack(fill='x',pady=(3,10))
  ttk.Label(r,text='2. Автоматизация:').pack(side='left')
  self.mode_combo=ttk.Combobox(r,textvariable=self.mode_display,state='readonly',width=74)
  self.mode_combo.pack(side='left',padx=8,fill='x',expand=True)
  self.mode_combo.bind('<<ComboboxSelected>>',self.on_mode_change)
  self.description=tk.StringVar()
  ttk.Label(frm,textvariable=self.description,wraplength=860,justify='left').pack(anchor='w',pady=(0,8))
  self.selection_frame=ttk.LabelFrame(frm,text='Избор на файлове (Ctrl/Shift)',style='Panel.TLabelframe')
  self.selection_frame.pack(fill='x',pady=(0,8))
  sel=ttk.Frame(self.selection_frame);sel.pack(fill='both',expand=True,padx=6,pady=6)
  self.loaded_files=[]
  self.files=tk.Listbox(sel,selectmode=tk.EXTENDED,height=8,exportselection=False)
  self.files.pack(side='left',fill='both',expand=True)
  self.files.configure(background=branding.PALETTE['console_bg'],foreground=branding.PALETTE['console_fg'],selectbackground=branding.PALETTE['accent'],selectforeground=branding.PALETTE['on_accent'],font=branding.FontBook(self.files).font(10),borderwidth=0,highlightthickness=0,activestyle='none')
  scroll=ttk.Scrollbar(sel,command=self.files.yview);scroll.pack(side='right',fill='y');self.files.config(yscrollcommand=scroll.set)
  controls=ttk.Frame(self.selection_frame);controls.pack(fill='x',padx=6,pady=(0,6))
  ttk.Button(controls,text='Добави файлове…',command=self.add_files).pack(side='left')
  ttk.Button(controls,text='Премахни маркираните',command=self.remove_files).pack(side='left',padx=6)
  ttk.Button(controls,text='Изчисти списъка',command=self.clear_files).pack(side='left')
  self.mode_settings=ttk.LabelFrame(frm,text='Настройки на избрания режим',style='Panel.TLabelframe')
  self.mode_settings.pack(fill='x',pady=(0,8))
  self.on_category_change()
  r=ttk.Frame(frm);r.pack(fill='x',pady=10)
  self.start=ttk.Button(r,text='▶ Старт',command=self.start_run,style='Accent.TButton');self.start.pack(side='left')
  ttk.Button(r,text='Покажи плана',command=self.preview).pack(side='left',padx=8)
  self.stop=ttk.Button(r,text='■ Спри',command=self.stop_run,state='disabled');self.stop.pack(side='left')
  ttk.Label(r,textvariable=self.state).pack(side='right')
  progress_panel=ttk.LabelFrame(frm,text='Мониторинг в реално време',style='Panel.TLabelframe')
  progress_panel.pack(fill='x',pady=(0,8))
  self.progress=ttk.Progressbar(progress_panel,maximum=100,mode='determinate')
  self.progress.pack(fill='x',padx=10,pady=(8,4))
  self.metrics=tk.StringVar(value='0 / 0 задачи  •  0 успешни  •  0 неуспешни')
  ttk.Label(progress_panel,textvariable=self.metrics).pack(anchor='w',padx=10,pady=(0,8))
  ttk.Label(frm,text='Дневник на изпълнението:').pack(anchor='w')
  logrow=ttk.Frame(frm);logrow.pack(fill='both',expand=True)
  self.log=tk.Text(logrow,height=10,state='disabled',wrap='word',background=branding.PALETTE['console_bg'],foreground=branding.PALETTE['console_fg'],insertbackground=branding.PALETTE['on_accent'],font=branding.FontBook(logrow).font(10,role='mono'),relief='flat');self.log.pack(side='left',fill='both',expand=True)
  logscroll=ttk.Scrollbar(logrow,orient='vertical',command=self.log.yview);logscroll.pack(side='right',fill='y');self.log.configure(yscrollcommand=logscroll.set)
  ttk.Label(frm,text='Всяка задача използва оригиналния Pipeline и задължителните TSA START/STOP проверки. Неуспешна задача не се отбелязва като PASS.',wraplength=900).pack(anchor='w',pady=8)
  self.source.trace_add('write',lambda *_:self.clear_files());self.root.after(100,self.poll)
  self.report_type.set(i18n.tr('Комбиниран отчет'));self.on_category_change()
  i18n.on_change(self._lang_changed)
  if parent is None:self.root.protocol('WM_DELETE_WINDOW',self.close)
 def _lang_changed(self):
  try:
   self.type_combo.configure(values=[i18n.tr(x) for x in self.categories])
   self.on_category_change_keep()
  except tk.TclError:pass
 def on_category_change_keep(self):
  category=self.categories[bg(self.report_type.get())]
  mode_bg=next((k for k,v in self.mode_labels[category].items() if v==self.mode.get()),None)
  self.mode_combo.configure(values=[i18n.tr(x) for x in self.mode_labels[category]])
  if mode_bg:self.mode_display.set(i18n.tr(mode_bg))
  self.on_mode_change()
 def on_category_change(self,event=None):
  category=self.categories[bg(self.report_type.get())]
  labels=list(self.mode_labels[category])
  self.mode_combo.configure(values=[i18n.tr(x) for x in labels])
  self.mode_display.set(i18n.tr(labels[0]))
  self.on_mode_change()
 def on_mode_change(self,event=None):
  category=self.categories[bg(self.report_type.get())]
  mode=self.mode_labels[category][bg(self.mode_display.get())]
  self.mode.set(mode)
  for widget in self.mode_settings.winfo_children():widget.destroy()
  self.files.selection_clear(0,'end')
  selected=mode in ('SINGLE_SELECTED','COMBO_SELECTED','SINGLE_AND_COMBO_SELECTED')
  if selected:
   self.selection_frame.pack(fill='x',pady=(0,8),before=self.mode_settings)
   self.refresh_files()
  else:self.selection_frame.pack_forget()
  descriptions={
   'SINGLE_SELECTED':'Отделен отчет с TSA за всеки маркиран файл. Другите файлове се пропускат.',
   'SINGLE_FOLDER':'Отделен отчет с TSA за всеки файл от текущата папка.',
   'COMBO_FOLDER':'Един комбиниран отчет с TSA за текущата папка.',
   'COMBO_RECURSIVE':'Един комбиниран отчет с TSA за папката и подпапките.',
   'COMBO_SELECTED':'Един комбиниран отчет само за маркираните файлове; за изпълнението се използва временна работна папка с копия.',
   'SINGLE_AND_COMBO':'Отделни отчети за файловете и един комбиниран отчет за папката.',
   'SINGLE_AND_COMBO_SELECTED':'Отделни отчети и един комбиниран отчет само за маркираните файлове.',
  }
  self.description.set(descriptions[mode])
  ttk.Label(self.mode_settings,text=('Добавете конкретните файлове с бутона „Добави файлове…“. Панелът показва само заредените файлове.' if selected else 'Обработката използва зададената директория.'),wraplength=770).pack(anchor='w',padx=6,pady=5)
  self.state.set(i18n.tr('Готов за {mode}',mode=self.mode_display.get()))
 def pick(self):
  p=filedialog.askdirectory();
  if p:self.source.set(p)
 def refresh_files(self):
  """Render only explicitly loaded files; never scan the directory."""
  self.files.delete(0,'end')
  total_bytes=0
  for path in self.loaded_files:
   try:
    size=path.stat().st_size
    total_bytes+=size
    detail=f'{size / 1048576:,.2f} MB'
   except OSError:detail=i18n.tr('липсва / недостъпен')
   self.files.insert('end',f'{path.name}   |   {detail}   |   {path}')
  self.summary_files.set(f'{len(self.loaded_files)} заредени файла')
  self.summary_bytes.set(f'{total_bytes / 1048576:,.2f} MB общ размер')
 def add_files(self):
  folder=self.source.get().strip()
  chosen=filedialog.askopenfilenames(parent=self.root,title='Добави файлове за отчета',initialdir=folder if Path(folder).is_dir() else None)
  if not chosen:return
  paths=[Path(name).expanduser().resolve() for name in chosen]
  # The existing Selected COMBO planner requires all files in one folder.
  parents={p.parent for p in paths}
  if len(parents)!=1:
   messagebox.showerror('ChronoSeal','Изберете файлове от една директория.');return
  parent=next(iter(parents))
  current=Path(self.source.get()).expanduser().resolve() if self.source.get().strip() else None
  if current!=parent:
   if self.loaded_files and not messagebox.askyesno('Нова директория','Файловете са от друга папка. Да се замени текущият списък?'):return
   self.source.set(str(parent)) # clears prior selection
  existing=set(self.loaded_files)
  for path in paths:
   if path.is_file() and path not in existing:
    self.loaded_files.append(path);existing.add(path)
  self.refresh_files()
 def remove_files(self):
  indices=set(self.files.curselection())
  self.loaded_files=[p for i,p in enumerate(self.loaded_files) if i not in indices]
  self.refresh_files()
 def clear_files(self):
  self.loaded_files=[]
  self.refresh_files()
 def jobs(self):
  src=Path(self.source.get())
  selected=[str(p) for p in self.loaded_files]
  if self.mode.get() in ('SINGLE_SELECTED','COMBO_SELECTED','SINGLE_AND_COMBO_SELECTED') and not selected:
   raise ValueError('Добавете поне един файл чрез „Добави файлове…“.')
  return plan(src,self.mode.get(),selected)
 def write(self,s):
  self.log.config(state='normal');self.log.insert('end',str(s)+'\n');self.log.see('end');self.log.config(state='disabled')
 def preview(self):
  try:
   jobs=self.jobs();self.write(f'План: {len(jobs)} задачи')
   for target,mode,recursive in jobs:self.write(f'  {mode} recursive={recursive} — {target}')
  except Exception as exc:messagebox.showerror('Невалиден план',str(exc))
 def start_run(self):
  if self.thread and self.thread.is_alive():return
  try:jobs=self.jobs()
  except Exception as exc:messagebox.showerror('Невалиден план',str(exc));return
  if not messagebox.askyesno('Потвърждение',f'Да започнат ли {len(jobs)} задачи със задължителен TSA?'):return
  self.cancel.clear();self.completed=0;self.failed=0;self.total=len(jobs);self.summary_jobs.set(f'0 / {self.total} задачи');self.started_at=time.monotonic();self.progress.configure(value=0);self.metrics.set(f'0 / {self.total} задачи  •  0 успешни  •  0 неуспешни');self.start.config(state='disabled');self.stop.config(state='normal');self.state.set('Работи…')
  def worker():
   # The UI is only re-enabled by the 'done' event, so every failure path must
   # still publish one; otherwise a crashed worker leaves the window locked.
   results=[];filename=None;error=None
   try:
    results=execute(BASE,jobs,self.cancel,lambda msg:self.events.put(('log',msg)))
    path=HERE/'logs';path.mkdir(exist_ok=True)
    filename=path/('run_'+time.strftime('%Y%m%d_%H%M%S')+'.json')
    filename.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
   except Exception as exc:error=exc
   finally:self.events.put(('done',(results,str(filename) if filename else '',str(error) if error else '')))
  self.thread=threading.Thread(target=worker,daemon=True);self.thread.start()
 def stop_run(self):
  self.cancel.set();self.state.set('Спиране…');self.write('Изпратена заявка за прекратяване')
 def poll(self):
  try:
   while True:
    kind,value=self.events.get_nowait()
    if kind=='log':
     self.write(value)
     # Update completed-job progress as events arrive, not only at the end.
     if value.startswith('[') and ('] PASS ' in value or '] FAILED ' in value):
      self.completed+=1
      self.summary_jobs.set(f'{self.completed} / {self.total} задачи')
      if '] FAILED ' in value:self.failed+=1
      self.progress.configure(value=100*self.completed/max(1,self.total))
      elapsed=time.monotonic()-self.started_at if self.started_at else 0
      self.metrics.set(f'{self.completed} / {self.total} задачи  •  {self.completed-self.failed} успешни  •  {self.failed} неуспешни  •  {elapsed:.1f} s')
      self.state.set(f'Обработени {self.completed}/{self.total}')
    elif kind=='done':
     results,path,error=value
     passed=sum(x.get('status')=='PASS' for x in results)
     self.completed=len(results);self.failed=len(results)-passed
     self.summary_jobs.set(f'{self.completed} / {self.total} задачи')
     self.progress.configure(value=100 if self.total and self.completed>=self.total else (100*self.completed/max(1,self.total)))
     elapsed=time.monotonic()-self.started_at if self.started_at else 0
     self.metrics.set(f'{self.completed} / {self.total} задачи  •  {passed} успешни  •  {self.failed} неуспешни  •  {elapsed:.1f} s')
     if error:self.write('ГРЕШКА: '+error);self.state.set('Грешка при изпълнение')
     else:self.write('Резултати: '+path);self.state.set(f'Готово: {passed}/{len(results)} PASS')
     self.start.config(state='normal');self.stop.config(state='disabled')
  except queue.Empty:pass
  self.root.after(100,self.poll)
 def close(self):
  if self.thread and self.thread.is_alive():messagebox.showwarning('Активна задача','Първо натиснете Спри и изчакайте приключването.');return
  self.root.destroy()
if __name__=='__main__':
 root=tk.Tk();App(root)
 i18n.add_language_selector(root,root,side='top',anchor='e')
 root.mainloop()
