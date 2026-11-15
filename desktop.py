"""Native desktop presentation. Legacy generator is isolated and unchanged."""
import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QFileDialog, QPlainTextEdit, QMessageBox,
    QComboBox, QTableWidget, QTableWidgetItem, QSpinBox, QSplitter, QLineEdit,
    QFormLayout, QGroupBox, QCheckBox, QHeaderView, QTabWidget, QScrollArea)

DARK = '''
QWidget { background: #0b1422; color: #e8f1ff; font-family: 'Segoe UI'; font-size: 11pt; }
QFrame#sidebar { background: #101e32; border-right: 1px solid #243a54; }
QFrame#panel, QGroupBox { background: #14243a; border: 1px solid #29425f; border-radius: 10px; }
QGroupBox { margin-top: 12px; padding: 16px 10px 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; }
QPushButton { background: #1b304c; border: 1px solid #335375; border-radius: 7px; padding: 10px 13px; text-align: left; }
QPushButton:hover { background: #29476b; }
QPushButton#primary { background: #1264d6; border-color: #3488ff; font-weight: 700; }
QPushButton#nav { border: 0; background: transparent; padding: 13px; }
QPushButton#nav:checked { background: #17478c; }
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QTableWidget { background: #0c192b; border: 1px solid #34506d; border-radius: 6px; padding: 5px; }
QHeaderView::section { background: #1b304c; color: #e8f1ff; padding: 7px; border: 0; }
QTabBar::tab { background: #1b304c; padding: 10px 15px; }
QTabBar::tab:selected { background: #1264d6; }
'''
LIGHT = '''
QWidget { background: #f4f7fb; color: #192b40; font-family: 'Segoe UI'; font-size: 11pt; }
QFrame#sidebar { background: #e7eef7; border-right: 1px solid #c5d3e4; }
QFrame#panel, QGroupBox { background: #fff; border: 1px solid #c5d3e4; border-radius: 10px; }
QGroupBox { margin-top: 12px; padding: 16px 10px 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; }
QPushButton { background: #e0e9f6; border: 1px solid #b7c8dd; border-radius: 7px; padding: 10px 13px; text-align: left; }
QPushButton:hover { background: #cddff5; }
QPushButton#primary { background: #1264d6; color: white; font-weight: 700; }
QPushButton#nav { border: 0; background: transparent; padding: 13px; }
QPushButton#nav:checked { background: #b7d6ff; }
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QTableWidget { background: white; border: 1px solid #b7c8dd; border-radius: 6px; padding: 5px; }
QHeaderView::section { background: #e0e9f6; padding: 7px; border: 0; }
QTabBar::tab { background: #e0e9f6; padding: 10px 15px; }
QTabBar::tab:selected { background: #b7d6ff; }
'''

class MainWindow(QMainWindow):
    def __init__(self, root):
        super().__init__()
        self.root = Path(root)
        self.config_path = self.root / 'desktop-settings.json'
        self.config = self.load_config()
        self.setWindowTitle('ChronoSeal Enterprise | Native Desktop')
        self.resize(1500, 920)
        self.setMinimumSize(960, 620)
        host = QWidget(); self.setCentralWidget(host)
        layout = QHBoxLayout(host); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        side = QFrame(); side.setObjectName('sidebar'); side.setFixedWidth(255)
        s = QVBoxLayout(side); s.setContentsMargins(14, 22, 14, 16)
        title = QLabel('◆  ChronoSeal'); title.setStyleSheet('font-size: 21pt; font-weight: 800;')
        s.addWidget(title)
        sub = QLabel('ENTERPRISE  •  HASH REPORT'); sub.setStyleSheet('font-size: 9pt;')
        s.addWidget(sub); s.addSpacing(24)
        self.pages = QStackedWidget(); self.nav = []
        definitions = [('Генератор / Report & TSA', self.generator_page),
                       ('Automation', self.automation_page),
                       ('Settings & Trust', self.trust_page),
                       ('Diagnostics', self.diagnostics_page),
                       ('Process Manifest Studio', self.manifest_page),
                       ('JSON Transform', self.json_page),
                       ('Visual Packages', self.visual_page)]
        for index, (name, factory) in enumerate(definitions):
            b = QPushButton(name); b.setObjectName('nav'); b.setCheckable(True)
            b.clicked.connect(lambda _, i=index: self.select(i))
            s.addWidget(b); self.nav.append(b)
            self.pages.addWidget(factory())
        s.addStretch()
        s.addWidget(QLabel('Нативен Qt • без WebView / HTTP'))
        layout.addWidget(side); layout.addWidget(self.pages, 1)
        self.statusBar().showMessage('Съществуващият Python engine остава непроменен')
        self.apply_theme()
        self.select(0)

    def load_config(self):
        try: return json.loads(self.config_path.read_text(encoding='utf-8'))
        except (OSError, ValueError): return {'theme': 'dark', 'font_size': 11}

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding='utf-8')

    def apply_theme(self):
        self.setStyleSheet((LIGHT if self.config.get('theme') == 'light' else DARK).replace('11pt', f"{self.config.get('font_size',11)}pt"))

    def select(self, i):
        self.pages.setCurrentIndex(i)
        for j, b in enumerate(self.nav): b.setChecked(j == i)

    def page(self, heading, subtitle):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(25, 22, 25, 20); v.setSpacing(13)
        h = QLabel(heading); h.setStyleSheet('font-size: 21pt; font-weight: 750;')
        v.addWidget(h); v.addWidget(QLabel(subtitle))
        return w, v

    def panel(self, label, details, button_label=None, callback=None):
        g = QGroupBox(label); v = QVBoxLayout(g)
        t = QLabel(details); t.setWordWrap(True); v.addWidget(t)
        if button_label:
            b = QPushButton(button_label); b.setObjectName('primary')
            b.clicked.connect(callback); v.addWidget(b)
        return g

    def legacy_candidates(self):
        return [self.root / 'ChronoSeal_GUI.pyw', self.root / 'ChronoSeal_Original_Legacy.py',
                self.root.parent / 'ChronoSeal_GUI.pyw', self.root.parent / 'ChronoSeal_Original_Legacy.py']

    def launch_legacy(self):
        target = next((p for p in self.legacy_candidates() if p.is_file()), None)
        if target is None:
            QMessageBox.warning(self, 'Липсва оригиналният проект', 'Поставете start-new.pyw в основната директория на оригиналния проект, заедно с desktop.py. Необходим е ChronoSeal_GUI.pyw или ChronoSeal_Original_Legacy.py.')
            return
        try:
            # A separate process ensures Qt never modifies Tkinter state or legacy engine.
            subprocess.Popen([sys.executable, str(target)], cwd=str(target.parent), close_fds=True)
            self.statusBar().showMessage(f'Оригинален интерфейс: {target.name}')
        except OSError as e:
            QMessageBox.critical(self, 'Стартиране', str(e))

    def generator_page(self):
        w,v=self.page('Report & TSA','Оригинален генератор • SINGLE / COMBO / SINGLE_PDF / COMBO_ALL')
        v.addWidget(self.panel('Съществуващ генератор', 'Файлове и папки, HASH изчисления, RFC 3161 START/STOP, PDF и проверка. За да не се промени работещата логика, отваря оригиналния интерфейс в отделен процес.', 'Отвори оригиналния Report & TSA', self.launch_legacy))
        v.addWidget(self.panel('Нова архитектура', 'Qt е само интерфейсен слой. Не се прихващат и не се симулират действията на оригиналния генератор.'))
        v.addStretch(); return w

    def automation_page(self):
        w,v=self.page('Automation','Запазва се оригиналният automation/Start_Automation.py')
        v.addWidget(self.panel('Automation • legacy', 'Отваря оригиналния workspace, където Automation остава свързан към съществуващия Python модул.', 'Отвори Automation в оригиналния GUI', self.launch_legacy)); v.addStretch(); return w

    def trust_page(self):
        w,v=self.page('Settings & Trust','Оригиналните TSA настройки и trust профили не се изменят')
        v.addWidget(self.panel('Trust configuration', 'Оригиналните настройки се отварят в съществуващия GUI. Новият интерфейс не презаписва TSA или certificate настройки.', 'Отвори оригиналните настройки', self.launch_legacy)); v.addStretch(); return w

    def diagnostics_page(self):
        w,v=self.page('Diagnostics','Проверка и логове от съществуващата система')
        v.addWidget(self.panel('Диагностика', 'Действителните preflight проверки и evidence logs остават в оригиналния модул.', 'Отвори оригиналната диагностика', self.launch_legacy)); v.addStretch(); return w

    def manifest_page(self):
        w,v=self.page('Process Manifest Studio','Планиран модул • няма достъп до RFC 3161 engine')
        v.addWidget(self.panel('START → Process Manifest → STOP', 'Редактира се само проектен JSON. Няма изпълнение на трансформации в доказателствения процес и няма промяна на подписани документи.'))
        row=QHBoxLayout(); self.manifest_file=QLineEdit(); self.manifest_file.setPlaceholderText('Път до manifest JSON')
        row.addWidget(self.manifest_file,1)
        for label,fn in [('Зареди',self.open_manifest),('Запази като',self.save_manifest),('Валидирай JSON',self.validate_manifest)]:
            b=QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        v.addLayout(row)
        self.manifest_edit=QPlainTextEdit(); self.manifest_edit.setPlainText(json.dumps({
            'schema_version': 'draft-1', 'name': 'Custom HASH report',
            'source': {'type': 'file_or_folder'},
            'process': [{'id':'extract_metadata','enabled':True}, {'id':'hash_files','enabled':True}],
            'output': {'sections': ['system_information','volume','user_information','file_hashes']}
        },ensure_ascii=False,indent=2))
        v.addWidget(self.manifest_edit,1)
        return w

    def validate_manifest(self):
        try:
            data=json.loads(self.manifest_edit.toPlainText())
            if not isinstance(data,dict): raise ValueError('Root must be an object')
            QMessageBox.information(self,'JSON','Валиден JSON синтаксис. Това НЕ е валидация на изпълним процес.')
        except (ValueError, json.JSONDecodeError) as e: QMessageBox.warning(self,'JSON',str(e))

    def open_manifest(self):
        path,_=QFileDialog.getOpenFileName(self,'Зареди манифест','','JSON (*.json)')
        if path:
            try:
                raw=Path(path).read_text(encoding='utf-8'); json.loads(raw)
                self.manifest_edit.setPlainText(raw); self.manifest_file.setText(path)
            except (OSError,ValueError) as e: QMessageBox.warning(self,'JSON',str(e))

    def save_manifest(self):
        try: json.loads(self.manifest_edit.toPlainText())
        except ValueError as e: QMessageBox.warning(self,'JSON',str(e)); return
        path,_=QFileDialog.getSaveFileName(self,'Запази манифест',self.manifest_file.text() or 'process-manifest.json','JSON (*.json)')
        if path:
            try: Path(path).write_text(self.manifest_edit.toPlainText(),encoding='utf-8'); self.manifest_file.setText(path)
            except OSError as e: QMessageBox.warning(self,'Запис',str(e))

    def json_page(self):
        w,v=self.page('JSON Transform','Локално визуализиране на JSON масив като таблица • без промяна на оригиналния файл')
        row=QHBoxLayout()
        b=QPushButton('Зареди JSON'); b.clicked.connect(self.open_json); row.addWidget(b)
        b=QPushButton('Преглед като таблица'); b.setObjectName('primary'); b.clicked.connect(self.preview_json); row.addWidget(b)
        row.addStretch(); v.addLayout(row)
        splitter=QSplitter(Qt.Orientation.Vertical)
        self.json_edit=QPlainTextEdit(); self.json_edit.setPlaceholderText('Постави JSON обект или масив...')
        splitter.addWidget(self.json_edit)
        self.json_table=QTableWidget(); self.json_table.setAlternatingRowColors(True)
        splitter.addWidget(self.json_table); splitter.setSizes([280,400]); v.addWidget(splitter,1)
        return w

    def open_json(self):
        path,_=QFileDialog.getOpenFileName(self,'Зареди JSON','','JSON (*.json);;Всички файлове (*)')
        if path:
            try:
                p=Path(path)
                if p.stat().st_size>20*1024*1024: raise ValueError('Файлът е над лимита 20 MB за визуален преглед')
                self.json_edit.setPlainText(p.read_text(encoding='utf-8'))
            except (OSError,ValueError) as e: QMessageBox.warning(self,'JSON',str(e))

    def preview_json(self):
        try:
            data=json.loads(self.json_edit.toPlainText())
            if isinstance(data,dict):
                arrays=[value for value in data.values() if isinstance(value,list)]
                data=arrays[0] if arrays else [data]
            if not isinstance(data,list): data=[{'value':data}]
            if len(data)>2000: raise ValueError('Прегледът е ограничен до 2000 реда')
            rows=[r if isinstance(r,dict) else {'value':r} for r in data]
            keys=list(dict.fromkeys(k for r in rows for k in r.keys()))
            if len(keys)>100: raise ValueError('Прегледът е ограничен до 100 колони')
            self.json_table.setUpdatesEnabled(False)
            self.json_table.clear(); self.json_table.setRowCount(len(rows)); self.json_table.setColumnCount(len(keys)); self.json_table.setHorizontalHeaderLabels(keys)
            for i,r in enumerate(rows):
                for j,k in enumerate(keys):
                    value=r.get(k,'')
                    self.json_table.setItem(i,j,QTableWidgetItem(json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value)))
            self.json_table.setUpdatesEnabled(True)
            self.statusBar().showMessage(f'JSON preview: {len(rows)} реда, {len(keys)} колони')
        except (ValueError,TypeError) as e:
            self.json_table.setUpdatesEnabled(True)
            QMessageBox.warning(self,'JSON',str(e))

    def visual_page(self):
        w,v=self.page('Visual Packages','Настройки на новия desktop интерфейс • PDF CSS остава непроменен')
        g=QGroupBox('Desktop appearance'); form=QFormLayout(g)
        theme=QComboBox(); theme.addItems(['dark','light']); theme.setCurrentText(self.config.get('theme','dark'))
        theme.currentTextChanged.connect(lambda value: self.set_setting('theme',value))
        form.addRow('Тема',theme)
        size=QSpinBox(); size.setRange(9,18); size.setValue(self.config.get('font_size',11))
        size.valueChanged.connect(lambda value: self.set_setting('font_size',value))
        form.addRow('Размер на шрифта (pt)',size)
        v.addWidget(g)
        v.addWidget(self.panel('Visual package manifest • планирано', 'Зареждане на външни пакети, цветови токени, A4 правила и настройка на PDF шаблоните ще се свърже след одит на съществуващите CSS генератори. Засега настройките са само за Qt интерфейса.'))
        v.addStretch(); return w

    def set_setting(self,key,value):
        self.config[key]=value
        try: self.save_config()
        except OSError as e: self.statusBar().showMessage(f'Неуспешен запис: {e}')
        self.apply_theme()
