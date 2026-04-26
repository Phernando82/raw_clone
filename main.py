"""
RawClone - Ferramenta de clone e imagem de disco
Requer: pip install PySide6 psutil lz4
Executar como Administrador no Windows.
"""

import sys
import os
import time
import hashlib
import struct
import ctypes
import threading
import json
import gzip
import platform
from datetime import datetime, timedelta
from pathlib import Path

try:
    import lz4.frame as lz4frame

    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QTextEdit,
    QFileDialog, QFrame, QStackedWidget, QSizePolicy,
    QSpacerItem, QGroupBox, QRadioButton, QButtonGroup,
    QScrollArea, QMessageBox, QCheckBox, QLineEdit, QSplitter
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QPropertyAnimation,
    QEasingCurve, QRect, QSize, QPoint, Property, QObject
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontDatabase,
    QLinearGradient, QPalette, QPixmap, QIcon, QRadialGradient,
    QPainterPath, QConicalGradient
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

IS_WINDOWS = platform.system() == "Windows"
BLOCK_SIZE = 4 * 1024 * 1024  # 4 MB
APP_VERSION = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# INTERNACIONALIZAÇÃO (i18n)
# ─────────────────────────────────────────────────────────────────────────────

TRANSLATIONS = {
    "pt_BR": {
        "app_sub": "disk imaging & cloning",
        "admin_yes": "🔓  ADMIN",
        "admin_no": "🔒  SEM PRIVILÉGIOS",
        "sec_source": "Fonte",
        "sec_dest": "Destino",
        "sec_options": "Opções",
        "sec_log": "Log de operação",
        "sec_progress": "PROGRESSO",
        "sec_sha": "SHA-256",
        "origin_title": "ORIGEM",
        "dest_title": "DESTINO",
        "rb_disk": "Disco físico",
        "rb_vol": "Volume / Partição",
        "rb_file": "Arquivo de imagem",
        "compression": "Compressão:",
        "comp_none": "Nenhuma",
        "comp_gz": "GZIP (lento)",
        "comp_lz4": "LZ4 (rápido)",
        "browse_btn": "📁  Procurar arquivo...",
        "file_placeholder": "Caminho do arquivo de imagem...",
        "size_label": "Tamanho:",
        "size_unknown": "Tamanho desconhecido",
        "chk_verify": "Verificar integridade (SHA-256)",
        "chk_bad": "Ignorar setores com erro (preencher com zeros)",
        "chk_log": "Salvar log ao concluir",
        "block_size": "Tamanho do bloco:",
        "btn_start": "INICIAR",
        "btn_pause": "PAUSAR",
        "btn_resume": "RETOMAR",
        "btn_cancel": "CANCELAR",
        "btn_clear_log": "Limpar log",
        "btn_save_log": "Exportar log",
        "stat_speed": "VELOCIDADE",
        "stat_eta": "TEMPO REST.",
        "stat_copied": "TRANSFERIDO",
        "stat_errors": "ERROS",
        "hash_src": "FONTE:",
        "hash_dst": "DESTINO:",
        "status_wait": "Aguardando...",
        "status_copying": "Copiando...",
        "status_paused": "Pausado",
        "status_canceling": "Cancelando...",
        "status_done": "✅  Concluído com sucesso",
        "dlg_no_src": "Selecione a origem.",
        "dlg_no_dst": "Selecione o destino.",
        "dlg_same": "Origem e destino não podem ser iguais.",
        "dlg_warn_title": "ATENÇÃO — Operação Destrutiva",
        "dlg_warn_body": "\u26a0  TODOS OS DADOS em\n\n{dst}\n\nser\u00e3o PERMANENTEMENTE DESTRU\u00cdDOS.\n\nDeseja continuar?",
        "log_admin_ok": "✅  Executando com privilégios de Administrador.",
        "log_admin_no": "⚠  Execute como Administrador para acessar discos físicos.",
        "log_admin_file": "   Acesso a arquivos de imagem funciona sem privilégios.",
        "log_size": "📦  Tamanho da fonte: {size}",
        "log_size_unk": "⚠  Não foi possível determinar o tamanho. Progresso estimado.",
        "log_src": "📂  Fonte: {path}",
        "log_dst": "💾  Destino: {path}",
        "log_comp": "🗜  Compressão: {comp}",
        "log_done": "✅  Transferência concluída: {size}",
        "log_time": "⏱  Tempo total: {time}",
        "log_speed": "⚡  Velocidade média: {speed}",
        "log_bad": "⚠  Setores com erro: {n}",
        "log_bad_saved": "📋  Log de erros salvo: {path}",
        "log_hash_src": "🔑  SHA256 fonte:   {h}...",
        "log_hash_dst": "🔑  SHA256 destino: {h}...",
        "log_integrity_ok": "✅  INTEGRIDADE VERIFICADA — hashes idênticos.",
        "log_integrity_fail": "❌  FALHA DE INTEGRIDADE — hashes divergem!",
        "log_perm": "❌  Permissão negada. Execute como Administrador.",
        "log_notfound": "❌  Arquivo/dispositivo não encontrado: {e}",
        "log_error": "❌  Erro: {e}",
        "log_canceled": "✖  Operação cancelada pelo usuário.",
        "log_bad_sector": "⚠  Setor com erro em offset {off} — preenchendo com zeros.",
        "log_paused": "⏸  Pausado pelo usuário.",
        "log_resumed": "▶  Retomado.",
        "log_exported": "📋  Log exportado: {path}",
        "log_log_saved": "📋  Log salvo: {path}",
        "log_log_err": "⚠  Não foi possível salvar log: {e}",
        "status_err": "✖  {msg}",
        "theme_label": "Tema:",
        "theme_dark": "🌙  Dark",
        "theme_light": "☀️  Light",
        "lang_label": "Idioma:",
        "footer": "Developed by Fernando Valverde",
    },
    "es_ES": {
        "app_sub": "imagen y clonación de discos",
        "admin_yes": "🔓  ADMIN",
        "admin_no": "🔒  SIN PRIVILEGIOS",
        "sec_source": "Origen",
        "sec_dest": "Destino",
        "sec_options": "Opciones",
        "sec_log": "Registro de operación",
        "sec_progress": "PROGRESO",
        "sec_sha": "SHA-256",
        "origin_title": "ORIGEN",
        "dest_title": "DESTINO",
        "rb_disk": "Disco físico",
        "rb_vol": "Volumen / Partición",
        "rb_file": "Archivo de imagen",
        "compression": "Compresión:",
        "comp_none": "Ninguna",
        "comp_gz": "GZIP (lento)",
        "comp_lz4": "LZ4 (rápido)",
        "browse_btn": "📁  Buscar archivo...",
        "file_placeholder": "Ruta del archivo de imagen...",
        "size_label": "Tamaño:",
        "size_unknown": "Tamaño desconocido",
        "chk_verify": "Verificar integridad (SHA-256)",
        "chk_bad": "Ignorar sectores con error (rellenar con ceros)",
        "chk_log": "Guardar registro al finalizar",
        "block_size": "Tamaño de bloque:",
        "btn_start": "INICIAR",
        "btn_pause": "PAUSAR",
        "btn_resume": "REANUDAR",
        "btn_cancel": "CANCELAR",
        "btn_clear_log": "Limpiar registro",
        "btn_save_log": "Exportar registro",
        "stat_speed": "VELOCIDAD",
        "stat_eta": "TIEMPO REST.",
        "stat_copied": "TRANSFERIDO",
        "stat_errors": "ERRORES",
        "hash_src": "ORIGEN:",
        "hash_dst": "DESTINO:",
        "status_wait": "Esperando...",
        "status_copying": "Copiando...",
        "status_paused": "Pausado",
        "status_canceling": "Cancelando...",
        "status_done": "✅  Completado con éxito",
        "dlg_no_src": "Seleccione el origen.",
        "dlg_no_dst": "Seleccione el destino.",
        "dlg_same": "El origen y el destino no pueden ser iguales.",
        "dlg_warn_title": "ATENCIÓN — Operación Destructiva",
        "dlg_warn_body": "\u26a0  TODOS LOS DATOS en\n\n{dst}\n\nser\u00e1n DESTRUIDOS PERMANENTEMENTE.\n\n\u00bfDesea continuar?",
        "log_admin_ok": "✅  Ejecutando con privilegios de Administrador.",
        "log_admin_no": "⚠  Ejecute como Administrador para acceder a discos físicos.",
        "log_admin_file": "   El acceso a archivos de imagen funciona sin privilegios.",
        "log_size": "📦  Tamaño del origen: {size}",
        "log_size_unk": "⚠  No se pudo determinar el tamaño. Progreso estimado.",
        "log_src": "📂  Origen: {path}",
        "log_dst": "💾  Destino: {path}",
        "log_comp": "🗜  Compresión: {comp}",
        "log_done": "✅  Transferencia completada: {size}",
        "log_time": "⏱  Tiempo total: {time}",
        "log_speed": "⚡  Velocidad media: {speed}",
        "log_bad": "⚠  Sectores con error: {n}",
        "log_bad_saved": "📋  Registro de errores guardado: {path}",
        "log_hash_src": "🔑  SHA256 origen:   {h}...",
        "log_hash_dst": "🔑  SHA256 destino:  {h}...",
        "log_integrity_ok": "✅  INTEGRIDAD VERIFICADA — hashes idénticos.",
        "log_integrity_fail": "❌  FALLO DE INTEGRIDAD — hashes distintos!",
        "log_perm": "❌  Permiso denegado. Ejecute como Administrador.",
        "log_notfound": "❌  Archivo/dispositivo no encontrado: {e}",
        "log_error": "❌  Error: {e}",
        "log_canceled": "✖  Operación cancelada por el usuario.",
        "log_bad_sector": "⚠  Sector con error en offset {off} — rellenando con ceros.",
        "log_paused": "⏸  Pausado por el usuario.",
        "log_resumed": "▶  Reanudado.",
        "log_exported": "📋  Registro exportado: {path}",
        "log_log_saved": "📋  Registro guardado: {path}",
        "log_log_err": "⚠  No se pudo guardar el registro: {e}",
        "status_err": "✖  {msg}",
        "theme_label": "Tema:",
        "theme_dark": "🌙  Dark",
        "theme_light": "☀️  Light",
        "lang_label": "Idioma:",
        "footer": "Developed by Fernando Valverde",
    },
    "en_US": {
        "app_sub": "disk imaging & cloning",
        "admin_yes": "🔓  ADMIN",
        "admin_no": "🔒  NO PRIVILEGES",
        "sec_source": "Source",
        "sec_dest": "Destination",
        "sec_options": "Options",
        "sec_log": "Operation log",
        "sec_progress": "PROGRESS",
        "sec_sha": "SHA-256",
        "origin_title": "SOURCE",
        "dest_title": "DESTINATION",
        "rb_disk": "Physical disk",
        "rb_vol": "Volume / Partition",
        "rb_file": "Image file",
        "compression": "Compression:",
        "comp_none": "None",
        "comp_gz": "GZIP (slow)",
        "comp_lz4": "LZ4 (fast)",
        "browse_btn": "📁  Browse file...",
        "file_placeholder": "Image file path...",
        "size_label": "Size:",
        "size_unknown": "Unknown size",
        "chk_verify": "Verify integrity (SHA-256)",
        "chk_bad": "Skip bad sectors (fill with zeros)",
        "chk_log": "Save log on completion",
        "block_size": "Block size:",
        "btn_start": "START",
        "btn_pause": "PAUSE",
        "btn_resume": "RESUME",
        "btn_cancel": "CANCEL",
        "btn_clear_log": "Clear log",
        "btn_save_log": "Export log",
        "stat_speed": "SPEED",
        "stat_eta": "ETA",
        "stat_copied": "TRANSFERRED",
        "stat_errors": "ERRORS",
        "hash_src": "SOURCE:",
        "hash_dst": "DEST:",
        "status_wait": "Waiting...",
        "status_copying": "Copying...",
        "status_paused": "Paused",
        "status_canceling": "Canceling...",
        "status_done": "✅  Completed successfully",
        "dlg_no_src": "Please select a source.",
        "dlg_no_dst": "Please select a destination.",
        "dlg_same": "Source and destination cannot be the same.",
        "dlg_warn_title": "WARNING — Destructive Operation",
        "dlg_warn_body": "\u26a0  ALL DATA on\n\n{dst}\n\nwill be PERMANENTLY DESTROYED.\n\nDo you want to continue?",
        "log_admin_ok": "✅  Running with Administrator privileges.",
        "log_admin_no": "⚠  Run as Administrator to access physical disks.",
        "log_admin_file": "   Image file access works without elevated privileges.",
        "log_size": "📦  Source size: {size}",
        "log_size_unk": "⚠  Could not determine size. Progress will be estimated.",
        "log_src": "📂  Source: {path}",
        "log_dst": "💾  Destination: {path}",
        "log_comp": "🗜  Compression: {comp}",
        "log_done": "✅  Transfer complete: {size}",
        "log_time": "⏱  Total time: {time}",
        "log_speed": "⚡  Average speed: {speed}",
        "log_bad": "⚠  Bad sectors: {n}",
        "log_bad_saved": "📋  Error log saved: {path}",
        "log_hash_src": "🔑  SHA256 source: {h}...",
        "log_hash_dst": "🔑  SHA256 dest:   {h}...",
        "log_integrity_ok": "✅  INTEGRITY VERIFIED — hashes match.",
        "log_integrity_fail": "❌  INTEGRITY FAILURE — hashes differ!",
        "log_perm": "❌  Permission denied. Run as Administrator.",
        "log_notfound": "❌  File/device not found: {e}",
        "log_error": "❌  Error: {e}",
        "log_canceled": "✖  Operation canceled by user.",
        "log_bad_sector": "⚠  Bad sector at offset {off} — filling with zeros.",
        "log_paused": "⏸  Paused by user.",
        "log_resumed": "▶  Resumed.",
        "log_exported": "📋  Log exported: {path}",
        "log_log_saved": "📋  Log saved: {path}",
        "log_log_err": "⚠  Could not save log: {e}",
        "status_err": "✖  {msg}",
        "theme_label": "Theme:",
        "theme_dark": "🌙  Dark",
        "theme_light": "☀️  Light",
        "lang_label": "Language:",
        "footer": "Developed by Fernando Valverde",
    },
}

LANG_OPTIONS = [
    ("🇧🇷  Português BR", "pt_BR"),
    ("🇪🇸  Español ES", "es_ES"),
    ("🇺🇸  English", "en_US"),
]

_current_lang = "pt_BR"


def tr(key, **kwargs):
    val = TRANSLATIONS.get(_current_lang, TRANSLATIONS["pt_BR"]).get(key, key)
    return val.format(**kwargs) if kwargs else val


def set_language(lang_code):
    global _current_lang
    if lang_code in TRANSLATIONS:
        _current_lang = lang_code


# ─────────────────────────────────────────────────────────────────────────────
# TEMAS
# ─────────────────────────────────────────────────────────────────────────────

THEME_DARK = {
    "bg": "#0A0C0F",
    "bg2": "#10141A",
    "bg3": "#161C24",
    "border": "#1E2A38",
    "border2": "#253445",
    "accent": "#00C8FF",
    "accent2": "#0090C8",
    "accent_glow": "#00C8FF40",
    "green": "#00E676",
    "green_dim": "#00E67630",
    "yellow": "#FFD600",
    "yellow_dim": "#FFD60030",
    "red": "#FF3D57",
    "red_dim": "#FF3D5730",
    "text": "#E8F0FA",
    "text2": "#8899AA",
    "text3": "#445566",
    "log_fg": "#00E676",
}

THEME_LIGHT = {
    "bg": "#F0F4F8",
    "bg2": "#E4ECF4",
    "bg3": "#D8E4EE",
    "border": "#B0C4D8",
    "border2": "#90AABF",
    "accent": "#0078C8",
    "accent2": "#005A9E",
    "accent_glow": "#0078C840",
    "green": "#007A3D",
    "green_dim": "#007A3D20",
    "yellow": "#B07800",
    "yellow_dim": "#B0780020",
    "red": "#C0001E",
    "red_dim": "#C0001E20",
    "text": "#0A1A2E",
    "text2": "#3A5068",
    "text3": "#7890A8",
    "log_fg": "#005A2A",
}

_current_theme = "dark"
COLORS = dict(THEME_DARK)


def set_theme(name):
    global _current_theme, COLORS
    _current_theme = name
    COLORS.clear()
    COLORS.update(THEME_DARK if name == "dark" else THEME_LIGHT)


def build_stylesheet():
    C = COLORS
    return f"""
QMainWindow, QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: 'Consolas', 'Courier New', monospace;
}}
QLabel {{
    color: {C['text']};
    background: transparent;
}}
QPushButton {{
    background-color: {C['bg3']};
    color: {C['text']};
    border: 1px solid {C['border2']};
    border-radius: 4px;
    padding: 8px 18px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    letter-spacing: 1px;
}}
QPushButton:hover {{
    background-color: {C['border2']};
    border-color: {C['accent']};
    color: {C['accent']};
}}
QPushButton:pressed {{
    background-color: {C['accent2']};
    color: white;
}}
QPushButton:disabled {{
    color: {C['text3']};
    border-color: {C['border']};
    background-color: {C['bg2']};
}}
QPushButton#btn_start {{
    background-color: {C['accent2']};
    color: #00FF90;
    border: 2px solid #00FF90;
    font-size: 13px;
    font-weight: bold;
    padding: 10px 32px;
    letter-spacing: 2px;
}}
QPushButton#btn_start:hover {{
    background-color: #00D870;
    color: #F0FFF8;
    border: 2px solid #00FF90;
}}
QPushButton#btn_start:pressed {{
    background-color: #008040;
    color: #FFFFFF;
    border: 2px solid #00FF90;
}}
QPushButton#btn_start:disabled {{
    background-color: {C['bg3']};
    color: {C['text3']};
    border: 1px solid {C['border']};
}}
QPushButton#btn_pause {{
    background-color: {C['bg3']};
    color: {C['yellow']};
    border: 1px solid {C['yellow']};
}}
QPushButton#btn_pause:hover {{
    background-color: {C['yellow_dim']};
}}
QPushButton#btn_cancel {{
    background-color: {C['bg3']};
    color: {C['red']};
    border: 1px solid {C['red']};
}}
QPushButton#btn_cancel:hover {{
    background-color: {C['red_dim']};
}}
QComboBox {{
    background-color: {C['bg3']};
    color: {C['text']};
    border: 1px solid {C['border2']};
    border-radius: 4px;
    padding: 6px 12px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    min-height: 32px;
}}
QComboBox:hover {{
    border-color: {C['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
    border: 2px solid {C['accent']};
    border-top: none;
    border-right: none;
    transform: rotate(-45deg);
}}
QComboBox QAbstractItemView {{
    background-color: {C['bg3']};
    color: {C['text']};
    border: 1px solid {C['border2']};
    selection-background-color: {C['accent2']};
    selection-color: {C['text']};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    color: {C['text']};
    background-color: {C['bg3']};
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {C['border2']};
    color: {C['text']};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {C['accent2']};
    color: {C['text']};
}}
QProgressBar {{
    background-color: {C['bg3']};
    border: 1px solid {C['border']};
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent2']}, stop:1 {C['accent']});
    border-radius: 3px;
}}
QTextEdit {{
    background-color: {C['bg2']};
    color: {C['log_fg']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 8px;
}}
QFrame#separator {{
    background-color: {C['border']};
    max-height: 1px;
}}
QCheckBox {{
    color: {C['text2']};
    spacing: 8px;
    font-size: 12px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {C['border2']};
    border-radius: 2px;
    background: {C['bg3']};
}}
QCheckBox::indicator:checked {{
    background: {C['accent2']};
    border-color: {C['accent']};
}}
QRadioButton {{
    color: {C['text2']};
    spacing: 8px;
    font-size: 12px;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {C['border2']};
    border-radius: 7px;
    background: {C['bg3']};
}}
QRadioButton::indicator:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
}}
QLineEdit {{
    background-color: {C['bg3']};
    color: {C['text']};
    border: 1px solid {C['border2']};
    border-radius: 4px;
    padding: 6px 10px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
}}
QLineEdit:focus {{
    border-color: {C['accent']};
}}
QScrollBar:vertical {{
    background: {C['bg2']};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C['border2']};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C['accent2']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QSplitter::handle {{
    background: {C['border']};
    width: 1px;
}}
"""


STYLESHEET = build_stylesheet()


def apply_combo_palette(combo):
    """Força palette correta no QComboBox e seu popup — necessário no Windows/Fusion
    para evitar faixa preta no hover dos itens."""
    C = COLORS
    p = combo.palette()
    bg   = QColor(C["bg3"])
    fg   = QColor(C["text"])
    sel_bg = QColor(C["accent2"])
    sel_fg = QColor(C["text"])
    # Widget do combo em si
    p.setColor(QPalette.Base,            bg)
    p.setColor(QPalette.Window,          bg)
    p.setColor(QPalette.Button,          bg)
    p.setColor(QPalette.Text,            fg)
    p.setColor(QPalette.WindowText,      fg)
    p.setColor(QPalette.ButtonText,      fg)
    # Itens da lista popup
    p.setColor(QPalette.AlternateBase,   bg)
    p.setColor(QPalette.Highlight,       sel_bg)
    p.setColor(QPalette.HighlightedText, sel_fg)
    combo.setPalette(p)
    # Aplica também na view interna do popup
    view = combo.view()
    if view:
        view.setPalette(p)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────────────

def human_size(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def human_speed(bps):
    return human_size(bps) + "/s"


def human_eta(seconds):
    if seconds <= 0 or seconds > 86400 * 7:
        return "--:--:--"
    return str(timedelta(seconds=int(seconds)))


def is_admin():
    if IS_WINDOWS:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    else:
        return os.geteuid() == 0


def get_disk_size_windows(handle_path):
    try:
        import ctypes.wintypes as wt
        IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0

        class DISK_GEOMETRY(ctypes.Structure):
            _fields_ = [
                ("Cylinders", ctypes.c_longlong),
                ("MediaType", ctypes.c_uint),
                ("TracksPerCylinder", ctypes.c_ulong),
                ("SectorsPerTrack", ctypes.c_ulong),
                ("BytesPerSector", ctypes.c_ulong),
            ]

        class DISK_GEOMETRY_EX(ctypes.Structure):
            _fields_ = [
                ("Geometry", DISK_GEOMETRY),
                ("DiskSize", ctypes.c_longlong),
                ("Data", ctypes.c_byte * 1),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateFileW(
            handle_path,
            0x80000000,
            0x3,
            None, 3, 0, None
        )
        if handle == ctypes.c_void_p(-1).value:
            return 0

        geo = DISK_GEOMETRY_EX()
        bytes_ret = ctypes.c_ulong(0)
        ok = kernel32.DeviceIoControl(
            handle, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,
            None, 0,
            ctypes.byref(geo), ctypes.sizeof(geo),
            ctypes.byref(bytes_ret), None
        )
        kernel32.CloseHandle(handle)
        return geo.DiskSize if ok else 0
    except:
        return 0


def list_physical_disks():
    disks = []

    if IS_WINDOWS:
        for i in range(16):
            path = f"\\\\.\\PhysicalDrive{i}"
            size = get_disk_size_windows(path)
            if size > 0:
                label = f"PhysicalDrive{i}  [{human_size(size)}]"
                disks.append({"path": path, "label": label, "size": size, "type": "disk"})

        if HAS_PSUTIL:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    path = f"\\\\.\\{part.device.rstrip(chr(92)).rstrip(':')}"
                    label = f"{part.device}  [{part.fstype}]  [{human_size(usage.total)}]"
                    disks.append({"path": path, "label": label, "size": usage.total, "type": "volume"})
                except:
                    pass
    else:
        import subprocess
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL"],
                capture_output=True, text=True, timeout=5
            )
            data = json.loads(result.stdout)
            for dev in data.get("blockdevices", []):
                if dev.get("type") in ("disk", "loop"):
                    path = f"/dev/{dev['name']}"
                    size = int(dev.get("size", 0))
                    model = dev.get("model", "").strip() or dev['name']
                    label = f"{path}  {model}  [{human_size(size)}]"
                    disks.append({"path": path, "label": label, "size": size, "type": "disk"})
                    for child in dev.get("children", []):
                        cpath = f"/dev/{child['name']}"
                        csize = int(child.get("size", 0))
                        mp = child.get("mountpoint", "") or ""
                        clabel = f"  ├─ {cpath}  [{human_size(csize)}]  {mp}"
                        disks.append({"path": cpath, "label": clabel, "size": csize, "type": "partition"})
        except:
            for dev in Path("/dev").glob("sd?"):
                disks.append({"path": str(dev), "label": str(dev), "size": 0, "type": "disk"})

    return disks


# ─────────────────────────────────────────────────────────────────────────────
# WORKER DE CÓPIA
# ─────────────────────────────────────────────────────────────────────────────

class CopyWorker(QThread):
    sig_progress = Signal(int, float, float, int)
    sig_log = Signal(str, str)
    sig_hash = Signal(str, str)
    sig_finished = Signal(bool, str)
    sig_size = Signal(int)

    def __init__(self, src, dst, options):
        super().__init__()
        self.src = src
        self.dst = dst
        self.options = options
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._cancel = False
        self.bad_sectors = 0
        self.bad_sector_log = []

    def pause(self):
        self._pause_event.clear()
        self.sig_log.emit(tr("log_paused"), "warn")

    def resume(self):
        self._pause_event.set()
        self.sig_log.emit(tr("log_resumed"), "info")

    def cancel(self):
        self._cancel = True
        self._pause_event.set()

    def _get_total_size(self, path):
        if os.path.isfile(path):
            return os.path.getsize(path)
        if IS_WINDOWS and path.startswith("\\\\.\\"):
            return get_disk_size_windows(path)
        try:
            return os.path.getsize(path)
        except:
            return 0

    def _open_src(self):
        compression = self.options.get("src_compression", "none")
        if compression == "gz":
            return gzip.open(self.src, "rb")
        elif compression == "lz4" and HAS_LZ4:
            return lz4frame.open(self.src, "rb")
        else:
            return open(self.src, "rb", buffering=0)

    def _open_dst(self):
        compression = self.options.get("dst_compression", "none")
        if compression == "gz":
            return gzip.open(self.dst, "wb", compresslevel=1)
        elif compression == "lz4" and HAS_LZ4:
            return lz4frame.open(self.dst, "wb")
        else:
            return open(self.dst, "wb", buffering=0)

    def run(self):
        sha_src = hashlib.sha256()
        sha_dst = hashlib.sha256()
        verify = self.options.get("verify", True)
        skip_bad = self.options.get("skip_bad_sectors", True)

        try:
            total = self._get_total_size(self.src)
            if total > 0:
                self.sig_size.emit(total)
                self.sig_log.emit(tr("log_size", size=human_size(total)), "info")
            else:
                self.sig_log.emit(tr("log_size_unk"), "warn")

            self.sig_log.emit(tr("log_src", path=self.src), "info")
            self.sig_log.emit(tr("log_dst", path=self.dst), "info")
            comp = self.options.get("dst_compression", "none")
            if comp != "none":
                self.sig_log.emit(tr("log_comp", comp=comp.upper()), "info")
            self.sig_log.emit("─" * 60, "info")

            copied = 0
            t_start = time.time()
            t_speed = time.time()
            bytes_window = 0
            speed_smooth = 0.0
            offset = 0

            src_f = self._open_src()
            dst_f = self._open_dst()

            try:
                while True:
                    if self._cancel:
                        self.sig_log.emit(tr("log_canceled"), "error")
                        self.sig_finished.emit(False, "Cancelado")
                        return

                    self._pause_event.wait()

                    try:
                        chunk = src_f.read(BLOCK_SIZE)
                    except OSError as e:
                        if skip_bad:
                            self.bad_sectors += 1
                            self.bad_sector_log.append(offset)
                            self.sig_log.emit(tr("log_bad_sector", off=human_size(offset)), "warn")
                            chunk = b"\x00" * BLOCK_SIZE
                            try:
                                src_f.seek(offset + BLOCK_SIZE)
                            except:
                                pass
                        else:
                            raise

                    if not chunk:
                        break

                    dst_f.write(chunk)
                    sha_src.update(chunk)
                    if verify:
                        sha_dst.update(chunk)

                    copied += len(chunk)
                    offset += len(chunk)
                    bytes_window += len(chunk)

                    now = time.time()
                    elapsed_window = now - t_speed
                    if elapsed_window >= 0.5:
                        instant_speed = bytes_window / elapsed_window
                        speed_smooth = 0.7 * speed_smooth + 0.3 * instant_speed if speed_smooth else instant_speed
                        bytes_window = 0
                        t_speed = now

                    elapsed_total = now - t_start
                    pct = int(copied / total * 100) if total > 0 else -1
                    eta = (total - copied) / speed_smooth if speed_smooth > 0 and total > 0 else 0

                    self.sig_progress.emit(pct, speed_smooth / 1e6, eta, self.bad_sectors)

            finally:
                src_f.close()
                dst_f.close()

            elapsed = time.time() - t_start
            avg_speed = copied / elapsed if elapsed > 0 else 0
            self.sig_log.emit("─" * 60, "info")
            self.sig_log.emit(tr("log_done", size=human_size(copied)), "ok")
            self.sig_log.emit(tr("log_time", time=human_eta(elapsed)), "info")
            self.sig_log.emit(tr("log_speed", speed=human_speed(avg_speed)), "info")

            if self.bad_sectors:
                self.sig_log.emit(tr("log_bad", n=self.bad_sectors), "warn")
                log_path = str(Path(self.dst).with_suffix(".badsectors.txt"))
                try:
                    with open(log_path, "w") as lf:
                        lf.write(f"Bad sectors log - {datetime.now()}\n")
                        lf.write(f"Fonte: {self.src}\n\n")
                        for off in self.bad_sector_log:
                            lf.write(f"Offset: {off} ({human_size(off)})\n")
                    self.sig_log.emit(tr("log_bad_saved", path=log_path), "warn")
                except:
                    pass

            hash_src = sha_src.hexdigest()
            hash_dst = sha_dst.hexdigest() if verify else "—"
            self.sig_log.emit(tr("log_hash_src", h=hash_src[:32]), "info")
            if verify:
                self.sig_log.emit(tr("log_hash_dst", h=hash_dst[:32]), "info")
                if hash_src == hash_dst:
                    self.sig_log.emit(tr("log_integrity_ok"), "ok")
                else:
                    self.sig_log.emit(tr("log_integrity_fail"), "error")

            self.sig_hash.emit(hash_src, hash_dst)
            self.sig_finished.emit(True, "Concluído com sucesso")

        except PermissionError:
            self.sig_log.emit(tr("log_perm"), "error")
            self.sig_finished.emit(False, "Permissão negada")
        except FileNotFoundError as e:
            self.sig_log.emit(tr("log_notfound", e=e), "error")
            self.sig_finished.emit(False, str(e))
        except Exception as e:
            self.sig_log.emit(tr("log_error", e=e), "error")
            self.sig_finished.emit(False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# WIDGETS CUSTOMIZADOS
# ─────────────────────────────────────────────────────────────────────────────

class GlowLabel(QLabel):
    def __init__(self, text="", glow_color=None, parent=None):
        super().__init__(text, parent)
        self._glow = QColor(glow_color or COLORS["accent"])

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for r in range(8, 0, -2):
            c = QColor(self._glow)
            c.setAlpha(int(15 * (9 - r) / 8))
            painter.setPen(QPen(c, r))
            painter.setFont(self.font())
            painter.drawText(self.rect(), self.alignment(), self.text())
        painter.setPen(QColor(self._glow))
        painter.setFont(self.font())
        painter.drawText(self.rect(), self.alignment(), self.text())


class CircularProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._max = 100
        self.setFixedSize(140, 140)

    def setValue(self, v):
        self._value = max(0, min(v, self._max))
        self.update()

    def setMaximum(self, m):
        self._max = m

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r = min(w, h) // 2 - 12

        pen = QPen(QColor(COLORS["bg3"]), 8)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        if self._max > 0 and self._value > 0:
            span = int(-(self._value / self._max) * 360 * 16)
            grad = QConicalGradient(cx, cy, 90)
            grad.setColorAt(0.0, QColor(COLORS["accent"]))
            grad.setColorAt(1.0, QColor(COLORS["accent2"]))
            pen2 = QPen(QBrush(grad), 8)
            pen2.setCapStyle(Qt.RoundCap)
            painter.setPen(pen2)
            painter.drawArc(cx - r, cy - r, r * 2, r * 2, 90 * 16, span)

        pct_str = f"{self._value}%" if self._max > 0 else "─"
        font = QFont("Consolas", 18, QFont.Bold)
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, pct_str)


class StatBox(QFrame):
    def __init__(self, icon, label, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg3']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setSpacing(2)
        lay.setContentsMargins(12, 10, 12, 10)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setStyleSheet(
            f"font-size: 18px; color: {COLORS['accent']}; background: transparent; border: none;")
        self._icon_lbl.setAlignment(Qt.AlignCenter)

        self._val_lbl = QLabel("—")
        self._val_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {COLORS['text']}; background: transparent; border: none;")
        self._val_lbl.setAlignment(Qt.AlignCenter)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"font-size: 10px; color: {COLORS['text3']}; letter-spacing: 1px; background: transparent; border: none;")
        self._lbl.setAlignment(Qt.AlignCenter)

        lay.addWidget(self._icon_lbl)
        lay.addWidget(self._val_lbl)
        lay.addWidget(self._lbl)

    def setValue(self, v):
        self._val_lbl.setText(str(v))


class SectionHeader(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(f"""
            color: {COLORS['text3']};
            font-size: 10px;
            letter-spacing: 3px;
            font-family: 'Consolas', monospace;
            padding: 0px;
            background: transparent;
        """)


class Separator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("separator")
        self.setFrameShape(QFrame.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {COLORS['border']}; border: none;")


# ─────────────────────────────────────────────────────────────────────────────
# PAINEL DE CONFIGURAÇÃO DE FONTE/DESTINO
# ─────────────────────────────────────────────────────────────────────────────

class SourceDestPanel(QWidget):
    changed = Signal()

    def __init__(self, title_key, is_source=True, parent=None):
        super().__init__(parent)
        self.is_source = is_source
        self.title_key = title_key
        self.disks = []

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        hdr = QHBoxLayout()
        icon = "📂" if is_source else "💾"
        self.lbl_title = QLabel(f"{icon}  {tr(title_key)}")
        self.lbl_title.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {COLORS['accent'] if is_source else COLORS['green']}; background: transparent;")
        hdr.addWidget(self.lbl_title)
        hdr.addStretch()
        layout.addLayout(hdr)

        type_row = QHBoxLayout()
        self.rb_disk = QRadioButton(tr("rb_disk"))
        self.rb_vol = QRadioButton(tr("rb_vol"))
        self.rb_file = QRadioButton(tr("rb_file"))
        self.rb_disk.setChecked(True)

        self._rb_group = QButtonGroup(self)
        for rb in [self.rb_disk, self.rb_vol, self.rb_file]:
            self._rb_group.addButton(rb)
            type_row.addWidget(rb)
        type_row.addStretch()
        layout.addLayout(type_row)

        disk_row = QHBoxLayout()
        self.cmb_disk = QComboBox()
        self.cmb_disk.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_refresh = QPushButton("↺")
        self.btn_refresh.setFixedWidth(36)
        self.btn_refresh.setToolTip("Atualizar lista de discos")
        disk_row.addWidget(self.cmb_disk)
        disk_row.addWidget(self.btn_refresh)
        layout.addLayout(disk_row)

        file_col = QVBoxLayout()
        file_col.setSpacing(6)

        self.le_file = QLineEdit()
        self.le_file.setPlaceholderText(tr("file_placeholder"))
        file_col.addWidget(self.le_file)

        self.btn_browse = QPushButton(tr("browse_btn"))
        self.btn_browse.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg3']};
                color: {COLORS['accent']};
                border: 1px dashed {COLORS['accent2']};
                border-radius: 4px;
                padding: 7px 14px;
                font-size: 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent_glow']};
                border-style: solid;
                border-color: {COLORS['accent']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['accent2']};
                color: white;
            }}
        """)
        file_col.addWidget(self.btn_browse)

        self.file_widget = QWidget()
        self.file_widget.setLayout(file_col)
        self.file_widget.hide()
        layout.addWidget(self.file_widget)

        self.comp_widget = QWidget()
        comp_row = QHBoxLayout(self.comp_widget)
        comp_row.setContentsMargins(0, 0, 0, 0)
        self.comp_lbl = QLabel(tr("compression"))
        self.comp_lbl.setStyleSheet(f"color: {COLORS['text2']}; background: transparent; font-size: 12px;")
        self.cmb_comp = QComboBox()
        self.cmb_comp.setFixedWidth(120)
        items = [(tr("comp_none"), "none"), (tr("comp_gz"), "gz")]
        if HAS_LZ4:
            items.append((tr("comp_lz4"), "lz4"))
        for lbl_t, val in items:
            self.cmb_comp.addItem(lbl_t, val)
        comp_row.addWidget(self.comp_lbl)
        comp_row.addWidget(self.cmb_comp)
        comp_row.addStretch()
        if is_source:
            self.comp_widget.hide()
        layout.addWidget(self.comp_widget)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet(f"color: {COLORS['text3']}; font-size: 11px; background: transparent;")
        layout.addWidget(self.lbl_info)

        self.btn_refresh.clicked.connect(self.refresh_disks)
        self.btn_browse.clicked.connect(self._browse)
        self._rb_group.buttonToggled.connect(self._on_type_changed)
        self.cmb_disk.currentIndexChanged.connect(self._update_info)
        self.le_file.textChanged.connect(self.changed)

        self.refresh_disks()

    def refresh_disks(self):
        self.cmb_disk.clear()
        self.disks = list_physical_disks()
        disk_type = "disk" if self.rb_disk.isChecked() else "volume"
        filtered = [d for d in self.disks if d["type"] == disk_type or d["type"] == "partition"]
        for d in filtered:
            self.cmb_disk.addItem(d["label"], d)
        self._update_info()

    def _on_type_changed(self):
        is_file = self.rb_file.isChecked()
        self.cmb_disk.setVisible(not is_file)
        self.btn_refresh.setVisible(not is_file)
        self.file_widget.setVisible(is_file)
        if self.is_source:
            self.comp_widget.setVisible(is_file)
        else:
            self.comp_widget.setVisible(True)
        if not is_file:
            self.refresh_disks()
        self.changed.emit()

    def _browse(self):
        if self.is_source:
            path, _ = QFileDialog.getOpenFileName(
                self, "Selecionar imagem", "",
                "Imagens de disco (*.img *.img.gz *.img.lz4 *.iso *.bin *.raw *.dd);;Todos (*.*)"
            )
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salvar imagem como", "",
                "Imagem raw (*.img);;GZIP (*.img.gz);;LZ4 (*.img.lz4);;Todos (*.*)"
            )
            if path:
                ext = Path(path).suffix.lower()
                if ext == ".gz":
                    self.cmb_comp.setCurrentIndex(self.cmb_comp.findData("gz"))
                elif ext == ".lz4":
                    idx = self.cmb_comp.findData("lz4")
                    if idx >= 0:
                        self.cmb_comp.setCurrentIndex(idx)
        if path:
            self.le_file.setText(path)

    def _update_info(self):
        if self.rb_file.isChecked():
            return
        idx = self.cmb_disk.currentIndex()
        if idx < 0:
            self.lbl_info.setText("")
            return
        data = self.cmb_disk.currentData()
        if data:
            size = data.get("size", 0)
            info = f"Tamanho: {human_size(size)}" if size else tr("size_unknown")
            self.lbl_info.setText(info)
        self.changed.emit()

    def get_path(self):
        if self.rb_file.isChecked():
            return self.le_file.text().strip()
        data = self.cmb_disk.currentData()
        return data["path"] if data else ""

    def get_compression(self):
        return self.cmb_comp.currentData() or "none"

    def is_valid(self):
        return bool(self.get_path())

    def retranslate(self):
        icon = "📂" if self.is_source else "💾"
        self.lbl_title.setText(f"{icon}  {tr(self.title_key)}")
        self.rb_disk.setText(tr("rb_disk"))
        self.rb_vol.setText(tr("rb_vol"))
        self.rb_file.setText(tr("rb_file"))
        self.comp_lbl.setText(tr("compression"))
        self.le_file.setPlaceholderText(tr("file_placeholder"))
        self.btn_browse.setText(tr("browse_btn"))
        cur = self.cmb_comp.currentData()
        self.cmb_comp.blockSignals(True)
        self.cmb_comp.clear()
        items = [(tr("comp_none"), "none"), (tr("comp_gz"), "gz")]
        if HAS_LZ4:
            items.append((tr("comp_lz4"), "lz4"))
        for lbl_t, val in items:
            self.cmb_comp.addItem(lbl_t, val)
        idx = self.cmb_comp.findData(cur)
        if idx >= 0:
            self.cmb_comp.setCurrentIndex(idx)
        self.cmb_comp.blockSignals(False)
        self._update_info()


# ─────────────────────────────────────────────────────────────────────────────
# JANELA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RawClone")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)

        icon_path = Path(__file__).parent / "icone.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.worker = None
        self._paused = False
        self._total_bytes = 0
        self._lang = "pt_BR"

        self._build_ui()
        self._check_admin()

    def _on_theme_changed(self):
        theme = self.cmb_theme.currentData()
        set_theme(theme)
        new_ss = build_stylesheet()
        QApplication.instance().setStyleSheet(new_ss)
        self.setStyleSheet(new_ss)
        self._apply_theme_inline()
        self._apply_fusion_palette()

    def _apply_theme_inline(self):
        C = COLORS
        for panel in [self.src_panel, self.dst_panel]:
            panel.btn_browse.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C['bg3']};
                    color: {C['accent']};
                    border: 1px dashed {C['accent2']};
                    border-radius: 4px;
                    padding: 7px 14px;
                    font-size: 12px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {C['accent_glow']};
                    border-style: solid;
                    border-color: {C['accent']};
                }}
                QPushButton:pressed {{
                    background-color: {C['accent2']};
                    color: white;
                }}
            """)
            panel.lbl_title.setStyleSheet(
                f"font-size: 13px; font-weight: bold; "
                f"color: {C['accent'] if panel.is_source else C['green']}; background: transparent;"
            )
            panel.comp_lbl.setStyleSheet(f"color: {C['text2']}; background: transparent; font-size: 12px;")
            panel.lbl_info.setStyleSheet(f"color: {C['text3']}; font-size: 11px; background: transparent;")

        for sb in [self.stat_speed, self.stat_eta, self.stat_copied, self.stat_bad]:
            sb.setStyleSheet(f"""
                QFrame {{
                    background: {C['bg3']};
                    border: 1px solid {C['border']};
                    border-radius: 6px;
                }}
            """)
            sb._icon_lbl.setStyleSheet(f"font-size: 18px; color: {C['accent']}; background: transparent; border: none;")
            sb._val_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {C['text']}; background: transparent; border: none;")
            sb._lbl.setStyleSheet(
                f"font-size: 10px; color: {C['text3']}; letter-spacing: 1px; background: transparent; border: none;")

        for sh in [self.sh_source, self.sh_dest, self.sh_opts, self.sh_log]:
            sh.setStyleSheet(
                f"color: {C['text3']}; font-size: 10px; letter-spacing: 3px; font-family: 'Consolas', monospace; background: transparent;")

        self.bar_lbl.setStyleSheet(
            f"color: {C['text3']}; font-size: 9px; letter-spacing: 2px; background: transparent;")
        self.bs_lbl.setStyleSheet(f"color: {C['text2']}; font-size: 12px; background: transparent;")
        self.lbl_status.setStyleSheet(f"color: {C['text2']}; font-size: 12px; background: transparent;")
        self.h_header.setStyleSheet(
            f"color: {C['text3']}; font-size: 9px; letter-spacing: 2px; background: transparent;")
        self.lbl_hash_src.setStyleSheet(f"color: {C['text2']}; font-size: 11px; background: transparent;")
        self.lbl_hash_dst.setStyleSheet(f"color: {C['text2']}; font-size: 11px; background: transparent;")
        self.footer_lbl.setStyleSheet(
            f"color: {C['text3']}; font-size: 10px; letter-spacing: 1px; font-family: 'Consolas', monospace; background: transparent;")

        if is_admin():
            self.lbl_admin.setStyleSheet(f"color: {C['green']}; font-size: 11px; background: transparent;")
        else:
            self.lbl_admin.setStyleSheet(f"color: {C['yellow']}; font-size: 11px; background: transparent;")

        self.lbl_theme.setStyleSheet(
            f"color: {C['text3']}; font-size: 11px; background: transparent; margin-right: 4px;")
        self.lbl_lang.setStyleSheet(
            f"color: {C['text3']}; font-size: 11px; background: transparent; margin-right: 4px;")

        self.header_w.setStyleSheet(f"""
            QWidget#header_w {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C['bg2']}, stop:1 {C['bg']});
                border-bottom: 1px solid {C['border']};
            }}
        """)
        self.left_w.setStyleSheet(f"background: {C['bg2']}; border-right: 1px solid {C['border']};")
        self.right_w.setStyleSheet(f"background: {C['bg']};")
        self.prog_frame.setStyleSheet(f"""
            background: {C['bg2']};
            border: 1px solid {C['border']};
            border-radius: 8px;
        """)
        self.hash_frame.setStyleSheet(f"""
            background: {C['bg3']};
            border: 1px solid {C['border']};
            border-radius: 6px;
            padding: 6px;
        """)
        self.footer_w.setStyleSheet(f"""
            background: {C['bg2']};
            border-top: 1px solid {C['border']};
        """)
        self.left_scroll_ref.setStyleSheet(f"border: none; background: {C['bg2']};")

        for w in [self.header_w, self.left_w, self.right_w, self.prog_frame,
                  self.hash_frame, self.footer_w, self.centralWidget()]:
            w.update()
            w.repaint()
        self.update()

    def _apply_fusion_palette(self):
        C = COLORS
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(C["bg"]))
        palette.setColor(QPalette.WindowText, QColor(C["text"]))
        palette.setColor(QPalette.Base, QColor(C["bg2"]))
        palette.setColor(QPalette.AlternateBase, QColor(C["bg3"]))
        palette.setColor(QPalette.ToolTipBase, QColor(C["bg3"]))
        palette.setColor(QPalette.ToolTipText, QColor(C["text"]))
        palette.setColor(QPalette.Text, QColor(C["text"]))
        palette.setColor(QPalette.Button, QColor(C["bg3"]))
        palette.setColor(QPalette.ButtonText, QColor(C["text"]))
        palette.setColor(QPalette.Highlight, QColor(C["accent2"]))
        palette.setColor(QPalette.HighlightedText, QColor(C["bg"]))
        QApplication.instance().setPalette(palette)

    def _on_lang_changed(self):
        code = self.cmb_lang.currentData()
        set_language(code)
        self._lang = code
        self._retranslate_ui()

    def _retranslate_ui(self):
        self.sub_lbl.setText(f"{tr('app_sub')}  ·  v{APP_VERSION}")
        self.lbl_theme.setText(tr("theme_label"))
        self.cmb_theme.blockSignals(True)
        cur_theme = self.cmb_theme.currentData()
        self.cmb_theme.clear()
        self.cmb_theme.addItem(tr("theme_dark"), "dark")
        self.cmb_theme.addItem(tr("theme_light"), "light")
        idx = self.cmb_theme.findData(cur_theme)
        if idx >= 0: self.cmb_theme.setCurrentIndex(idx)
        self.cmb_theme.blockSignals(False)
        self.lbl_lang.setText(tr("lang_label"))
        if is_admin():
            self.lbl_admin.setText(tr("admin_yes"))
        else:
            self.lbl_admin.setText(tr("admin_no"))
        self.sh_source.setText(tr("sec_source").upper())
        self.sh_dest.setText(tr("sec_dest").upper())
        self.sh_opts.setText(tr("sec_options").upper())
        self.sh_log.setText(tr("sec_log").upper())
        self.src_panel.retranslate()
        self.dst_panel.retranslate()
        self.chk_verify.setText(tr("chk_verify"))
        self.chk_bad.setText(tr("chk_bad"))
        self.chk_log.setText(tr("chk_log"))
        self.bs_lbl.setText(tr("block_size"))
        self.btn_start.setText(tr("btn_start"))
        self.btn_pause.setText(tr("btn_resume") if self._paused else tr("btn_pause"))
        self.btn_cancel.setText(tr("btn_cancel"))
        self.btn_clear_log.setText(tr("btn_clear_log"))
        self.btn_save_log.setText(tr("btn_save_log"))
        self.stat_speed._lbl.setText(tr("stat_speed"))
        self.stat_eta._lbl.setText(tr("stat_eta"))
        self.stat_copied._lbl.setText(tr("stat_copied"))
        self.stat_bad._lbl.setText(tr("stat_errors"))
        self.bar_lbl.setText(tr("sec_progress"))
        self.h_header.setText(tr("sec_sha"))
        self.lbl_hash_src_key.setText(tr("hash_src") + "   ")
        self.lbl_hash_dst_key.setText(tr("hash_dst") + " ")
        if not self.worker or not self.worker.isRunning():
            self.lbl_status.setText(tr("status_wait"))
        self.footer_lbl.setText(tr("footer"))

    def _check_admin(self):
        if not is_admin():
            self._log(tr("log_admin_no"), "warn")
            self._log(tr("log_admin_file"), "info")
        else:
            self._log(tr("log_admin_ok"), "ok")
        self._log("─" * 60, "info")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────
        self.header_w = QWidget()
        self.header_w.setFixedHeight(60)
        self.header_w.setObjectName("header_w")
        self.header_w.setStyleSheet(f"""
            QWidget#header_w {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {COLORS['bg2']}, stop:1 {COLORS['bg']});
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        h_lay = QHBoxLayout(self.header_w)
        h_lay.setContentsMargins(24, 0, 24, 0)

        title_lbl = QLabel("RAWCLONE")
        title_lbl.setStyleSheet(f"""
            font-family: 'Consolas', monospace;
            font-size: 22px;
            font-weight: bold;
            color: {COLORS['accent']};
            letter-spacing: 6px;
        """)
        self.sub_lbl = QLabel(f"{tr('app_sub')}  ·  v{APP_VERSION}")
        self.sub_lbl.setStyleSheet(f"color: {COLORS['text3']}; font-size: 11px; letter-spacing: 2px;")

        v_hdr = QVBoxLayout()
        v_hdr.setSpacing(0)
        v_hdr.addWidget(title_lbl)
        v_hdr.addWidget(self.sub_lbl)
        h_lay.addLayout(v_hdr)
        h_lay.addStretch()

        # Seletor de tema
        self.lbl_theme = QLabel(tr("theme_label"))
        self.lbl_theme.setStyleSheet(
            f"color: {COLORS['text3']}; font-size: 11px; background: transparent; margin-right: 4px;")
        self.cmb_theme = QComboBox()
        self.cmb_theme.setFixedWidth(110)
        self.cmb_theme.addItem(tr("theme_dark"), "dark")
        self.cmb_theme.addItem(tr("theme_light"), "light")
        h_lay.addWidget(self.lbl_theme)
        h_lay.addWidget(self.cmb_theme)
        h_lay.addSpacing(12)

        # Seletor de idioma
        self.lbl_lang = QLabel(tr("lang_label"))
        self.lbl_lang.setStyleSheet(
            f"color: {COLORS['text3']}; font-size: 11px; background: transparent; margin-right: 4px;")
        self.cmb_lang = QComboBox()
        self.cmb_lang.setFixedWidth(170)
        for lbl_t, code in LANG_OPTIONS:
            self.cmb_lang.addItem(lbl_t, code)
        h_lay.addWidget(self.lbl_lang)
        h_lay.addWidget(self.cmb_lang)
        h_lay.addSpacing(16)

        # Admin
        self.lbl_admin = QLabel()
        self.lbl_admin.setStyleSheet("font-size: 11px; background: transparent;")
        if is_admin():
            self.lbl_admin.setText(tr("admin_yes"))
            self.lbl_admin.setStyleSheet(f"color: {COLORS['green']}; font-size: 11px; background: transparent;")
        else:
            self.lbl_admin.setText(tr("admin_no"))
            self.lbl_admin.setStyleSheet(f"color: {COLORS['yellow']}; font-size: 11px; background: transparent;")
        h_lay.addWidget(self.lbl_admin)

        root.addWidget(self.header_w)

        # ── Splitter ──────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {COLORS['border']}; }}")

        # ── Painel esquerdo ───────────────────────────────────────────────
        self.left_scroll_ref = QScrollArea()
        left_scroll = self.left_scroll_ref
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet("border: none; background: transparent;")
        left_scroll.setMinimumWidth(420)

        self.left_w = QWidget()
        self.left_w.setStyleSheet(f"background: {COLORS['bg2']}; border-right: 1px solid {COLORS['border']};")
        left_lay = QVBoxLayout(self.left_w)
        left_lay.setSpacing(16)
        left_lay.setContentsMargins(20, 20, 20, 20)

        self.sh_source = SectionHeader(tr("sec_source"))
        left_lay.addWidget(self.sh_source)
        self.src_panel = SourceDestPanel("origin_title", is_source=True)
        left_lay.addWidget(self.src_panel)
        left_lay.addWidget(Separator())

        self.sh_dest = SectionHeader(tr("sec_dest"))
        left_lay.addWidget(self.sh_dest)
        self.dst_panel = SourceDestPanel("dest_title", is_source=False)
        left_lay.addWidget(self.dst_panel)
        left_lay.addWidget(Separator())

        self.sh_opts = SectionHeader(tr("sec_options"))
        left_lay.addWidget(self.sh_opts)
        opts = QWidget()
        opts_lay = QVBoxLayout(opts)
        opts_lay.setSpacing(8)
        opts_lay.setContentsMargins(0, 0, 0, 0)

        self.chk_verify = QCheckBox(tr("chk_verify"))
        self.chk_verify.setChecked(True)
        self.chk_bad = QCheckBox(tr("chk_bad"))
        self.chk_bad.setChecked(True)
        self.chk_log = QCheckBox(tr("chk_log"))
        self.chk_log.setChecked(True)

        for chk in [self.chk_verify, self.chk_bad, self.chk_log]:
            opts_lay.addWidget(chk)
        left_lay.addWidget(opts)
        left_lay.addWidget(Separator())

        bs_row = QHBoxLayout()
        self.bs_lbl = QLabel(tr("block_size"))
        self.bs_lbl.setStyleSheet(f"color: {COLORS['text2']}; font-size: 12px; background: transparent;")
        self.cmb_bs = QComboBox()
        self.cmb_bs.setFixedWidth(120)
        for label, val in [("512 KB", 512 * 1024), ("1 MB", 1024 ** 2),
                           ("4 MB", 4 * 1024 ** 2), ("8 MB", 8 * 1024 ** 2),
                           ("16 MB", 16 * 1024 ** 2)]:
            self.cmb_bs.addItem(label, val)
        self.cmb_bs.setCurrentIndex(2)
        bs_row.addWidget(self.bs_lbl)
        bs_row.addWidget(self.cmb_bs)
        bs_row.addStretch()
        left_lay.addLayout(bs_row)

        left_lay.addStretch()

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton(tr("btn_start"))
        self.btn_start.setObjectName("btn_start")
        self.btn_pause = QPushButton(tr("btn_pause"))
        self.btn_pause.setObjectName("btn_pause")
        self.btn_cancel = QPushButton(tr("btn_cancel"))
        self.btn_cancel.setObjectName("btn_cancel")

        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)

        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_cancel)
        left_lay.addLayout(btn_row)

        left_scroll.setWidget(self.left_w)
        splitter.addWidget(left_scroll)

        # ── Painel direito ────────────────────────────────────────────────
        self.right_w = QWidget()
        self.right_w.setStyleSheet(f"background: {COLORS['bg']};")
        right_lay = QVBoxLayout(self.right_w)
        right_lay.setSpacing(12)
        right_lay.setContentsMargins(20, 20, 20, 20)

        self.prog_frame = QFrame()
        self.prog_frame.setStyleSheet(f"""
            background: {COLORS['bg2']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
        """)
        prog_lay = QHBoxLayout(self.prog_frame)
        prog_lay.setContentsMargins(20, 16, 20, 16)
        prog_lay.setSpacing(20)

        self.circular = CircularProgress()
        prog_lay.addWidget(self.circular)

        stats_grid = QWidget()
        sg_lay = QVBoxLayout(stats_grid)
        sg_lay.setSpacing(8)
        sg_lay.setContentsMargins(0, 0, 0, 0)

        self.bar_lbl = QLabel(tr("sec_progress"))
        self.bar_lbl.setStyleSheet(
            f"color: {COLORS['text3']}; font-size: 9px; letter-spacing: 2px; background: transparent;")
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(8)

        self.lbl_status = QLabel(tr("status_wait"))
        self.lbl_status.setStyleSheet(f"color: {COLORS['text2']}; font-size: 12px; background: transparent;")

        sg_lay.addWidget(self.bar_lbl)
        sg_lay.addWidget(self.prog_bar)
        sg_lay.addWidget(self.lbl_status)
        sg_lay.addSpacing(8)

        stat_row = QHBoxLayout()
        self.stat_speed = StatBox("⚡", tr("stat_speed"))
        self.stat_eta = StatBox("⏱", tr("stat_eta"))
        self.stat_copied = StatBox("📦", tr("stat_copied"))
        self.stat_bad = StatBox("⚠", tr("stat_errors"))
        for sb in [self.stat_speed, self.stat_eta, self.stat_copied, self.stat_bad]:
            stat_row.addWidget(sb)
        sg_lay.addLayout(stat_row)

        prog_lay.addWidget(stats_grid, 1)
        right_lay.addWidget(self.prog_frame)

        self.hash_frame = QFrame()
        self.hash_frame.setStyleSheet(f"""
            background: {COLORS['bg3']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            padding: 6px;
        """)
        hash_lay = QVBoxLayout(self.hash_frame)
        hash_lay.setContentsMargins(12, 8, 12, 8)
        hash_lay.setSpacing(4)

        self.h_header = QLabel(tr("sec_sha"))
        self.h_header.setStyleSheet(
            f"color: {COLORS['text3']}; font-size: 9px; letter-spacing: 2px; background: transparent;")
        hash_lay.addWidget(self.h_header)

        src_row = QHBoxLayout()
        self.lbl_hash_src_key = QLabel(tr("hash_src") + "   ")
        src_row.addWidget(self.lbl_hash_src_key)
        self.lbl_hash_src = QLabel("—")
        self.lbl_hash_src.setStyleSheet(f"color: {COLORS['text2']}; font-size: 11px; background: transparent;")
        self.lbl_hash_src.setTextInteractionFlags(Qt.TextSelectableByMouse)
        src_row.addWidget(self.lbl_hash_src, 1)
        hash_lay.addLayout(src_row)

        dst_row = QHBoxLayout()
        self.lbl_hash_dst_key = QLabel(tr("hash_dst") + " ")
        dst_row.addWidget(self.lbl_hash_dst_key)
        self.lbl_hash_dst = QLabel("—")
        self.lbl_hash_dst.setStyleSheet(f"color: {COLORS['text2']}; font-size: 11px; background: transparent;")
        self.lbl_hash_dst.setTextInteractionFlags(Qt.TextSelectableByMouse)
        dst_row.addWidget(self.lbl_hash_dst, 1)
        hash_lay.addLayout(dst_row)

        right_lay.addWidget(self.hash_frame)

        self.sh_log = SectionHeader(tr("sec_log"))
        right_lay.addWidget(self.sh_log)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(200)
        right_lay.addWidget(self.log_view, 1)

        log_btns = QHBoxLayout()
        self.btn_clear_log = QPushButton(tr("btn_clear_log"))
        self.btn_clear_log.setMinimumWidth(130)
        self.btn_save_log = QPushButton(tr("btn_save_log"))
        self.btn_save_log.setMinimumWidth(130)
        log_btns.addStretch()
        log_btns.addWidget(self.btn_clear_log)
        log_btns.addWidget(self.btn_save_log)
        right_lay.addLayout(log_btns)

        splitter.addWidget(self.right_w)
        splitter.setSizes([440, 840])
        root.addWidget(splitter, 1)

        # ── Rodapé ────────────────────────────────────────────────────────
        self.footer_w = QWidget()
        self.footer_w.setFixedHeight(28)
        self.footer_w.setStyleSheet(f"""
            background: {COLORS['bg2']};
            border-top: 1px solid {COLORS['border']};
        """)
        footer_lay = QHBoxLayout(self.footer_w)
        footer_lay.setContentsMargins(0, 0, 0, 0)
        self.footer_lbl = QLabel(tr("footer"))
        self.footer_lbl.setAlignment(Qt.AlignCenter)
        self.footer_lbl.setStyleSheet(f"""
            color: {COLORS['text3']};
            font-size: 10px;
            letter-spacing: 1px;
            font-family: 'Consolas', monospace;
            background: transparent;
        """)
        footer_lay.addWidget(self.footer_lbl)
        root.addWidget(self.footer_w)

        # ── Conexões ──────────────────────────────────────────────────────
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_clear_log.clicked.connect(self.log_view.clear)
        self.btn_save_log.clicked.connect(self._export_log)
        self.cmb_theme.currentIndexChanged.connect(self._on_theme_changed)
        self.cmb_lang.currentIndexChanged.connect(self._on_lang_changed)

    # ── Operações ─────────────────────────────────────────────────────────────

    def _log(self, msg, level="info"):
        colors = {
            "info": COLORS["text2"],
            "ok": COLORS["green"],
            "warn": COLORS["yellow"],
            "error": COLORS["red"],
        }
        c = colors.get(level, COLORS["text2"])
        ts = datetime.now().strftime("%H:%M:%S")
        line = f'<span style="color:{COLORS["text3"]}">[{ts}]</span> <span style="color:{c}">{msg}</span>'
        self.log_view.append(line)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _start(self):
        src = self.src_panel.get_path()
        dst = self.dst_panel.get_path()

        if not src:
            QMessageBox.warning(self, "RawClone", tr("dlg_no_src"))
            return
        if not dst:
            QMessageBox.warning(self, "RawClone", tr("dlg_no_dst"))
            return
        if src == dst:
            QMessageBox.warning(self, "RawClone", tr("dlg_same"))
            return

        if "\\\\.\\Physical" in dst or (not IS_WINDOWS and dst.startswith("/dev/")):
            r = QMessageBox.warning(
                self, tr("dlg_warn_title"),
                tr("dlg_warn_body", dst=dst),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if r != QMessageBox.Yes:
                return

        bs = self.cmb_bs.currentData() or BLOCK_SIZE

        options = {
            "src_compression": self.src_panel.get_compression(),
            "dst_compression": self.dst_panel.get_compression(),
            "verify": self.chk_verify.isChecked(),
            "skip_bad_sectors": self.chk_bad.isChecked(),
            "block_size": bs,
        }

        self._paused = False
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.circular.setValue(0)
        self.prog_bar.setValue(0)
        self.lbl_hash_src.setText("—")
        self.lbl_hash_dst.setText("—")
        self.lbl_status.setText("Iniciando...")

        self.worker = CopyWorker(src, dst, options)
        self.worker.sig_progress.connect(self._on_progress)
        self.worker.sig_log.connect(self._log)
        self.worker.sig_hash.connect(self._on_hash)
        self.worker.sig_finished.connect(self._on_finished)
        self.worker.sig_size.connect(self._on_size)
        self.worker.start()

    def _toggle_pause(self):
        if not self.worker:
            return
        if self._paused:
            self.worker.resume()
            self.btn_pause.setText(tr("btn_pause"))
            self._paused = False
            self.lbl_status.setText(tr("status_copying"))
        else:
            self.worker.pause()
            self.btn_pause.setText(tr("btn_resume"))
            self._paused = True
            self.lbl_status.setText(tr("status_paused"))

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
        self.lbl_status.setText(tr("status_canceling"))

    def _on_size(self, total):
        self._total_bytes = total

    def _on_progress(self, pct, speed_mb, eta_sec, bad):
        if pct >= 0:
            self.circular.setValue(pct)
            self.prog_bar.setValue(pct)

        self.stat_speed.setValue(f"{speed_mb:.1f} MB/s")
        self.stat_eta.setValue(human_eta(eta_sec))
        copied_est = int(pct / 100 * self._total_bytes) if self._total_bytes and pct >= 0 else 0
        self.stat_copied.setValue(human_size(copied_est) if copied_est else "—")
        self.stat_bad.setValue(str(bad) if bad else "0")

        if pct >= 0:
            self.lbl_status.setText(f"{tr('status_copying')}  {pct}%  —  {speed_mb:.1f} MB/s")
        else:
            self.lbl_status.setText(f"{tr('status_copying')}  {speed_mb:.1f} MB/s  ({tr('size_unknown')})")

    def _on_hash(self, h_src, h_dst):
        self.lbl_hash_src.setText(h_src)
        self.lbl_hash_dst.setText(h_dst)
        if h_src == h_dst and h_dst != "—":
            self.lbl_hash_dst.setStyleSheet(f"color: {COLORS['green']}; font-size: 11px; background: transparent;")
        elif h_dst != "—":
            self.lbl_hash_dst.setStyleSheet(f"color: {COLORS['red']}; font-size: 11px; background: transparent;")

    def _on_finished(self, success, msg):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_pause.setText(tr("btn_pause"))
        self._paused = False

        if success:
            self.circular.setValue(100)
            self.prog_bar.setValue(100)
            self.lbl_status.setText(tr("status_done"))
        else:
            self.lbl_status.setText(tr("status_err", msg=msg))

        if self.chk_log.isChecked() and success:
            self._auto_save_log()

    def _auto_save_log(self):
        try:
            dst = self.dst_panel.get_path()
            base = Path(dst).with_suffix(".log") if dst and not dst.startswith(
                "\\\\.\\") else Path.home() / f"rawclone_{datetime.now():%Y%m%d_%H%M%S}.log"
            with open(str(base), "w", encoding="utf-8") as f:
                f.write(self.log_view.toPlainText())
            self._log(tr("log_log_saved", path=base), "info")
        except Exception as e:
            self._log(tr("log_log_err", e=e), "warn")

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("btn_save_log"), f"rawclone_{datetime.now():%Y%m%d_%H%M%S}.log",
            "Arquivos de log (*.log *.txt)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log_view.toPlainText())
                self._log(tr("log_exported", path=path), "ok")
            except Exception as e:
                self._log(tr("log_error", e=e), "error")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RawClone")
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Base, QColor(COLORS["bg2"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["bg3"]))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS["bg3"]))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.Button, QColor(COLORS["bg3"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["accent2"]))
    palette.setColor(QPalette.HighlightedText, QColor(COLORS["bg"]))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()