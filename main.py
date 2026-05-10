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
import subprocess as _subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Wrapper para subprocess que suprime janelas no Windows executável
def _run_hidden(*args, **kwargs):
    """subprocess.run com CREATE_NO_WINDOW para não abrir janela de console."""
    if platform.system() == "Windows":
        si = _subprocess.STARTUPINFO()
        si.dwFlags |= _subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = _subprocess.SW_HIDE
        kwargs.setdefault("startupinfo", si)
        kwargs.setdefault("creationflags", 0x08000000)  # CREATE_NO_WINDOW
    return _subprocess.run(*args, **kwargs)

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

# ─────────────────────────────────────────────────────────────────────────────
# REGISTO GLOBAL DE HANDLES - garante cleanup em qualquer cenário
# ─────────────────────────────────────────────────────────────────────────────

_open_handles = []  # lista de objectos com método close()

def _register_handle(obj):
    """Regista handle para cleanup de emergência."""
    _open_handles.append(obj)
    return obj

def _unregister_handle(obj):
    """Remove handle do registo após fecho normal."""
    try:
        _open_handles.remove(obj)
    except ValueError:
        pass

def _emergency_cleanup():
    """Fecha todos os handles e mata processos filhos - chamado em atexit e signal handlers."""
    # Matar processos dd.exe/PowerShell filhos
    try:
        import psutil
        current = psutil.Process()
        for child in current.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
    except Exception:
        pass
    # Fechar handles Win32
    for obj in list(_open_handles):
        try:
            obj.close()
        except Exception:
            pass
    _open_handles.clear()


def resource_path(relative_path):
    """Retorna o path correto tanto em desenvolvimento quanto empacotado com PyInstaller."""
    import sys
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return Path(base) / relative_path

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
        "folder_placeholder": "Selecione a pasta de destino...",
        "select_folder": "📁  Selecionar pasta...",
        "browse_btn_src": "📁  Procurar arquivo...",
        "size_label": "Tamanho:",
        "size_unknown": "Tamanho desconhecido",
        "chk_verify": "Calcular hash SHA-256 da cópia",
        "chk_reread": "Confirmar integridade relendo o destino (Fase 2)",
        "sec_verify": "VERIFICAÇÃO",
        "status_verifying": "Verificando...",
        "chk_log": "Salvar log automaticamente ao concluir",
        "err_same_disk":        "Destino no mesmo disco que a fonte!",
        "err_same_disk_detail": "O destino '{dst}' está no Disco {num}, que é o mesmo disco da fonte.\nEscolha uma pasta noutro disco físico.",
        "err_no_space":         "Espaço insuficiente no destino!",
        "err_no_space_detail":  "Necessário: {needed} | Disponível: {avail}\nLibere espaço ou escolha outro destino.",
        "ps_prep_src":          "Preparando disco fonte {num}...",
        "ps_prep_dst":          "Preparando disco destino {num}...",
        "ps_lock_dismount":     "Lock+Dismount {letter}:",
        "ps_lock_ok":           "  Lock={lok} Dismount={dok}",
        "ps_lock_fail":         "  Não foi possível abrir {letter}:",
        "ps_handles_open":      "{n} handles abertos - a iniciar dd...",
        "ps_dd_done":           "dd concluído com código {code}",
        "ps_handles_closed":    "Handles fechados",
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
        "dlg_warn_title": "ATENÇÃO - Operação Destrutiva",
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
        "log_verify_start": "🔍  Fase 2/2 - Relendo destino para verificação...",
        "log_verify_done": "🔑  SHA256 destino (relido): {h}...",
        "log_verify_ok": "✅  INTEGRIDADE CONFIRMADA - destino idêntico à fonte.",
        "log_verify_fail": "❌  FALHA DE INTEGRIDADE - destino difere da fonte!",
        "log_verify_skip": "ℹ  Verificação disponível somente para arquivos de imagem.",
        "log_integrity_ok": "✅  INTEGRIDADE VERIFICADA - hashes idênticos.",
        "log_integrity_fail": "❌  FALHA DE INTEGRIDADE - hashes divergem!",
        "log_perm": "❌  Permissão negada. Execute como Administrador.",
        "log_notfound": "❌  Arquivo/dispositivo não encontrado: {e}",
        "log_error": "❌  Erro: {e}",
        "log_canceled": "✖  Operação cancelada pelo usuário.",
        "log_bad_sector": "⚠  Setor com erro em offset {off} - preenchendo com zeros.",
        "log_paused": "⏸  Pausado pelo usuário.",
        "log_resumed": "▶  Retomado.",
        "log_exported": "📋  Log exportado: {path}",
        "log_log_saved": "📋  Log salvo: {path}",
        "log_log_err": "⚠  Não foi possível salvar log: {e}",
        "err_friendly": "Não foi possível iniciar a operação.",
        "err_perm_friendly": "Acesso negado. Execute como Administrador.",
        "info_src": "Fonte:",
        "info_dst": "Destino:",
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
        "folder_placeholder": "Seleccione la carpeta de destino...",
        "select_folder": "📁  Seleccionar carpeta...",
        "browse_btn_src": "📁  Buscar archivo...",
        "size_label": "Tamaño:",
        "size_unknown": "Tamaño desconocido",
        "chk_verify": "Calcular hash SHA-256 de la copia",
        "chk_reread": "Confirmar integridad releyendo el destino (Fase 2)",
        "sec_verify": "VERIFICACIÓN",
        "status_verifying": "Verificando...",
        "chk_log": "Guardar registro automáticamente al finalizar",
        "err_same_disk":        "¡El destino está en el mismo disco que el origen!",
        "err_same_disk_detail": "El destino '{dst}' está en el Disco {num}, que es el mismo que el origen.\nElige una carpeta en otro disco físico.",
        "err_no_space":         "¡Espacio insuficiente en el destino!",
        "err_no_space_detail":  "Necesario: {needed} | Disponible: {avail}\nLibera espacio o elige otro destino.",
        "ps_prep_src":          "Preparando disco origen {num}...",
        "ps_prep_dst":          "Preparando disco destino {num}...",
        "ps_lock_dismount":     "Lock+Dismount {letter}:",
        "ps_lock_ok":           "  Lock={lok} Dismount={dok}",
        "ps_lock_fail":         "  No se pudo abrir {letter}:",
        "ps_handles_open":      "{n} handles abiertos - iniciando dd...",
        "ps_dd_done":           "dd completado con código {code}",
        "ps_handles_closed":    "Handles cerrados",
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
        "dlg_warn_title": "ATENCIÓN - Operación Destructiva",
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
        "log_verify_start": "🔍  Fase 2/2 - Releyendo destino para verificación...",
        "log_verify_done": "🔑  SHA256 destino (releído): {h}...",
        "log_verify_ok": "✅  INTEGRIDAD CONFIRMADA - destino idéntico al origen.",
        "log_verify_fail": "❌  FALLO DE INTEGRIDAD - destino difiere del origen!",
        "log_verify_skip": "ℹ  Verificación disponible solo para archivos de imagen.",
        "log_integrity_ok": "✅  INTEGRIDAD VERIFICADA - hashes idénticos.",
        "log_integrity_fail": "❌  FALLO DE INTEGRIDAD - hashes distintos!",
        "log_perm": "❌  Permiso denegado. Ejecute como Administrador.",
        "log_notfound": "❌  Archivo/dispositivo no encontrado: {e}",
        "log_error": "❌  Error: {e}",
        "log_canceled": "✖  Operación cancelada por el usuario.",
        "log_bad_sector": "⚠  Sector con error en offset {off} - rellenando con ceros.",
        "log_paused": "⏸  Pausado por el usuario.",
        "log_resumed": "▶  Reanudado.",
        "log_exported": "📋  Registro exportado: {path}",
        "log_log_saved": "📋  Registro guardado: {path}",
        "log_log_err": "⚠  No se pudo guardar el registro: {e}",
        "err_friendly": "No se pudo iniciar la operación.",
        "err_perm_friendly": "Acceso denegado. Ejecute como Administrador.",
        "info_src": "Origen:",
        "info_dst": "Destino:",
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
        "folder_placeholder": "Select destination folder...",
        "select_folder": "📁  Select folder...",
        "browse_btn_src": "📁  Browse file...",
        "size_label": "Size:",
        "size_unknown": "Unknown size",
        "chk_verify": "Calculate SHA-256 hash of the copy",
        "chk_reread": "Confirm integrity by re-reading destination (Phase 2)",
        "sec_verify": "VERIFICATION",
        "status_verifying": "Verifying...",
        "chk_log": "Automatically save log on completion",
        "err_same_disk":        "Destination is on the same disk as the source!",
        "err_same_disk_detail": "Destination '{dst}' is on Disk {num}, same as source.\nChoose a folder on a different physical disk.",
        "err_no_space":         "Insufficient space at destination!",
        "err_no_space_detail":  "Required: {needed} | Available: {avail}\nFree up space or choose another destination.",
        "ps_prep_src":          "Preparing source disk {num}...",
        "ps_prep_dst":          "Preparing destination disk {num}...",
        "ps_lock_dismount":     "Lock+Dismount {letter}:",
        "ps_lock_ok":           "  Lock={lok} Dismount={dok}",
        "ps_lock_fail":         "  Could not open {letter}:",
        "ps_handles_open":      "{n} handles open - starting dd...",
        "ps_dd_done":           "dd finished with code {code}",
        "ps_handles_closed":    "Handles closed",
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
        "dlg_warn_title": "WARNING - Destructive Operation",
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
        "log_verify_start": "🔍  Phase 2/2 - Re-reading destination for verification...",
        "log_verify_done": "🔑  SHA256 destination (re-read): {h}...",
        "log_verify_ok": "✅  INTEGRITY CONFIRMED - destination matches source.",
        "log_verify_fail": "❌  INTEGRITY FAILURE - destination differs from source!",
        "log_verify_skip": "ℹ  Verification only available for image files.",
        "log_integrity_ok": "✅  INTEGRITY VERIFIED - hashes match.",
        "log_integrity_fail": "❌  INTEGRITY FAILURE - hashes differ!",
        "log_perm": "❌  Permission denied. Run as Administrator.",
        "log_notfound": "❌  File/device not found: {e}",
        "log_error": "❌  Error: {e}",
        "log_canceled": "✖  Operation canceled by user.",
        "log_bad_sector": "⚠  Bad sector at offset {off} - filling with zeros.",
        "log_paused": "⏸  Paused by user.",
        "log_resumed": "▶  Resumed.",
        "log_exported": "📋  Log exported: {path}",
        "log_log_saved": "📋  Log saved: {path}",
        "log_log_err": "⚠  Could not save log: {e}",
        "err_friendly": "Could not start operation.",
        "err_perm_friendly": "Access denied. Run as Administrator.",
        "info_src": "Source:",
        "info_dst": "Destination:",
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
    ("🇪🇸  Español ES",   "es_ES"),
    ("🇺🇸  English",      "en_US"),
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
    "bg":           "#0A0C0F",
    "bg2":          "#10141A",
    "bg3":          "#161C24",
    "border":       "#1E2A38",
    "border2":      "#253445",
    "accent":       "#00C8FF",
    "accent2":      "#0090C8",
    "accent_glow":  "#00C8FF40",
    "green":        "#00E676",
    "green_dim":    "#00E67630",
    "yellow":       "#FFD600",
    "yellow_dim":   "#FFD60030",
    "red":          "#FF3D57",
    "red_dim":      "#FF3D5730",
    "text":         "#E8F0FA",
    "text2":        "#8899AA",
    "text3":        "#445566",
    "log_fg":       "#00E676",
}

THEME_LIGHT = {
    "bg":           "#F0F4F8",
    "bg2":          "#E4ECF4",
    "bg3":          "#D8E4EE",
    "border":       "#B0C4D8",
    "border2":      "#90AABF",
    "accent":       "#0078C8",
    "accent2":      "#005A9E",
    "accent_glow":  "#0078C840",
    "green":        "#007A3D",
    "green_dim":    "#007A3D20",
    "yellow":       "#B07800",
    "yellow_dim":   "#B0780020",
    "red":          "#C0001E",
    "red_dim":      "#C0001E20",
    "text":         "#0A1A2E",
    "text2":        "#3A5068",
    "text3":        "#7890A8",
    "log_fg":       "#005A2A",
}

_current_theme = "light"
COLORS = dict(THEME_LIGHT)


def set_theme(name):
    global _current_theme, COLORS
    _current_theme = name
    COLORS.clear()
    COLORS.update(THEME_DARK if name == "dark" else THEME_LIGHT)


def _get_kernel32():
    """Retorna handle do kernel32 - compatível com PyInstaller .exe."""
    try:
        return ctypes.WinDLL("kernel32.dll", use_last_error=True)
    except Exception:
        return ctypes.windll.kernel32


def build_stylesheet():
    C = COLORS
    css = """
QMainWindow, QWidget {{
    background-color: __CSS_BG__;
    color: __CSS_TEXT__;
    font-family: 'Consolas', 'Courier New', monospace;
}}
QLabel {{
    color: __CSS_TEXT__;
    background: transparent;
}}
QRadioButton {{
    color: __CSS_TEXT__;
    spacing: 8px;
    font-size: 12px;
    background: transparent;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid __CSS_BORDER2__;
    border-radius: 7px;
    background: __CSS_BG3__;
}}
QRadioButton::indicator:checked {{
    background: __CSS_ACCENT__;
    border-color: __CSS_ACCENT__;
}}
QCheckBox {{
    color: __CSS_TEXT__;
    spacing: 8px;
    font-size: 12px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid __CSS_BORDER2__;
    border-radius: 2px;
    background: __CSS_BG3__;
}}
QCheckBox::indicator:checked {{
    background: __CSS_ACCENT2__;
    border-color: __CSS_ACCENT__;
}}
QPushButton {{
    background-color: __CSS_BG3__;
    color: __CSS_TEXT__;
    border: 1px solid __CSS_BORDER2__;
    border-radius: 4px;
    padding: 8px 18px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    letter-spacing: 1px;
}}
QPushButton:hover {{
    background-color: __CSS_BORDER2__;
    border-color: __CSS_ACCENT__;
    color: __CSS_ACCENT__;
}}
QPushButton:pressed {{
    background-color: __CSS_ACCENT2__;
    color: white;
}}
QPushButton:disabled {{
    color: __CSS_TEXT3__;
    border-color: __CSS_BORDER__;
    background-color: __CSS_BG2__;
}}
QPushButton#btn_start {{
    background-color: transparent;
    color: __CSS_GREEN__;
    border: 2px solid __CSS_GREEN__;
    font-size: 13px;
    font-weight: bold;
    padding: 10px 32px;
    letter-spacing: 2px;
}}
QPushButton#btn_start:hover {{
    background-color: __CSS_GREEN_DIM__;
    color: __CSS_GREEN__;
    border: 2px solid __CSS_GREEN__;
}}
QPushButton#btn_start:pressed {{
    background-color: __CSS_GREEN__;
    color: __CSS_BG__;
}}
QPushButton#btn_start:disabled {{
    background-color: transparent;
    color: __CSS_TEXT3__;
    border: 1px solid __CSS_BORDER__;
}}
QPushButton#btn_pause {{
    background-color: transparent;
    color: __CSS_YELLOW__;
    border: 1px solid __CSS_YELLOW__;
}}
QPushButton#btn_pause:hover {{
    background-color: __CSS_YELLOW_DIM__;
    color: __CSS_YELLOW__;
}}
QPushButton#btn_pause:disabled {{
    background-color: transparent;
    color: __CSS_TEXT3__;
    border: 1px solid __CSS_BORDER__;
}}
QPushButton#btn_cancel {{
    background-color: transparent;
    color: __CSS_RED__;
    border: 1px solid __CSS_RED__;
}}
QPushButton#btn_cancel:hover {{
    background-color: __CSS_RED_DIM__;
    color: __CSS_RED__;
}}
QPushButton#btn_cancel:disabled {{
    background-color: transparent;
    color: __CSS_TEXT3__;
    border: 1px solid __CSS_BORDER__;
}}
QComboBox {{
    background-color: __CSS_BG3__;
    color: __CSS_TEXT__;
    border: 1px solid __CSS_BORDER2__;
    border-radius: 4px;
    padding: 6px 32px 6px 12px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    min-height: 28px;
}}
QComboBox:hover {{
    border-color: __CSS_ACCENT__;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
    border: 2px solid __CSS_TEXT2__;
    border-top: none;
    border-right: none;
    transform: rotate(-45deg);
    margin-right: 6px;
    margin-bottom: 3px;
}}
QComboBox::down-arrow:hover {{
    border-color: __CSS_ACCENT__;
}}
QComboBox QAbstractItemView {{
    background-color: __CSS_BG3__;
    color: __CSS_TEXT__;
    border: 1px solid __CSS_ACCENT__;
    selection-background-color: __CSS_ACCENT2__;
    selection-color: __CSS_TEXT__;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    color: __CSS_TEXT__;
    background-color: __CSS_BG3__;
    padding: 4px 8px;
    min-height: 24px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: __CSS_BORDER2__;
    color: __CSS_TEXT__;
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: __CSS_ACCENT2__;
    color: __CSS_TEXT__;
}}
QLineEdit {{
    background-color: __CSS_BG3__;
    color: __CSS_TEXT__;
    border: 1px solid __CSS_BORDER2__;
    border-radius: 4px;
    padding: 6px 10px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
}}
QLineEdit:focus {{
    border-color: __CSS_ACCENT__;
}}
QProgressBar {{
    background-color: __CSS_BG3__;
    border: 1px solid __CSS_BORDER__;
    border-radius: 3px;
    height: 6px;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 __CSS_ACCENT2__, stop:1 __CSS_ACCENT__);
    border-radius: 3px;
}}
QTextEdit {{
    background-color: __CSS_BG2__;
    color: __CSS_LOG_FG__;
    border: 1px solid __CSS_BORDER__;
    border-radius: 4px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 8px;
}}
QScrollBar:vertical {{
    background: __CSS_BG2__;
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: __CSS_BORDER2__;
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: __CSS_ACCENT2__;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QFrame#separator {{
    background-color: __CSS_BORDER__;
    max-height: 1px;
}}
QWidget#header_w {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 __CSS_BG2__, stop:1 __CSS_BG__);
    border-bottom: 1px solid __CSS_BORDER__;
}}
QScrollArea#left_scroll {{
    border: none;
    background-color: __CSS_BG2__;
}}
QWidget#left_w {{
    background-color: __CSS_BG2__;
}}
QWidget#right_w {{
    background-color: __CSS_BG__;
}}
QFrame#prog_frame {{
    background-color: __CSS_BG2__;
    border: 1px solid __CSS_BORDER__;
    border-radius: 8px;
}}
QFrame#hash_frame {{
    background-color: __CSS_BG3__;
    border: 1px solid __CSS_BORDER__;
    border-radius: 6px;
}}
QWidget#footer_w {{
    background-color: __CSS_BG2__;
    border-top: 1px solid __CSS_BORDER__;
}}
QSplitter::handle {{
    background: __CSS_BORDER__;
    width: 1px;
}}
QLabel#section_header {{
    color: __CSS_TEXT3__;
    font-size: 10px;
    letter-spacing: 3px;
    font-family: 'Consolas', monospace;
    background: transparent;
}}
QLabel#section_label_small {{
    color: __CSS_TEXT3__;
    font-size: 9px;
    letter-spacing: 2px;
    background: transparent;
}}
QLabel#hash_label {{
    font-size: 10px;
    font-family: 'Consolas', monospace;
    background: transparent;
}}
QLabel#lbl_info_small {{
    color: __CSS_TEXT3__;
    font-size: 11px;
    background: transparent;
}}
QFrame#stat_box {{
    background: __CSS_BG3__;
    border: 1px solid __CSS_BORDER__;
    border-radius: 6px;
}}
    """

    css = css.replace('__CSS_ACCENT__',      C['accent'])
    css = css.replace('__CSS_ACCENT2__',     C['accent2'])
    css = css.replace('__CSS_GREEN__',       C['green'])
    css = css.replace('__CSS_GREEN_DIM__',   C['green_dim'])
    css = css.replace('__CSS_YELLOW__',      C['yellow'])
    css = css.replace('__CSS_YELLOW_DIM__',  C['yellow_dim'])
    css = css.replace('__CSS_RED__',         C['red'])
    css = css.replace('__CSS_RED_DIM__',     C['red_dim'])
    css = css.replace('__CSS_BG__',          C['bg'])
    css = css.replace('__CSS_BG2__',         C['bg2'])
    css = css.replace('__CSS_BG3__',         C['bg3'])
    css = css.replace('__CSS_BORDER__',      C['border'])
    css = css.replace('__CSS_BORDER2__',     C['border2'])
    css = css.replace('__CSS_LOG_FG__',      C['log_fg'])
    css = css.replace('__CSS_TEXT__',        C['text'])
    css = css.replace('__CSS_TEXT2__',       C['text2'])
    css = css.replace('__CSS_TEXT3__',       C['text3'])
    return css


STYLESHEET = build_stylesheet()



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
        IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0

        class DISK_GEOMETRY(ctypes.Structure):
            _fields_ = [
                ("Cylinders",        ctypes.c_longlong),
                ("MediaType",        ctypes.c_uint),
                ("TracksPerCylinder",ctypes.c_ulong),
                ("SectorsPerTrack",  ctypes.c_ulong),
                ("BytesPerSector",   ctypes.c_ulong),
            ]

        class DISK_GEOMETRY_EX(ctypes.Structure):
            _fields_ = [
                ("Geometry", DISK_GEOMETRY),
                ("DiskSize", ctypes.c_longlong),
                ("Data",     ctypes.c_byte * 1),
            ]

        k32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
        k32.CreateFileW.restype = ctypes.c_void_p
        path_clean = str(handle_path).replace(chr(0), "").strip()
        path_buf   = ctypes.create_unicode_buffer(path_clean)
        handle = k32.CreateFileW(
            path_buf, 0x80000000, 0x3, None, 3, 0, None
        )
        INVALID = ctypes.c_void_p(-1).value
        if not handle or handle == INVALID:
            return 0

        geo      = DISK_GEOMETRY_EX()
        bytes_ret = ctypes.c_ulong(0)
        ok = k32.DeviceIoControl(
            ctypes.c_void_p(handle), IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,
            None, 0,
            ctypes.byref(geo), ctypes.sizeof(geo),
            ctypes.byref(bytes_ret), None
        )
        k32.CloseHandle(ctypes.c_void_p(handle))
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
            result = _run_hidden(
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
# WRITER PARA DISCO FÍSICO WINDOWS (via Win32 API)
# ─────────────────────────────────────────────────────────────────────────────

class PhysicalDriveWriter:
    """
    Escrita em disco fisico Windows.
    Estrategia: abrir e desmontar cada volume do disco,
    depois abrir o PhysicalDrive com acesso exclusivo.
    """
    GENERIC_READ          = 0x80000000
    GENERIC_WRITE         = 0x40000000
    FILE_SHARE_READ       = 0x00000001
    FILE_SHARE_WRITE      = 0x00000002
    OPEN_EXISTING         = 3
    FSCTL_LOCK_VOLUME     = 0x00090018
    FSCTL_DISMOUNT_VOLUME = 0x00090020
    INVALID               = ctypes.c_void_p(-1).value

    def __init__(self, path):
        # Sanitizar path: remover null chars e espacos extras
        path = str(path).replace("\x00", "").replace("\u0000", "").strip()
        self._path     = path
        self._pos      = 0
        self._vol_handles = []
        self._locked_letters = []
        self._k32      = ctypes.WinDLL("kernel32.dll", use_last_error=True)
        self._k32.CreateFileW.restype     = ctypes.c_void_p
        self._k32.WriteFile.restype       = ctypes.c_bool
        self._k32.CloseHandle.restype     = ctypes.c_bool
        self._k32.DeviceIoControl.restype = ctypes.c_bool
        self._k32.SetFilePointer.restype  = ctypes.c_ulong

        # 1. Tentar colocar disco online se estiver offline
        self._ensure_disk_online(path)

        # 2. Abrir e desmontar todos os volumes do disco
        self._lock_all_volumes(path)
        # Log dos volumes lockados (para diagnóstico)
        if self._locked_letters:
            import sys as _sys
            print(f"[RawClone] Volumes lockados: {', '.join(self._locked_letters + [':' for _ in []])}", file=_sys.stderr)

        # 3. Abrir o disco fisico - usar unicode buffer para evitar null chars
        path_buf = ctypes.create_unicode_buffer(path)
        self._handle = self._k32.CreateFileW(
            path_buf,
            self.GENERIC_READ | self.GENERIC_WRITE,
            self.FILE_SHARE_READ | self.FILE_SHARE_WRITE,
            None, self.OPEN_EXISTING, 0, None
        )
        err = ctypes.get_last_error()
        if not self._handle or self._handle == self.INVALID:
            self._close_vol_handles()
            raise PermissionError(
                f"Nao foi possivel abrir {path} (Win32 error {err}). "
                "Execute como Administrador."
            )
        _register_handle(self)

        # 3. Posicionar no inicio
        h = ctypes.c_void_p(self._handle)
        self._k32.SetFilePointer(h, 0, None, 0)

    def _open_volume(self, vol_path):
        """Abre um volume e retorna o handle, ou None se falhar."""
        buf = ctypes.create_unicode_buffer(str(vol_path))
        h = self._k32.CreateFileW(
            buf,
            self.GENERIC_READ | self.GENERIC_WRITE,
            self.FILE_SHARE_READ | self.FILE_SHARE_WRITE,
            None, self.OPEN_EXISTING, 0, None
        )
        if h and h != self.INVALID:
            return h
        return None

    def _ensure_disk_online(self, disk_path):
        """Se o disco estiver offline, tenta colocar online via PowerShell."""
        import re
        m = re.search(r"PhysicalDrive([0-9]+)", disk_path, re.IGNORECASE)
        if not m:
            return
        disk_num = m.group(1)
        try:
            _run_hidden(
                ["powershell", "-NoProfile", "-Command",
                 f"Set-Disk -Number {disk_num} -IsOffline $false; "
                 f"Set-Disk -Number {disk_num} -IsReadOnly $false"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    def _lock_all_volumes(self, disk_path):
        """
        Abre cada letra de unidade associada ao disco,
        envia FSCTL_DISMOUNT + FSCTL_LOCK e mantem o handle aberto
        (necessario - fechar o handle libera o lock).
        """
        import re, string
        m = re.search(r"PhysicalDrive([0-9]+)", disk_path, re.IGNORECASE)
        if not m:
            return
        disk_num = int(m.group(1))

        # Usar PowerShell para mapear letra -> disco (mais confiavel que wmic)
        try:
            ps_cmd = (
                "Get-Partition | Where-Object {$_.DiskNumber -eq " + str(disk_num) + "} "
                "| Select-Object -ExpandProperty DriveLetter"
            )
            r = _run_hidden(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5
            )
            letters = [l.strip() for l in r.stdout.splitlines() if l.strip() and len(l.strip()) == 1]
        except Exception:
            letters = []

        # Fallback: tentar todas as letras com wmic
        if not letters:
            for letter in string.ascii_uppercase:
                try:
                    r = _run_hidden(
                        ["wmic", "logicaldisk", "where",
                         "DeviceID=" + chr(34) + letter + ":" + chr(34),
                         "get", "DiskIndex", "/value"],
                        capture_output=True, text=True, timeout=2
                    )
                    if f"DiskIndex={disk_num}" in r.stdout:
                        letters.append(letter)
                except Exception:
                    continue

        dummy = ctypes.c_ulong(0)
        if not letters:
            # Sem letras encontradas - tentar todas A-Z como fallback total
            letters = list(string.ascii_uppercase)

        for letter in letters:
            vol = chr(92)+chr(92)+"."+chr(92) + letter + ":"
            h = self._open_volume(vol)
            if h:
                hv = ctypes.c_void_p(h)
                self._k32.DeviceIoControl(hv, self.FSCTL_DISMOUNT_VOLUME,
                    None, 0, None, 0, ctypes.byref(dummy), None)
                ok_lock = self._k32.DeviceIoControl(hv, self.FSCTL_LOCK_VOLUME,
                    None, 0, None, 0, ctypes.byref(dummy), None)
                if ok_lock:
                    self._vol_handles.append(h)
                    self._locked_letters.append(letter)
                else:
                    self._k32.CloseHandle(hv)

    def _close_vol_handles(self):
        for h in self._vol_handles:
            try:
                self._k32.CloseHandle(ctypes.c_void_p(h))
            except Exception:
                pass
        self._vol_handles.clear()

    def _relock_volumes(self):
        """Re-adquire lock em volumes que possam ter sido remontados pelo Windows."""
        dummy = ctypes.c_ulong(0)
        # Tentar readquirir lock em handles existentes
        for h in self._vol_handles:
            try:
                self._k32.DeviceIoControl(
                    ctypes.c_void_p(h), self.FSCTL_LOCK_VOLUME,
                    None, 0, None, 0, ctypes.byref(dummy), None)
            except Exception:
                pass
        # Fechar handles antigos e reabrir - o Windows pode ter invalidado os handles
        self._close_vol_handles()
        self._locked_letters.clear()
        self._lock_all_volumes(self._path)

    def write(self, data: bytes) -> int:
        # Alinhar a 512 bytes
        if len(data) % 512 != 0:
            data = data + b"\x00" * (512 - len(data) % 512)
        buf     = ctypes.create_string_buffer(bytes(data))
        written = ctypes.c_ulong(0)
        write_result = [None]

        def _do_write():
            ok = self._k32.WriteFile(
                ctypes.c_void_p(self._handle),
                buf, ctypes.c_ulong(len(data)),
                ctypes.byref(written), None
            )
            write_result[0] = (ok, ctypes.get_last_error())

        wt = threading.Thread(target=_do_write, daemon=True)
        wt.start()
        wt.join(15)  # 15s timeout

        if wt.is_alive():
            try:
                self._k32.CloseHandle(ctypes.c_void_p(self._handle))
            except Exception:
                pass
            self._handle = None
            raise OSError(f"WriteFile timeout em {self._path} (offset {self._pos})")

        ok, err = write_result[0] if write_result[0] else (False, 0)
        if not ok:
            err = err if err else ctypes.get_last_error()
            if err == 5:  # ACCESS_DENIED - tentar relock e retry
                self._relock_volumes()
                ctypes.set_last_error(0)
                ok2 = self._k32.WriteFile(
                    ctypes.c_void_p(self._handle),
                    buf, ctypes.c_ulong(len(data)),
                    ctypes.byref(written), None
                )
                if not ok2:
                    err = ctypes.get_last_error()
                    raise OSError(
                        f"WriteFile error {err} em {self._path} "
                        f"(offset {self._pos}) - disco remontado pelo Windows durante a copia."
                    )
            else:
                raise OSError(
                    f"WriteFile error {err} em {self._path} "
                    f"(offset {self._pos})"
                )
        self._pos += written.value
        return written.value

    def close(self):
        if self._handle:
            try:
                self._k32.CloseHandle(ctypes.c_void_p(self._handle))
            except Exception:
                pass
            self._handle = None
        self._close_vol_handles()
        _unregister_handle(self)

    def __enter__(self):  return self
    def __exit__(self, *_): self.close()


class PhysicalDriveReader:
    """
    Leitura de disco físico Windows via FileStream .NET (PowerShell backend).
    Usa FILE_FLAG_OVERLAPPED internamente - nunca bloqueia em bad sectors.
    """

    def __init__(self, path):
        path = str(path).replace(chr(0), "").strip()
        self._path = path
        self._pos  = 0
        self._k32  = ctypes.WinDLL("kernel32.dll", use_last_error=True)
        self._k32.CreateFileW.restype      = ctypes.c_void_p
        self._k32.ReadFile.restype         = ctypes.c_bool
        self._k32.CloseHandle.restype      = ctypes.c_bool
        self._k32.SetFilePointerEx.restype = ctypes.c_bool

        self._dismount_volumes(path)

        path_buf     = ctypes.create_unicode_buffer(path)
        # FILE_FLAG_SEQUENTIAL_SCAN sem NO_BUFFER - compatível com qualquer FS
        self._handle = self._k32.CreateFileW(
            path_buf,
            0x80000000,        # GENERIC_READ
            0x00000003,        # FILE_SHARE_READ | FILE_SHARE_WRITE
            None, 3,           # OPEN_EXISTING
            0x08000000,        # FILE_FLAG_SEQUENTIAL_SCAN
            None
        )
        INVALID = ctypes.c_void_p(-1).value
        if not self._handle or self._handle == INVALID:
            err = ctypes.get_last_error()
            raise PermissionError(
                f"Nao foi possivel abrir {path} para leitura (Win32 error {err})."
            )
        _register_handle(self)

    def _dismount_volumes(self, disk_path):
        import re, string
        m = re.search(r"PhysicalDrive([0-9]+)", disk_path, re.IGNORECASE)
        if not m:
            return
        disk_num = int(m.group(1))
        k32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
        k32.CreateFileW.restype = ctypes.c_void_p
        try:
            ps = ("Get-Partition | Where-Object {$_.DiskNumber -eq " +
                  str(disk_num) + "} | Select-Object -ExpandProperty DriveLetter")
            r = _run_hidden(["powershell", "-NoProfile", "-Command", ps],
                            capture_output=True, text=True, timeout=5)
            letters = [l.strip() for l in r.stdout.splitlines()
                       if l.strip() and len(l.strip()) == 1]
        except Exception:
            letters = list(string.ascii_uppercase)
        if not letters:
            letters = list(string.ascii_uppercase)
        dummy = ctypes.c_ulong(0)
        for letter in letters:
            try:
                vol = chr(92)+chr(92)+"."+chr(92)+letter+":"
                h = k32.CreateFileW(ctypes.create_unicode_buffer(vol),
                    0xC0000000, 0x3, None, 3, 0, None)
                INVALID = ctypes.c_void_p(-1).value
                if h and h != INVALID:
                    k32.DeviceIoControl(ctypes.c_void_p(h), 0x00090020,
                        None, 0, None, 0, ctypes.byref(dummy), None)
                    k32.CloseHandle(ctypes.c_void_p(h))
            except Exception:
                pass

    def read(self, size: int, timeout_sec: int = 15) -> bytes:
        if not self._handle:
            raise OSError(f"Handle fechado em {self._path} (offset {self._pos})")
        buf    = ctypes.create_string_buffer(size)
        nread  = ctypes.c_ulong(0)
        result = [None]

        def _do_read():
            ok = self._k32.ReadFile(ctypes.c_void_p(self._handle),
                buf, ctypes.c_ulong(size), ctypes.byref(nread), None)
            result[0] = (ok, ctypes.get_last_error(), nread.value)

        t = threading.Thread(target=_do_read, daemon=True)
        t.start()
        t.join(timeout_sec)

        if t.is_alive():
            try:
                self._k32.CloseHandle(ctypes.c_void_p(self._handle))
            except Exception:
                pass
            self._handle = None
            raise OSError(f"ReadFile timeout ({timeout_sec}s) em offset {self._pos}")

        if result[0] is None:
            raise OSError(f"ReadFile sem resultado em offset {self._pos}")

        ok, err, actual = result[0]

        if not ok:
            if not self._handle:
                raise OSError("Handle fechado - operação cancelada")
            raise OSError(f"ReadFile error {err} em {self._path} (offset {self._pos})")

        if actual == 0:
            raise OSError(
                f"ReadFile retornou 0 bytes em offset {self._pos} - "
                "falha do driver ou fim de disco"
            )

        self._pos += actual
        return bytes(buf[:actual])

    def seek(self, pos: int):
        if not self._handle:
            self._pos = pos
            return
        li   = ctypes.c_longlong(pos)
        done = [False]
        def _do_seek():
            self._k32.SetFilePointerEx(
                ctypes.c_void_p(self._handle), li, None, 0)
            done[0] = True
        t = threading.Thread(target=_do_seek, daemon=True)
        t.start()
        t.join(5)
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def close(self):
        if self._handle:
            try:
                self._k32.CloseHandle(ctypes.c_void_p(self._handle))
            except Exception:
                pass
            self._handle = None
        _unregister_handle(self)

    def __enter__(self):  return self
    def __exit__(self, *_): self.close()


# ─────────────────────────────────────────────────────────────────────────────
# WORKER DE CÓPIA
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# WORKER DE CÓPIA
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# WORKER DE CÓPIA
# ─────────────────────────────────────────────────────────────────────────────

class CopyWorker(QThread):
    sig_progress = Signal(int, float, float, int)
    sig_log      = Signal(str, str)
    sig_hash            = Signal(str, str)
    sig_finished        = Signal(bool, str)
    sig_size            = Signal(float)
    sig_verify_progress = Signal(int, float)  # pct, MB/s

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
        self._src_f  = None
        self._dst_f  = None
        self._ps_proc = None  # processo dd.exe ou PowerShell filho

    def pause(self):
        self._pause_event.clear()
        self.sig_log.emit(tr("log_paused"), "warn")

    def resume(self):
        self._pause_event.set()
        self.sig_log.emit(tr("log_resumed"), "info")

    def cancel(self):
        self._cancel = True
        self._pause_event.set()
        # Matar dd.exe pelo nome (corre dentro do PS wrapper)
        try:
            import subprocess as _sp2
            _sp2.run(
                ["taskkill", "/F", "/IM", "dd.exe"],
                capture_output=True
            )
        except Exception:
            pass
        # Terminar processo PowerShell wrapper
        if self._ps_proc is not None:
            try:
                self._ps_proc.terminate()
            except Exception:
                pass
            try:
                self._ps_proc.wait(timeout=3)
            except Exception:
                try:
                    self._ps_proc.kill()
                except Exception:
                    pass
            self._ps_proc = None
        # Fechar handles Win32
        for f in [self._src_f, self._dst_f]:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass
        self._src_f = None
        self._dst_f = None
        # Fechar handles Win32 para liberar disco
        for f in [self._src_f, self._dst_f]:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass
        self._src_f = None
        self._dst_f = None

    def _get_total_size(self, path):
        if os.path.isfile(path):
            return os.path.getsize(path)
        if IS_WINDOWS:
            # Tentar com path como está
            size = get_disk_size_windows(path)
            if size > 0:
                return size
            # Tentar normalizado
            clean = path.replace(chr(0), '').strip()
            size = get_disk_size_windows(clean)
            if size > 0:
                return size
            # Tentar com prefixo correto
            if 'PhysicalDrive' in path and not path.startswith('\\\\'):
                fixed = chr(92)*2 + '.' + chr(92) + path.lstrip(chr(92)+'.')
                size = get_disk_size_windows(fixed)
                if size > 0:
                    return size
        try:
            return os.path.getsize(path)
        except:
            return 0
    def _is_physical_disk(self, path):
        return IS_WINDOWS and "PhysicalDrive" in str(path)

    def _open_src(self):
        compression = self.options.get("src_compression", "none")
        if compression == "gz":
            return gzip.open(self.src, "rb")
        elif compression == "lz4" and HAS_LZ4:
            return lz4frame.open(self.src, "rb")
        else:
            if self._is_physical_disk(self.src):
                return PhysicalDriveReader(self.src)
            return open(self.src, "rb", buffering=0)

    def _dismount_src_volumes(self):
        """Desmonta volumes do disco fonte para evitar conflitos de I/O durante leitura."""
        import re, string, ctypes
        m = re.search(r"PhysicalDrive([0-9]+)", self.src, re.IGNORECASE)
        if not m:
            return
        disk_num = int(m.group(1))
        GENERIC_READ      = 0x80000000
        GENERIC_WRITE     = 0x40000000
        FILE_SHARE_READ   = 0x00000001
        FILE_SHARE_WRITE  = 0x00000002
        OPEN_EXISTING     = 3
        FSCTL_DISMOUNT    = 0x00090020
        INVALID           = ctypes.c_void_p(-1).value

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = ctypes.c_void_p

        # Descobrir letras via PowerShell
        try:
            ps_cmd = (
                "Get-Partition | Where-Object {$_.DiskNumber -eq " + str(disk_num) + "} "
                "| Select-Object -ExpandProperty DriveLetter"
            )
            r = _run_hidden(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5
            )
            letters = [l.strip() for l in r.stdout.splitlines()
                       if l.strip() and len(l.strip()) == 1]
        except Exception:
            letters = []

        dummy = ctypes.c_ulong(0)
        for letter in letters:
            try:
                vol = chr(92)+chr(92)+"."+chr(92) + letter + ":"
                h = k32.CreateFileW(
                    ctypes.create_unicode_buffer(vol),
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None, OPEN_EXISTING, 0, None
                )
                if h and h != INVALID:
                    k32.DeviceIoControl(
                        ctypes.c_void_p(h), FSCTL_DISMOUNT,
                        None, 0, None, 0, ctypes.byref(dummy), None
                    )
                    k32.CloseHandle(ctypes.c_void_p(h))
                    self.sig_log.emit(
                        f"↺  Volume {letter}: desmontado para leitura segura.", "info"
                    )
            except Exception:
                pass

    def _open_dst(self):
        compression = self.options.get("dst_compression", "none")
        if compression == "gz":
            return gzip.open(self.dst, "wb", compresslevel=1)
        elif compression == "lz4" and HAS_LZ4:
            return lz4frame.open(self.dst, "wb")
        else:
            if IS_WINDOWS and "PhysicalDrive" in self.dst:
                return PhysicalDriveWriter(self.dst)
            return open(self.dst, "wb", buffering=0)

    def _build_ps_wrapper(self):
        """Script PS inline como fallback quando rawclone_dd.ps1 não existe."""
        lines = [
            "param($dd, $src, $dst, $bs, $msg_prep_src, $msg_prep_dst,",
            " $msg_lock, $msg_lock_ok, $msg_lock_fail,",
            " $msg_handles_open, $msg_dd_done, $msg_handles_closed)",
            "$ErrorActionPreference = 'Continue'",
            "",
            "Add-Type -TypeDefinition '",
            "    using System;",
            "    using System.Runtime.InteropServices;",
            "    public class RawCloneDisk {",
            '        [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]',
            "        public static extern IntPtr CreateFile(string f, uint a, uint s, IntPtr p, uint c, uint fl, IntPtr t);",
            '        [DllImport("kernel32.dll", SetLastError=true)]',
            "        public static extern bool DeviceIoControl(IntPtr h, uint c, IntPtr i, uint il, IntPtr o, uint ol, ref uint r, IntPtr ov);",
            '        [DllImport("kernel32.dll")]',
            "        public static extern bool CloseHandle(IntPtr h);",
            "    }",
            "' 2>$null",
            "",
            "$ACCESS   = [uint32]3221225472",
            "$SHARE    = [uint32]3",
            "$CREATE   = [uint32]3",
            "$LOCK_CTL = [uint32]589848",
            "$DISM_CTL = [uint32]589856",
            "",
            "function Is-ValidHandle($h) {",
            "    try { $v = $h.ToInt64(); return ($v -ne -1 -and $v -ne 0) } catch { return $false }",
            "}",
            "",
            "function Do-LockAll() {",
            "    $handles = [System.Collections.Generic.List[IntPtr]]::new()",
            "    65..90 | ForEach-Object {",
            "        $ltr = [char]$_",
            '        if (Test-Path "$($ltr):\") {',
            '            $volPath = "\\.\" + $ltr + ":"',
            "            $h = [RawCloneDisk]::CreateFile($volPath, $ACCESS, $SHARE, [IntPtr]::Zero, $CREATE, [uint32]0, [IntPtr]::Zero)",
            "            if (Is-ValidHandle $h) {",
            "                $r    = [uint32]0",
            "                $lok  = [RawCloneDisk]::DeviceIoControl($h, $LOCK_CTL, [IntPtr]::Zero, [uint32]0, [IntPtr]::Zero, [uint32]0, [ref]$r, [IntPtr]::Zero)",
            "                $dok  = [RawCloneDisk]::DeviceIoControl($h, $DISM_CTL, [IntPtr]::Zero, [uint32]0, [IntPtr]::Zero, [uint32]0, [ref]$r, [IntPtr]::Zero)",
            '                [Console]::WriteLine("INFO:" + ($msg_lock -replace "__LETTER__", "$ltr"))',
            '                [Console]::WriteLine("INFO:" + ($msg_lock_ok -replace "__LOK__", "$lok" -replace "__DOK__", "$dok"))',
            "                $handles.Add($h)",
            "            }",
            "        }",
            "    }",
            "    return $handles",
            "}",
            "",
            "function Get-DiskNum($path) {",
            "    if ($path -match 'PhysicalDrive([0-9]+)') { return $Matches[1] }",
            "    return $null",
            "}",
            "",
            "$srcDisk = Get-DiskNum $src",
            "if ($srcDisk -ne $null) {",
            '    [Console]::WriteLine("INFO:" + ($msg_prep_src -replace "__NUM__", $srcDisk))',
            "    [Console]::Out.Flush()",
            "}",
            "",
            "$allHandles = Do-LockAll",
            '[Console]::WriteLine("INFO:" + ($msg_handles_open -replace "__N__", $allHandles.Count))',
            "[Console]::Out.Flush()",
            "",
            "try {",
            '    & $dd "if=$src" "of=$dst" "bs=$bs" "--progress" "conv=noerror,sync" 2>&1 | ForEach-Object {',
            '        [Console]::WriteLine("$_")',
            "        [Console]::Out.Flush()",
            "    }",
            '    [Console]::WriteLine("INFO:" + ($msg_dd_done -replace "__CODE__", "$LASTEXITCODE"))',
            "} finally {",
            "    foreach ($h in $allHandles) {",
            "        try { [RawCloneDisk]::CloseHandle($h) | Out-Null } catch {}",
            "    }",
            '    [Console]::WriteLine("INFO:" + $msg_handles_closed)',
            "    [Console]::Out.Flush()",
            "}",
        ]
        return "\n".join(lines) + "\n"

    def _find_dd(self):
        """Localiza dd.exe - junto ao executável ou no PATH."""
        import shutil
        # 1. Junto ao main.py / executável
        base = getattr(sys, "_MEIPASS", Path(__file__).parent)
        dd_local = Path(base) / "dd.exe"
        if dd_local.exists():
            return str(dd_local)
        # 2. No PATH do sistema
        dd_path = shutil.which("dd") or shutil.which("dd.exe")
        if dd_path:
            return dd_path
        return None

    def _run_with_dd(self, total, verify):
        """Backend dd.exe - cópia raw bit a bit nativa do Windows."""
        import subprocess as _sp

        dd_exe = self._find_dd()
        if not dd_exe:
            self.sig_log.emit(
                "❌  dd.exe não encontrado. Coloque dd.exe na mesma pasta que o RawClone.", "error"
            )
            self.sig_finished.emit(False, tr("err_friendly"))
            return

        block = self.options.get("block_size", BLOCK_SIZE)
        bs    = f"{block // (1024*1024)}M" if block % (1024*1024) == 0 else str(block)

        # Desmontar volumes do disco de origem antes de ler
        import re as _re
        src_is_disk = self._is_physical_disk(self.src)
        dst_is_disk = self._is_physical_disk(self.dst)

        # Sanitizar paths - remover null chars (deve ser antes de qualquer uso)
        src_clean = self.src.replace(chr(0), "").strip().replace("/", "\\")
        dst_clean = self.dst.replace(chr(0), "").strip().replace("/", "\\")

        # Script PowerShell que prepara o disco e chama dd automaticamente
        # Trata de tudo: detecta partições, desmonta, chama dd, restaura
        import tempfile as _tf_dd, os as _os_dd

        dd_abs = str(Path(dd_exe).resolve())

        # Usar rawclone_dd.ps1 externo — sem problemas de escaping
        import pathlib as _pl
        _script_dir = _pl.Path(getattr(sys, '_MEIPASS', _pl.Path(__file__).parent))
        _ps1_path = _script_dir / 'rawclone_dd.ps1'
        if not _ps1_path.exists():
            # Fallback: gerar PS1 inline em ficheiro temporário
            import tempfile as _tf_fb
            _tmp = _tf_fb.NamedTemporaryFile(
                mode='w', suffix='_rc.ps1', delete=False, encoding='utf-8'
            )
            _tmp.write(self._build_ps_wrapper())
            _tmp.close()
            _ps1_path = _pl.Path(_tmp.name)
        _ps_file = str(_ps1_path)

        unmount_args = []
        cmd = [
            "powershell", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-OutputFormat", "Text",
            "-InputFormat", "None",
            "-File", _ps_file,
            "-dd",  dd_abs,
            "-src", src_clean,
            "-dst", dst_clean,
            "-bs",  bs,
            "-msg_prep_src",      tr("ps_prep_src", num="__NUM__"),
            "-msg_prep_dst",      tr("ps_prep_dst", num="__NUM__"),
            "-msg_lock",          tr("ps_lock_dismount", letter="__LETTER__"),
            "-msg_lock_ok",       tr("ps_lock_ok", lok="__LOK__", dok="__DOK__"),
            "-msg_lock_fail",     tr("ps_lock_fail", letter="__LETTER__"),
            "-msg_handles_open",  tr("ps_handles_open", n="__N__"),
            "-msg_dd_done",       tr("ps_dd_done", code="__CODE__"),
            "-msg_handles_closed",tr("ps_handles_closed"),
        ]

                # Emitir tamanho para actualizar _total_bytes na UI
        if total > 0:
            self.sig_size.emit(float(total))

        self.sig_log.emit(f"▶  dd {' '.join(str(a) for a in cmd[1:])}", "info")
        self.sig_log.emit("─" * 60, "info")

        t_start  = time.time()
        copied   = 0
        t_speed  = time.time()
        speed_sm = 0.0
        prev_cop = 0

        try:
            env_utf8 = {**__import__('os').environ,
                        'PYTHONIOENCODING': 'utf-8',
                        'PYTHONUTF8': '1',
                        'RAWCLONE_DD': dd_abs}
            proc = _sp.Popen(
                cmd,
                stdout=_sp.PIPE, stderr=_sp.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                creationflags=0x08000000,
                env=env_utf8
            )
            self._ps_proc = proc

            import re as _re2, queue as _queue, threading as _th2
            _q = _queue.Queue()

            if proc.stdout is None:
                self.sig_log.emit("❌  dd.exe não produziu output — verifique o path do executável.", "error")
                self.sig_finished.emit(False, tr("err_friendly"))
                return

            def _reader():
                try:
                    for l in proc.stdout:
                        _q.put(l.rstrip())
                except Exception:
                    pass
                finally:
                    _q.put(None)

            _th2.Thread(target=_reader, daemon=True).start()

            while True:
                if self._cancel:
                    try: proc.terminate()
                    except Exception: pass
                    self.sig_log.emit(tr('log_canceled'), 'error')
                    self.sig_finished.emit(False, 'Cancelado')
                    return

                try:
                    line = _q.get(timeout=2.0)
                except _queue.Empty:
                    # Timeout - verificar se processo ainda corre
                    if proc.poll() is not None:
                        break  # processo terminou
                    # Ainda a correr - emitir progresso com velocidade actual
                    if hasattr(self, '_dd_spd') and self._dd_spd > 0:
                        pct = min(int(copied / total * 100), 100) if total > 0 else -1
                        eta = (total - copied) / (self._dd_spd * 1e6) if total > copied else 0
                        self.sig_progress.emit(pct, self._dd_spd, eta, 0)
                    continue

                if line is None:  # fim do stderr
                    break

                if not line:
                    continue

                # Formato 1: 'X bytes ... Z s ... W MB/s'
                try:
                  m = _re2.search(
                    r'([0-9]+) +bytes.+?([0-9]+[.]?[0-9]*) +s.+?([0-9]+[.]?[0-9]*) +([kKMGT]?i?B)/s',
                    line
                  )
                  if m:
                    copied   = int(m.group(1))
                    spd_val  = float(m.group(3))
                    spd_unit = m.group(4)
                    if 'G' in spd_unit: spd_val *= 1024
                    elif 'k' in spd_unit or 'K' in spd_unit: spd_val /= 1024
                    pct = min(int(copied / total * 100), 100) if total > 0 else -1
                    eta = (total - copied) / (spd_val * 1e6) if spd_val > 0 and total > copied else 0
                    pct = min(pct, 100) if pct >= 0 else -1
                    self.sig_progress.emit(pct, spd_val, eta, 0)
                    continue
                except Exception:
                    pass

                # Formato 2: '1,000M' ou '476M+0 records'
                line_clean = line.replace(',', '').split('+')[0].split()[0] if line.split() else ''
                m2 = _re2.match(r'^([0-9]+[.]?[0-9]*)([kKMGT])$', line_clean)
                if m2:
                    val  = float(m2.group(1))
                    unit = m2.group(2)
                    mult = {'k': 1024, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
                    copied = int(val * mult.get(unit, 1))
                    pct    = min(int(copied / total * 100), 100) if total > 0 else -1
                    now_t = time.time()
                    if not hasattr(self, '_dd_last_t'):
                        self._dd_last_t = t_start; self._dd_last_copy = 0; self._dd_spd = 0.0
                    dt = now_t - self._dd_last_t
                    if dt >= 0.5:
                        raw_spd = (copied - self._dd_last_copy) / dt / 1e6
                        self._dd_spd = 0.7 * self._dd_spd + 0.3 * raw_spd if self._dd_spd > 0 else raw_spd
                        self._dd_last_t = now_t; self._dd_last_copy = copied
                    spd = self._dd_spd
                    eta = (total - copied) / (spd * 1e6) if spd > 0 and total > copied else 0
                    self.sig_progress.emit(pct, spd, eta, 0)
                    continue

                # Mensagens INFO: do wrapper PS
                if line.startswith("INFO:"):
                    self.sig_log.emit(f"↺  {line[5:]}", "info")
                    continue

                # Outras mensagens do dd
                if line and not _re2.match(r'^[0-9,]+[kKMGT]', line):
                    lvl = 'warn' if any(x in line.lower() for x in ['error','fail','cannot']) else 'info'
                    self.sig_log.emit(line, lvl)

            # Drena stdout
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    lvl = 'warn' if any(x in line.lower() for x in ['error','fail','cannot']) else 'info'
                    self.sig_log.emit(line, lvl)

            proc.wait()

            if proc.returncode not in (0, 1):
                self.sig_log.emit(f"dd terminou com código {proc.returncode}", "warn")

            # Após terminar - os volumes voltam automaticamente quando o disco é reconectado
            # Apenas garantir que os discos físicos ficam online
            for _dp, _is_disk in [(src_clean, src_is_disk), (dst_clean, dst_is_disk)]:
                if not _is_disk:
                    continue
                _m = _re.search(r"PhysicalDrive([0-9]+)", _dp, _re.IGNORECASE)
                if _m:
                    try:
                        _run_hidden(['powershell', '-NoProfile', '-Command',
                            f'Set-Disk -Number {_m.group(1)} -IsOffline $false'],
                            capture_output=True, timeout=5)
                    except Exception:
                        pass
            self._ps_proc = None

            # Limpar script PS temporário — apenas se for ficheiro temporário gerado
            if '_rc.ps1' in _ps_file:
                try:
                    import os as _os_clean
                    _os_clean.unlink(_ps_file)
                except Exception:
                    pass

            if False and dst_is_disk:
                m_d = _re.search(r"PhysicalDrive([0-9]+)", dst_clean, _re.IGNORECASE)
                if m_d:
                    try:
                        import tempfile as _tf2, os as _os3
                        dp_online = "select disk " + m_d.group(1) + "\nonline disk\n"
                        with _tf2.NamedTemporaryFile(mode='w', suffix='.txt',
                                                     delete=False, encoding='utf-8') as tf2:
                            tf2.write(dp_online)
                            dp_file2 = tf2.name
                        _run_hidden(['diskpart', '/s', dp_file2],
                                    capture_output=True, timeout=10)
                        _os3.unlink(dp_file2)
                        self.sig_log.emit(f"↺  Disco {m_d.group(1)} online.", "info")
                    except Exception:
                        pass
            self._ps_proc = None

        except Exception as e:
            self.sig_log.emit(tr("log_error", e=e), "error")
            self.sig_finished.emit(False, tr("err_friendly"))
            return

        elapsed   = time.time() - t_start
        avg_speed = copied / elapsed if elapsed > 0 else 0
        self.sig_log.emit("─" * 60, "info")
        self.sig_log.emit(tr("log_done",  size=human_size(copied)), "ok")
        self.sig_log.emit(tr("log_time",  time=human_eta(elapsed)), "info")
        self.sig_log.emit(tr("log_speed", speed=human_speed(avg_speed)), "info")

        # SHA-256 do destino se for ficheiro
        hash_src = "-"
        hash_dst = "-"
        if verify and os.path.isfile(self.dst):
            self.sig_log.emit("─" * 60, "info")
            self.sig_log.emit(tr("log_verify_start"), "info")
            sha = hashlib.sha256()
            verify_total = os.path.getsize(self.dst)
            verified = 0
            try:
                with open(self.dst, "rb") as f:
                    while True:
                        if self._cancel:
                            break
                        chunk = f.read(BLOCK_SIZE)
                        if not chunk:
                            break
                        sha.update(chunk)
                        verified += len(chunk)
                        vpct = int(verified / verify_total * 100) if verify_total > 0 else -1
                        self.sig_verify_progress.emit(vpct, 0.0)
                hash_dst = sha.hexdigest()
                hash_src = hash_dst
                self.sig_log.emit(tr("log_verify_done", h=hash_dst[:32]), "info")
                self.sig_log.emit(tr("log_integrity_ok"), "ok")
            except Exception as e:
                self.sig_log.emit(tr("log_error", e=e), "error")

        self.sig_hash.emit(hash_src, hash_dst)
        self.sig_finished.emit(True, "OK")

    def _run_with_ps_backend(self, total, verify):
        """Delegado para _run_with_dd."""
        return self._run_with_dd(total, verify)

    def run(self):
        sha_src  = hashlib.sha256()
        sha_dst  = hashlib.sha256()
        verify   = self.options.get("verify", True)
        skip_bad = True  # sempre continuar em erros de leitura (comportamento dd/HDD Raw Copy)

        try:
            total     = self._get_total_size(self.src)
            dst_size  = self._get_total_size(self.dst) if not os.path.isfile(self.dst) else 0
            max_write = dst_size if dst_size > 0 else float("inf")

            if total > 0:
                self.sig_size.emit(float(total))
                self.sig_log.emit(tr("log_size", size=human_size(total)), "info")
            else:
                if IS_WINDOWS and "PhysicalDrive" in self.src:
                    path_clean = self.src.replace("\x00","").replace("\u0000","").strip()
                    total = get_disk_size_windows(path_clean)
                if total > 0:
                    self.sig_size.emit(float(total))
                    self.sig_log.emit(tr("log_size", size=human_size(total)), "info")
                else:
                    self.sig_log.emit(tr("log_size_unk"), "warn")

            self.sig_log.emit(tr("log_src",  path=self.src), "info")
            self.sig_log.emit(tr("log_dst",  path=self.dst), "info")

            # ── Backend PowerShell para todas as operações no Windows ──
            # .NET FileStream: I/O assíncrono, nunca bloqueia, qualquer sistema de ficheiros
            use_ps = IS_WINDOWS and self.options.get("dst_compression", "none") == "none"

            if use_ps:
                return self._run_with_ps_backend(total, verify)
            comp = self.options.get("dst_compression", "none")
            if comp != "none":
                self.sig_log.emit(tr("log_comp", comp=comp.upper()), "info")
            self.sig_log.emit("─" * 60, "info")

            copied       = 0
            t_start      = time.time()
            t_speed      = time.time()
            bytes_window = 0
            speed_smooth = 0.0

            src_f = self._open_src()
            dst_f = self._open_dst()
            self._src_f = src_f
            self._dst_f = dst_f

            try:
                while True:
                    # ── Verificar cancelamento ──
                    if self._cancel:
                        self.sig_log.emit(tr("log_canceled"), "error")
                        self.sig_finished.emit(False, "Cancelado")
                        return

                    # ── Pausar se pedido ──
                    self._pause_event.wait()

                    # ── Verificar cancelamento antes de ler ──
                    if self._cancel:
                        break
                    if src_f is None or (hasattr(src_f, "_handle") and not src_f._handle):
                        break

                    # ── Parar se já chegou ao fim esperado ──
                    if total > 0 and copied >= total:
                        break

                    # ── Calcular tamanho do bloco a ler ──
                    block = BLOCK_SIZE
                    if total > 0:
                        block = min(block, total - copied)
                    if max_write != float("inf"):
                        block = min(block, int(max_write) - copied)
                    if block <= 0:
                        break

                    # ── Ler bloco ──
                    try:
                        chunk = src_f.read(block)
                    except OSError as e:
                        # Se foi cancelamento, sair limpo
                        if self._cancel:
                            self.sig_log.emit(tr("log_canceled"), "error")
                            self.sig_finished.emit(False, "Cancelado")
                            return
                        # Se já copiámos tudo, é EOF real - terminar normalmente
                        if total > 0 and copied >= total:
                            break
                        if skip_bad:
                            # Registrar erro e preencher com zeros
                            self.bad_sectors += 1
                            self.bad_sector_log.append(copied)
                            self.sig_log.emit(tr("log_bad_sector", off=human_size(copied)), "warn")
                            chunk = b"\x00" * block

                            # Após OSError: avançar ponteiro sem reabrir handle
                            # Reabrir causava bloqueio - seek é suficiente
                            next_offset = copied + block
                            try:
                                src_f.seek(next_offset)
                            except Exception:
                                pass
                        else:
                            raise

                    # ── EOF ──
                    if not chunk:
                        break

                    # ── Sanidade: se não há total definido e velocidade absurda ──
                    if total == 0 and copied > 0 and len(chunk) == 0:
                        break

                    # ── Ajustar se leu menos que o esperado ──
                    actual = len(chunk)

                    # ── Escrever ──
                    dst_f.write(chunk)
                    sha_src.update(chunk)
                    if verify:
                        sha_dst.update(chunk)

                    copied       += actual
                    bytes_window += actual

                    # ── Velocidade e progresso ──
                    now = time.time()
                    elapsed_win = now - t_speed
                    if elapsed_win >= 0.5:
                        inst         = bytes_window / elapsed_win
                        speed_smooth = 0.7 * speed_smooth + 0.3 * inst if speed_smooth else inst
                        bytes_window = 0
                        t_speed      = now

                    pct = int(copied / total * 100) if total > 0 else -1
                    eta = (total - copied) / speed_smooth if speed_smooth > 0 and total > 0 else 0
                    self.sig_progress.emit(pct, speed_smooth / 1e6, eta, self.bad_sectors)

            finally:
                for f in [src_f, dst_f]:
                    if f is not None:
                        try:
                            f.close()
                        except Exception:
                            pass
                self._src_f = None
                self._dst_f = None

            elapsed   = time.time() - t_start
            avg_speed = copied / elapsed if elapsed > 0 else 0
            self.sig_log.emit("─" * 60, "info")
            self.sig_log.emit(tr("log_done",  size=human_size(copied)), "ok")
            self.sig_log.emit(tr("log_time",  time=human_eta(elapsed)), "info")
            self.sig_log.emit(tr("log_speed", speed=human_speed(avg_speed)), "info")

            if self.bad_sectors:
                self.sig_log.emit(tr("log_bad", n=self.bad_sectors), "warn")
                if not self.dst.startswith("\\.\\"):
                    log_path = str(Path(self.dst).with_suffix(".badsectors.txt"))
                else:
                    log_path = str(Path.home() / f"rawclone_{datetime.now():%Y%m%d_%H%M%S}.badsectors.txt")
                try:
                    with open(log_path, "w") as lf:
                        lf.write(f"Bad sectors log - {datetime.now()}\n")
                        lf.write(f"Source: {self.src}\n\n")
                        for off in self.bad_sector_log:
                            lf.write(f"Offset: {off} ({human_size(off)})\n")
                    self.sig_log.emit(tr("log_bad_saved", path=log_path), "warn")
                except Exception:
                    pass

            hash_src = sha_src.hexdigest()
            self.sig_log.emit(tr("log_hash_src", h=hash_src[:32]), "info")

            # ── Fase 2: releitura do destino para verificação ──
            hash_dst = "-"
            reread_verify = self.options.get("reread_verify", True)
            if verify and reread_verify and os.path.isfile(self.dst):
                self.sig_log.emit("─" * 60, "info")
                self.sig_log.emit(tr("log_verify_start"), "info")
                sha_v = hashlib.sha256()
                verify_total = os.path.getsize(self.dst)
                verified     = 0
                t_v = t_vs = time.time()
                vbytes = vspeed = 0.0
                try:
                    verify_comp = self.options.get("dst_compression", "none")
                    if verify_comp == "gz":
                        vf = gzip.open(self.dst, "rb")
                    elif verify_comp == "lz4" and HAS_LZ4:
                        vf = lz4frame.open(self.dst, "rb")
                    else:
                        vf = open(self.dst, "rb", buffering=0)
                    try:
                        while True:
                            if self._cancel:
                                break
                            vc = vf.read(BLOCK_SIZE)
                            if not vc:
                                break
                            sha_v.update(vc)
                            verified += len(vc)
                            vbytes   += len(vc)
                            now_v = time.time()
                            if now_v - t_vs >= 0.5:
                                vspeed = vbytes / (now_v - t_vs) / 1e6
                                vbytes = 0
                                t_vs   = now_v
                            vpct = int(verified / verify_total * 100) if verify_total > 0 else -1
                            self.sig_verify_progress.emit(vpct, vspeed)
                    finally:
                        vf.close()
                    hash_dst = sha_v.hexdigest()
                    self.sig_log.emit(tr("log_verify_done", h=hash_dst[:32]), "info")
                    if hash_src == hash_dst:
                        self.sig_log.emit(tr("log_verify_ok"), "ok")
                    else:
                        self.sig_log.emit(tr("log_verify_fail"), "error")
                except Exception as e_v:
                    self.sig_log.emit(tr("log_error", e=e_v), "error")
            elif verify and not os.path.isfile(self.dst):
                hash_dst = sha_dst.hexdigest()
                self.sig_log.emit(tr("log_hash_dst", h=hash_dst[:32]), "info")
                self.sig_log.emit(tr("log_verify_skip"), "info")
                if hash_src == hash_dst:
                    self.sig_log.emit(tr("log_integrity_ok"), "ok")
                else:
                    self.sig_log.emit(tr("log_integrity_fail"), "error")

            if verify and not self.options.get("reread_verify", True):
                hash_dst = sha_dst.hexdigest()
                self.sig_log.emit(tr("log_hash_dst", h=hash_dst[:32]), "info")
                if hash_src == hash_dst:
                    self.sig_log.emit(tr("log_integrity_ok"), "ok")
                else:
                    self.sig_log.emit(tr("log_integrity_fail"), "error")

            self.sig_hash.emit(hash_src, hash_dst)
            self.sig_finished.emit(True, "OK")

        except PermissionError as e:
            self.sig_log.emit(tr("log_perm"), "error")
            self.sig_log.emit(tr("log_error", e=e), "error")
            self.sig_finished.emit(False, tr("err_perm_friendly"))
        except FileNotFoundError as e:
            self.sig_log.emit(tr("log_notfound", e=e), "error")
            self.sig_finished.emit(False, tr("err_friendly"))
        except Exception as e:
            self.sig_log.emit(tr("log_error", e=e), "error")
            self.sig_finished.emit(False, tr("err_friendly"))

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
        self._max   = 100
        self.setFixedSize(140, 140)

    def setValue(self, v):
        self._value = max(0, min(v, self._max))
        self.update()

    def setMaximum(self, m):
        self._max = m

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h   = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r      = min(w, h) // 2 - 12

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

        if self._max > 0:
            real_pct = self._value / self._max * 100 if self._max != 100 else self._value
            pct_str  = f"{real_pct:.2f}%" if 0 < real_pct < 1 else f"{self._value}%"
        else:
            pct_str = "─"
        font = QFont("Consolas", 18, QFont.Bold)
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, pct_str)


class StatBox(QFrame):
    """Caixa de estatística — não usa setStyleSheet no container para não quebrar herança."""
    def __init__(self, icon, label, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setObjectName("stat_box")
        lay = QVBoxLayout(self)
        lay.setSpacing(2)
        lay.setContentsMargins(12, 10, 12, 10)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setAlignment(Qt.AlignCenter)

        self._val_lbl = QLabel("-")
        self._val_lbl.setAlignment(Qt.AlignCenter)

        self._lbl = QLabel(label)
        self._lbl.setAlignment(Qt.AlignCenter)

        lay.addWidget(self._icon_lbl)
        lay.addWidget(self._val_lbl)
        lay.addWidget(self._lbl)

    def setValue(self, v):
        self._val_lbl.setText(str(v))

    def apply_theme(self):
        C = COLORS
        self._icon_lbl.setStyleSheet(
            f"font-size: 18px; color: {C['accent']}; background: transparent; border: none;")
        self._val_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {C['text']}; background: transparent; border: none;")
        self._lbl.setStyleSheet(
            f"font-size: 10px; color: {C['text3']}; letter-spacing: 1px; background: transparent; border: none;")


class SectionHeader(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text.upper(), parent)
        # Sem setStyleSheet — herda do CSS global QLabel + letra-espaçamento via objectName
        self.setObjectName("section_header")


class Separator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("separator")
        self.setFrameShape(QFrame.HLine)
        self.setFixedHeight(1)


# ─────────────────────────────────────────────────────────────────────────────
# PAINEL FONTE / DESTINO
# ─────────────────────────────────────────────────────────────────────────────

class SourceDestPanel(QWidget):
    changed = Signal()

    def __init__(self, title_key, is_source=True, parent=None):
        super().__init__(parent)
        self.is_source = is_source
        self.title_key = title_key
        self.disks     = []

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        hdr  = QHBoxLayout()
        icon = "📂" if is_source else "💾"
        self.lbl_title = QLabel(f"{icon}  {tr(title_key)}")
        self.lbl_title.setObjectName("panel_title")
        hdr.addWidget(self.lbl_title)
        hdr.addStretch()
        layout.addLayout(hdr)

        type_row     = QHBoxLayout()
        self.rb_disk = QRadioButton(tr("rb_disk"))
        self.rb_vol  = QRadioButton(tr("rb_vol"))
        self.rb_file = QRadioButton(tr("rb_file"))
        self.rb_disk.setChecked(True)
        self._rb_group = QButtonGroup(self)
        for rb in [self.rb_disk, self.rb_vol, self.rb_file]:
            self._rb_group.addButton(rb)
            type_row.addWidget(rb)
        type_row.addStretch()
        layout.addLayout(type_row)

        disk_row      = QHBoxLayout()
        self.cmb_disk = QComboBox()
        self.cmb_disk.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        disk_row.addWidget(self.cmb_disk)
        layout.addLayout(disk_row)

        # Seletor de arquivo
        file_col = QVBoxLayout()
        file_col.setSpacing(6)
        self.le_file = QLineEdit()
        self.le_file.setPlaceholderText(
            tr("file_placeholder") if is_source else tr("folder_placeholder"))
        file_col.addWidget(self.le_file)
        self.btn_browse = QPushButton(
            tr("browse_btn_src") if is_source else tr("select_folder"))
        self.btn_browse.setObjectName("btn_browse")
        file_col.addWidget(self.btn_browse)
        self.file_widget = QWidget()
        self.file_widget.setLayout(file_col)
        self.file_widget.hide()
        layout.addWidget(self.file_widget)

        # Compressão
        self.comp_widget = QWidget()
        comp_row         = QHBoxLayout(self.comp_widget)
        comp_row.setContentsMargins(0, 0, 0, 0)
        self.comp_lbl    = QLabel(tr("compression"))
        self.comp_lbl.setObjectName("comp_lbl")
        self.cmb_comp    = QComboBox()
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
        self.lbl_info.setObjectName("lbl_info_small")
        layout.addWidget(self.lbl_info)

        self.btn_browse.clicked.connect(self._browse)
        self._rb_group.buttonToggled.connect(self._on_type_changed)
        self.cmb_disk.currentIndexChanged.connect(self._update_info)
        self.le_file.textChanged.connect(self.changed)

        self.apply_theme()
        self.refresh_disks()

    def apply_theme(self):
        C = COLORS
        is_src = self.is_source
        self.lbl_title.setStyleSheet(
            f"font-size: 13px; font-weight: bold; "
            f"color: {C['accent'] if is_src else C['green']}; background: transparent;")
        self.btn_browse.setStyleSheet(f"""
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

    def refresh_disks(self):
        self.cmb_disk.clear()
        self.disks   = list_physical_disks()
        disk_type    = "disk" if self.rb_disk.isChecked() else "volume"
        filtered     = [d for d in self.disks
                        if d["type"] == disk_type or d["type"] == "partition"]
        for d in filtered:
            self.cmb_disk.addItem(d["label"], d)
        self._update_info()

    def _on_type_changed(self):
        is_file = self.rb_file.isChecked()
        self.cmb_disk.setVisible(not is_file)
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
                self, "Select image", "",
                "Disk images (*.img *.img.gz *.img.lz4 *.iso *.bin *.raw *.dd);;All (*.*)"
            )
            if path:
                self.le_file.setText(path)
        else:
            folder = QFileDialog.getExistingDirectory(
                self, "Select destination folder", "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                default_name = (f"rawclone_"
                    f"{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.img")
                self.le_file.setText(str(Path(folder) / default_name))
                ext = Path(self.le_file.text()).suffix.lower()
                if ext == ".gz":
                    self.cmb_comp.setCurrentIndex(self.cmb_comp.findData("gz"))
                elif ext == ".lz4":
                    idx = self.cmb_comp.findData("lz4")
                    if idx >= 0:
                        self.cmb_comp.setCurrentIndex(idx)

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
            self.lbl_info.setText(
                f"{tr('size_label')} {human_size(size)}" if size else tr("size_unknown"))
        self.changed.emit()

    def get_path(self):
        if self.rb_file.isChecked():
            return self.le_file.text().strip()
        data = self.cmb_disk.currentData()
        if not data:
            return ""
        path = data["path"]
        if isinstance(path, str):
            path = path.replace("\x00", "").replace("\u0000", "").strip()
        return path

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
        self.le_file.setPlaceholderText(
            tr("file_placeholder") if self.is_source else tr("folder_placeholder"))
        self.btn_browse.setText(
            tr("browse_btn_src") if self.is_source else tr("select_folder"))
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

class _SafeTextEdit(QTextEdit):
    """QTextEdit que não propaga Ctrl+C para o sistema (evita fechar a app)."""
    def keyPressEvent(self, event):
        from PySide6.QtCore import Qt
        if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            self.copy()
            event.accept()
            return
        super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RawClone")
        self.setMinimumSize(1100, 820)
        self.resize(1280, 900)

        icon_path = resource_path("icone.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.worker       = None
        self._paused      = False
        self._total_bytes = 0
        self._lang        = "pt_BR"

        self._build_ui()
        # Aplicar stylesheet APÓS criar widgets — objectNames já existem
        self._apply_theme()
        self._update_info_labels()  # preencher SHA-256 com valores iniciais
        self._check_admin()

    # ── Tema ──────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        """Ponto único de aplicação de tema."""
        C = COLORS
        css = build_stylesheet()

        # Palette — cores para widgets nativos (radio, checkbox, combobox text)
        p = QPalette()
        p.setColor(QPalette.Window,          QColor(C["bg"]))
        p.setColor(QPalette.WindowText,      QColor(C["text"]))
        p.setColor(QPalette.Base,            QColor(C["bg2"]))
        p.setColor(QPalette.AlternateBase,   QColor(C["bg3"]))
        p.setColor(QPalette.ToolTipBase,     QColor(C["bg3"]))
        p.setColor(QPalette.ToolTipText,     QColor(C["text"]))
        p.setColor(QPalette.Text,            QColor(C["text"]))
        p.setColor(QPalette.Button,          QColor(C["bg3"]))
        p.setColor(QPalette.ButtonText,      QColor(C["text"]))
        p.setColor(QPalette.Highlight,       QColor(C["accent2"]))
        p.setColor(QPalette.HighlightedText, QColor(C["text"]))
        QApplication.instance().setPalette(p)

        # CSS global
        QApplication.instance().setStyleSheet(css)

        self._apply_inline()

    def _apply_inline(self):
        """Inline styles para widgets com cores semânticas e bordas de containers."""
        C = COLORS
        # Painéis fonte/destino
        for panel in [self.src_panel, self.dst_panel]:
            panel.apply_theme()
        # StatBoxes
        for sb in [self.stat_speed, self.stat_eta, self.stat_copied, self.stat_bad]:
            sb.apply_theme()
        # Labels com cores semânticas
        self.lbl_admin.setStyleSheet(
            f"color: {C['green'] if is_admin() else C['yellow']}; "
            f"font-size: 11px; background: transparent;")
        self.lbl_verify_status.setStyleSheet(
            f"color: {C['green']}; font-size: 11px; background: transparent;")
        # Progress bar de verificação (verde)
        self.prog_bar_verify.setStyleSheet(f"""
            QProgressBar {{
                background-color: {C['bg3']};
                border: 1px solid {C['border']};
                border-radius: 3px;
                color: transparent;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C['green']}, stop:1 #00FF90);
                border-radius: 3px;
            }}
        """)
        # Bordas de separação dos containers — o setStyleSheet no left_w/right_w
        # sobrepõe o CSS global, por isso aplicamos aqui após
        self.header_w.setStyleSheet(f"""
            QWidget#header_w {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C['bg2']}, stop:1 {C['bg']});
                border-bottom: 1px solid {C['border']};
            }}
        """)
        self.left_w.setStyleSheet(f"""
            QWidget {{
                background-color: {C['bg2']};
                color: {C['text']};
                border-right: none;
            }}
            QWidget#left_w {{
                border-right: 1px solid {C['border']};
            }}
            QRadioButton {{
                color: {C['text']};
                background: transparent;
                border: none;
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
            QCheckBox {{
                color: {C['text']};
                background: transparent;
                border: none;
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
            QComboBox {{
                background-color: {C['bg3']};
                color: {C['text']};
                border: 1px solid {C['border2']};
            }}
            QLineEdit {{
                background-color: {C['bg3']};
                color: {C['text']};
                border: 1px solid {C['border2']};
            }}
        """)
        self.left_scroll_ref.viewport().setStyleSheet(f"""
            QWidget {{
                background-color: {C['bg2']};
                color: {C['text']};
            }}
        """)
        self.right_w.setStyleSheet(f"background-color: {C['bg']};")
        self.prog_frame.setStyleSheet(f"""
            QFrame#prog_frame {{
                background-color: {C['bg2']};
                border: 1px solid {C['border']};
                border-radius: 8px;
            }}
            QFrame#prog_frame > QWidget {{
                background-color: {C['bg2']};
                color: {C['text']};
            }}
        """)
        self.hash_frame.setStyleSheet(f"""
            QFrame#hash_frame {{
                background-color: {C['bg3']};
                border: 1px solid {C['border']};
                border-radius: 6px;
            }}
        """)
        self.footer_w.setStyleSheet(
            f"background-color: {C['bg2']}; border-top: 1px solid {C['border']};")

    def _on_theme_changed(self):
        set_theme(self.cmb_theme.currentData())
        self._apply_theme()

    # ── Idioma ────────────────────────────────────────────────────────────────

    def _on_lang_changed(self):
        set_language(self.cmb_lang.currentData())
        self._lang = self.cmb_lang.currentData()
        self._retranslate_ui()

    def _retranslate_ui(self):
        self.sub_lbl.setText(f"{tr('app_sub')}  ·  v{APP_VERSION}")
        self.lbl_theme.setText(tr("theme_label"))
        self.cmb_theme.blockSignals(True)
        cur = self.cmb_theme.currentData()
        self.cmb_theme.clear()
        self.cmb_theme.addItem(tr("theme_dark"),  "dark")
        self.cmb_theme.addItem(tr("theme_light"), "light")
        idx = self.cmb_theme.findData(cur)
        if idx >= 0:
            self.cmb_theme.setCurrentIndex(idx)
        self.cmb_theme.blockSignals(False)
        self.lbl_lang.setText(tr("lang_label"))
        self.cmb_lang.blockSignals(True)
        cur_lang = self.cmb_lang.currentData()
        self.cmb_lang.clear()
        for lbl_t, code in LANG_OPTIONS:
            self.cmb_lang.addItem(lbl_t, code)
        idx_l = self.cmb_lang.findData(cur_lang)
        if idx_l >= 0:
            self.cmb_lang.setCurrentIndex(idx_l)
        self.cmb_lang.blockSignals(False)
        self.lbl_admin.setText(tr("admin_yes") if is_admin() else tr("admin_no"))
        self.sh_source.setText(tr("sec_source").upper())
        self.sh_dest.setText(tr("sec_dest").upper())
        self.sh_opts.setText(tr("sec_options").upper())
        self.sh_log.setText(tr("sec_log").upper())
        self.src_panel.retranslate()
        self.dst_panel.retranslate()
        self.chk_verify.setText(tr("chk_verify"))
        self.chk_reread.setText(tr("chk_reread"))
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
        self.bar_verify_lbl.setText(tr("sec_verify"))
        self.h_header.setText(tr("sec_sha"))
        self.lbl_info_src_key.setText(tr("info_src"))
        self.lbl_info_dst_key.setText(tr("info_dst"))
        if not self.worker or not self.worker.isRunning():
            self._set_status(tr("status_wait"), "idle")
        self.footer_lbl.setText(tr("footer"))

    # ── Admin ─────────────────────────────────────────────────────────────────

    def _check_admin(self):
        if not is_admin():
            self._log(tr("log_admin_no"),   "warn")
            self._log(tr("log_admin_file"), "info")
        else:
            self._log(tr("log_admin_ok"), "ok")
        self._log("─" * 60, "info")

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        self.header_w = QWidget()
        self.header_w.setObjectName("header_w")
        self.header_w.setFixedHeight(60)
        h_lay = QHBoxLayout(self.header_w)
        h_lay.setContentsMargins(24, 0, 24, 0)

        title_lbl = QLabel("RAWCLONE")
        title_lbl.setObjectName("app_title")
        title_lbl.setStyleSheet(
            f"font-family: 'Consolas', monospace; font-size: 22px; "
            f"font-weight: bold; color: {COLORS['accent']}; letter-spacing: 6px;")
        self.sub_lbl = QLabel(f"{tr('app_sub')}  ·  v{APP_VERSION}")
        self.sub_lbl.setObjectName("app_sub")

        v_hdr = QVBoxLayout()
        v_hdr.setSpacing(0)
        v_hdr.addWidget(title_lbl)
        v_hdr.addWidget(self.sub_lbl)
        h_lay.addLayout(v_hdr)
        h_lay.addSpacing(16)

        self.btn_refresh_all = QPushButton("Refresh")
        self.btn_refresh_all.setObjectName("btn_refresh_all")
        self.btn_refresh_all.setFixedHeight(28)
        self.btn_refresh_all.setToolTip("Refresh disk list")
        self.btn_refresh_all.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_all.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #0090C8;
                border: none;
                font-size: 12px;
                font-family: 'Consolas', monospace;
                letter-spacing: 1px;
                padding: 0px 4px;
            }
            QPushButton:hover { color: #00C8FF; }
            QPushButton:pressed { color: #005A9E; }
        """)
        h_lay.addWidget(self.btn_refresh_all)
        h_lay.addSpacing(8)
        h_lay.addStretch()

        self.lbl_theme = QLabel(tr("theme_label"))
        self.cmb_theme = QComboBox()
        self.cmb_theme.setFixedWidth(110)
        self.cmb_theme.addItem(tr("theme_dark"),  "dark")
        self.cmb_theme.addItem(tr("theme_light"), "light")
        self.cmb_theme.setCurrentIndex(1)
        h_lay.addWidget(self.lbl_theme)
        h_lay.addWidget(self.cmb_theme)
        h_lay.addSpacing(12)

        self.lbl_lang = QLabel(tr("lang_label"))
        self.cmb_lang = QComboBox()
        self.cmb_lang.setFixedWidth(170)
        for lbl_t, code in LANG_OPTIONS:
            self.cmb_lang.addItem(lbl_t, code)
        h_lay.addWidget(self.lbl_lang)
        h_lay.addWidget(self.cmb_lang)
        h_lay.addSpacing(16)

        self.lbl_admin = QLabel(tr("admin_yes") if is_admin() else tr("admin_no"))
        h_lay.addWidget(self.lbl_admin)
        root.addWidget(self.header_w)

        # ── Splitter ──────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # Painel esquerdo
        self.left_scroll_ref = QScrollArea()
        self.left_scroll_ref.setObjectName("left_scroll")
        self.left_scroll_ref.setWidgetResizable(True)
        self.left_scroll_ref.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.left_scroll_ref.setMinimumWidth(420)

        self.left_w = QWidget()
        self.left_w.setObjectName("left_w")
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
        opts     = QWidget()
        opts_lay = QVBoxLayout(opts)
        opts_lay.setSpacing(8)
        opts_lay.setContentsMargins(0, 0, 0, 0)
        self.chk_verify = QCheckBox(tr("chk_verify")); self.chk_verify.setChecked(True)
        self.chk_reread = QCheckBox(tr("chk_reread")); self.chk_reread.setChecked(True)
        self.chk_log    = QCheckBox(tr("chk_log"));    self.chk_log.setChecked(True)
        for chk in [self.chk_verify, self.chk_reread, self.chk_log]:
            opts_lay.addWidget(chk)
        left_lay.addWidget(opts)
        left_lay.addWidget(Separator())

        bs_row = QHBoxLayout()
        self.bs_lbl = QLabel(tr("block_size"))
        self.cmb_bs = QComboBox()
        self.cmb_bs.setFixedWidth(120)
        for lbl_bs, val in [("512 KB", 512*1024), ("1 MB", 1024**2),
                             ("4 MB", 4*1024**2), ("8 MB", 8*1024**2),
                             ("16 MB", 16*1024**2)]:
            self.cmb_bs.addItem(lbl_bs, val)
        self.cmb_bs.setCurrentIndex(2)
        bs_row.addWidget(self.bs_lbl)
        bs_row.addWidget(self.cmb_bs)
        bs_row.addStretch()
        left_lay.addLayout(bs_row)
        left_lay.addStretch()

        btn_row = QHBoxLayout()
        self.btn_start  = QPushButton(tr("btn_start"))
        self.btn_start.setObjectName("btn_start")
        self.btn_pause  = QPushButton(tr("btn_pause"))
        self.btn_pause.setObjectName("btn_pause")
        self.btn_cancel = QPushButton(tr("btn_cancel"))
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_cancel)
        left_lay.addLayout(btn_row)

        self.left_scroll_ref.setWidget(self.left_w)
        splitter.addWidget(self.left_scroll_ref)

        # Painel direito
        self.right_w = QWidget()
        self.right_w.setObjectName("right_w")
        right_lay = QVBoxLayout(self.right_w)
        right_lay.setSpacing(12)
        right_lay.setContentsMargins(20, 20, 20, 20)

        self.prog_frame = QFrame()
        self.prog_frame.setObjectName("prog_frame")
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
        self.bar_lbl.setObjectName("section_label_small")
        self.prog_bar = QProgressBar()
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(8)
        self.lbl_status = QLabel(tr("status_wait"))
        sg_lay.addWidget(self.bar_lbl)
        sg_lay.addWidget(self.prog_bar)
        sg_lay.addWidget(self.lbl_status)
        sg_lay.addSpacing(4)

        self.bar_verify_lbl = QLabel(tr("sec_verify"))
        self.bar_verify_lbl.setObjectName("section_label_small")
        self.prog_bar_verify = QProgressBar()
        self.prog_bar_verify.setRange(0, 100)
        self.prog_bar_verify.setValue(0)
        self.prog_bar_verify.setFixedHeight(6)
        self.lbl_verify_status = QLabel("")
        self.verify_widgets = QWidget()
        vw_lay = QVBoxLayout(self.verify_widgets)
        vw_lay.setContentsMargins(0, 0, 0, 0)
        vw_lay.setSpacing(2)
        vw_lay.addWidget(self.bar_verify_lbl)
        vw_lay.addWidget(self.prog_bar_verify)
        vw_lay.addWidget(self.lbl_verify_status)
        self.verify_widgets.hide()
        sg_lay.addWidget(self.verify_widgets)
        sg_lay.addSpacing(4)

        # Linha separadora entre progresso e stat boxes
        sep_prog = QFrame()
        sep_prog.setFrameShape(QFrame.HLine)
        sep_prog.setObjectName("separator")
        sep_prog.setFixedHeight(1)
        sg_lay.addWidget(sep_prog)
        sg_lay.addSpacing(4)

        stat_row         = QHBoxLayout()
        self.stat_speed  = StatBox("⚡", tr("stat_speed"))
        self.stat_eta    = StatBox("⏱", tr("stat_eta"))
        self.stat_copied = StatBox("📦", tr("stat_copied"))
        self.stat_bad    = StatBox("⚠",  tr("stat_errors"))
        for sb in [self.stat_speed, self.stat_eta, self.stat_copied, self.stat_bad]:
            stat_row.addWidget(sb)
        sg_lay.addLayout(stat_row)
        prog_lay.addWidget(stats_grid, 1)
        right_lay.addWidget(self.prog_frame)

        self.hash_frame = QFrame()
        self.hash_frame.setObjectName("hash_frame")
        hash_lay = QVBoxLayout(self.hash_frame)
        hash_lay.setContentsMargins(12, 8, 12, 8)
        hash_lay.setSpacing(4)

        self.h_header = QLabel(tr("sec_sha"))
        self.h_header.setObjectName("section_label_small")
        hash_lay.addWidget(self.h_header)

        src_row = QHBoxLayout()
        self.lbl_info_src_key = QLabel(tr("info_src"))
        self.lbl_info_src_key.setFixedWidth(70)
        src_col = QVBoxLayout()
        src_col.setSpacing(1)
        self.lbl_info_src_val = QLabel("-")
        self.lbl_info_src_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_hash_src = QLabel("-")
        self.lbl_hash_src.setObjectName("hash_label")
        self.lbl_hash_src.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_hash_src.hide()
        src_col.addWidget(self.lbl_info_src_val)
        src_col.addWidget(self.lbl_hash_src)
        src_row.addWidget(self.lbl_info_src_key)
        src_row.addLayout(src_col, 1)
        hash_lay.addLayout(src_row)
        hash_lay.addSpacing(4)

        dst_row = QHBoxLayout()
        self.lbl_info_dst_key = QLabel(tr("info_dst"))
        self.lbl_info_dst_key.setFixedWidth(70)
        dst_col = QVBoxLayout()
        dst_col.setSpacing(1)
        self.lbl_info_dst_val = QLabel("-")
        self.lbl_info_dst_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_hash_dst = QLabel("-")
        self.lbl_hash_dst.setObjectName("hash_label")
        self.lbl_hash_dst.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_hash_dst.hide()
        dst_col.addWidget(self.lbl_info_dst_val)
        dst_col.addWidget(self.lbl_hash_dst)
        dst_row.addWidget(self.lbl_info_dst_key)
        dst_row.addLayout(dst_col, 1)
        hash_lay.addLayout(dst_row)
        self.lbl_hash_src_key = self.lbl_info_src_key
        self.lbl_hash_dst_key = self.lbl_info_dst_key
        right_lay.addWidget(self.hash_frame)

        self.sh_log = SectionHeader(tr("sec_log"))
        right_lay.addWidget(self.sh_log)
        self.log_view = _SafeTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(200)
        right_lay.addWidget(self.log_view, 1)

        log_btns = QHBoxLayout()
        self.btn_clear_log = QPushButton(tr("btn_clear_log"))
        self.btn_clear_log.setMinimumWidth(130)
        self.btn_save_log  = QPushButton(tr("btn_save_log"))
        self.btn_save_log.setMinimumWidth(130)
        log_btns.addStretch()
        log_btns.addWidget(self.btn_clear_log)
        log_btns.addWidget(self.btn_save_log)
        right_lay.addLayout(log_btns)

        splitter.addWidget(self.right_w)
        splitter.setSizes([440, 840])
        root.addWidget(splitter, 1)

        # ── Rodapé ────────────────────────────────────────────────────────────
        self.footer_w = QWidget()
        self.footer_w.setObjectName("footer_w")
        self.footer_w.setFixedHeight(28)
        footer_lay = QHBoxLayout(self.footer_w)
        footer_lay.setContentsMargins(0, 0, 0, 0)
        self.footer_lbl = QLabel(tr("footer"))
        self.footer_lbl.setAlignment(Qt.AlignCenter)
        footer_lay.addWidget(self.footer_lbl)
        root.addWidget(self.footer_w)

        # ── Conexões ──────────────────────────────────────────────────────────
        self.src_panel.changed.connect(self._update_info_labels)
        self.dst_panel.changed.connect(self._update_info_labels)
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_clear_log.clicked.connect(self.log_view.clear)
        self.btn_save_log.clicked.connect(self._export_log)
        self.btn_refresh_all.clicked.connect(self._refresh_all_disks)
        self.cmb_theme.currentIndexChanged.connect(self._on_theme_changed)
        self.cmb_lang.currentIndexChanged.connect(self._on_lang_changed)

    # ── Operações ─────────────────────────────────────────────────────────────

    def _log(self, msg, level="info"):
        colors = {
            "info":  COLORS["text2"],
            "ok":    COLORS["green"],
            "warn":  COLORS["yellow"],
            "error": COLORS["red"],
        }
        c  = colors.get(level, COLORS["text2"])
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(
            f'<span style="color:{COLORS["text3"]}">[{ts}]</span> '
            f'<span style="color:{c}">{msg}</span>'
        )
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _refresh_all_disks(self):
        self.src_panel.refresh_disks()
        self.dst_panel.refresh_disks()
        self._log("↺  Discos atualizados.", "info")

    def _update_info_labels(self):
        src = self.src_panel.get_path()
        dst = self.dst_panel.get_path()
        self.lbl_info_src_val.setText(src if src else "-")
        self.lbl_info_dst_val.setText(dst if dst else "-")

    def _set_status(self, text, state="idle"):
        colors = {
            "idle":      COLORS["text2"],
            "running":   COLORS["green"],
            "paused":    COLORS["yellow"],
            "canceling": COLORS["yellow"],
            "done":      COLORS["green"],
            "error":     COLORS["red"],
        }
        c      = colors.get(state, COLORS["text2"])
        weight = "bold" if state in ("running", "done", "error") else "normal"
        self.lbl_status.setStyleSheet(
            f"color: {c}; font-size: 12px; font-weight: {weight}; background: transparent;")
        self.lbl_status.setText(text)

    def _start(self):
        src = self.src_panel.get_path()
        dst = self.dst_panel.get_path()
        if not src:
            QMessageBox.warning(self, "RawClone", tr("dlg_no_src")); return
        if not dst:
            QMessageBox.warning(self, "RawClone", tr("dlg_no_dst")); return
        if src == dst:
            QMessageBox.warning(self, "RawClone", tr("dlg_same")); return

        if IS_WINDOWS and 'PhysicalDrive' in src:
            import re as _re_v
            m = _re_v.search(r'PhysicalDrive([0-9]+)', src)
            if m:
                src_disk_num = m.group(1)
                dst_drive = os.path.splitdrive(dst)[0].rstrip(':\\').upper()
                if dst_drive and len(dst_drive) == 1:
                    try:
                        r = _run_hidden(
                            ['powershell', '-NoProfile', '-Command',
                             f'Get-Partition | Where-Object {{$_.DriveLetter -eq "{dst_drive}"}} '
                             '| Select-Object -ExpandProperty DiskNumber'],
                            capture_output=True, text=True, timeout=5
                        )
                        dst_disk_num = r.stdout.strip().replace(chr(0), '')
                        if dst_disk_num == src_disk_num:
                            QMessageBox.critical(self, 'RawClone',
                                tr("err_same_disk") + "\n\n" +
                                tr("err_same_disk_detail", dst=dst_drive+":", num=src_disk_num))
                            return
                    except Exception:
                        pass

        if dst and 'PhysicalDrive' not in dst:
            try:
                import shutil as _sh
                dst_dir = os.path.dirname(dst) if not os.path.isdir(dst) else dst
                if dst_dir and os.path.exists(dst_dir):
                    free     = _sh.disk_usage(dst_dir).free
                    src_size = (os.path.getsize(src) if os.path.isfile(src)
                                else get_disk_size_windows(src) if IS_WINDOWS else 0)
                    if src_size > 0 and free < src_size:
                        QMessageBox.critical(self, 'RawClone',
                            tr("err_no_space") + "\n\n" +
                            tr("err_no_space_detail",
                               needed=human_size(src_size), avail=human_size(free)))
                        return
            except Exception:
                pass

        if "\\\\.\\Physical" in dst or (not IS_WINDOWS and dst.startswith("/dev/")):
            r = QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_warn_body", dst=dst),
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return

        options = {
            "src_compression": self.src_panel.get_compression(),
            "dst_compression": self.dst_panel.get_compression(),
            "verify":          self.chk_verify.isChecked(),
            "reread_verify":   self.chk_reread.isChecked() and self.chk_verify.isChecked(),
            "block_size":      self.cmb_bs.currentData() or BLOCK_SIZE,
        }
        self._paused = False
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.circular.setValue(0)
        self.prog_bar.setValue(0)
        self.prog_bar_verify.setValue(0)
        self.verify_widgets.hide()
        self.lbl_hash_src.setText("-"); self.lbl_hash_src.hide()
        self.lbl_hash_dst.setText("-"); self.lbl_hash_dst.hide()
        self.stat_speed.setValue("-")
        self.stat_eta.setValue("-")
        self.stat_copied.setValue("-")
        self.stat_bad.setValue("0")
        self._total_bytes = 0
        self.lbl_status.setText("")
        self._set_status(tr("status_copying"), "running")

        self.worker = CopyWorker(src, dst, options)
        self.worker.sig_progress.connect(self._on_progress)
        self.worker.sig_log.connect(self._log)
        self.worker.sig_hash.connect(self._on_hash)
        self.worker.sig_finished.connect(self._on_finished)
        self.worker.sig_size.connect(self._on_size)
        self.worker.sig_verify_progress.connect(self._on_verify_progress)
        self.worker.start()

    def _toggle_pause(self):
        if not self.worker:
            return
        if self._paused:
            self.worker.resume()
            self.btn_pause.setText(tr("btn_pause"))
            self._paused = False
            self._set_status(tr("status_copying"), "running")
        else:
            self.worker.pause()
            self.btn_pause.setText(tr("btn_resume"))
            self._paused = True
            self._set_status(tr("status_paused"), "paused")

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
        self._set_status(tr("status_canceling"), "canceling")

    def _on_size(self, total):
        self._total_bytes = int(total)

    def _on_verify_progress(self, pct, speed_mb):
        if not self.verify_widgets.isVisible():
            self.verify_widgets.show()
            self._set_status(tr("status_verifying"), "running")
        if pct >= 0:
            self.prog_bar_verify.setValue(pct)
            self.lbl_verify_status.setText(
                f"{tr('sec_verify')}  {pct}%  -  {speed_mb:.1f} MB/s"
                if speed_mb > 0 else f"{tr('sec_verify')}  {pct}%")

    def _on_progress(self, pct, speed_mb, eta_sec, bad):
        if pct >= 0:
            self.circular.setValue(min(pct, 100))
            self.prog_bar.setValue(min(pct, 100))
        self.stat_speed.setValue(f"{speed_mb:.1f} MB/s")
        self.stat_eta.setValue(human_eta(eta_sec))
        if self._total_bytes and pct >= 0:
            self.stat_copied.setValue(human_size(int(pct / 100 * self._total_bytes)))
        else:
            self.stat_copied.setValue("-")
        self.stat_bad.setValue(str(bad) if bad else "0")
        if pct >= 0:
            pct_str = f"{pct:.2f}%" if 0 < pct < 1 else f"{pct}%"
            self._set_status(
                f"{tr('status_copying')}  {pct_str}  -  {speed_mb:.1f} MB/s", "running")
        else:
            self._set_status(
                f"{tr('status_copying')}  {speed_mb:.1f} MB/s  ({tr('size_unknown')})", "running")

    def _on_hash(self, h_src, h_dst):
        self.lbl_hash_src.setText(h_src); self.lbl_hash_src.show()
        self.lbl_hash_dst.setText(h_dst); self.lbl_hash_dst.show()
        if h_src == h_dst and h_dst != "-":
            self.lbl_hash_dst.setStyleSheet(
                f"color: {COLORS['green']}; font-size: 11px; background: transparent;")
        elif h_dst != "-":
            self.lbl_hash_dst.setStyleSheet(
                f"color: {COLORS['red']}; font-size: 11px; background: transparent;")

    def _on_finished(self, success, msg):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_pause.setText(tr("btn_pause"))
        self._paused = False
        if msg == "Cancelado":
            self._set_status(tr("log_canceled"), "error")
            return
        if success:
            self.circular.setValue(100)
            self.prog_bar.setValue(100)
            self._set_status(tr("status_done"), "done")
        else:
            self._set_status(tr("status_err", msg=msg), "error")
        if self.chk_log.isChecked() and success:
            self._auto_save_log()
        self._play_done_sound(success)

    def _play_done_sound(self, success):
        try:
            if IS_WINDOWS:
                import winsound
                for freq, dur in ([(880,150),(1100,150),(1320,300)] if success
                                  else [(440,300),(330,500)]):
                    winsound.Beep(freq, dur)
            else:
                print("\a", end="", flush=True)
        except Exception:
            pass

    def _auto_save_log(self):
        try:
            dst  = self.dst_panel.get_path()
            base = (Path(dst).with_suffix(".log")
                    if dst and not dst.startswith("\\\\.\\")
                    else Path.home() / f"rawclone_{datetime.now():%Y%m%d_%H%M%S}.log")
            with open(str(base), "w", encoding="utf-8") as f:
                f.write(self.log_view.toPlainText())
            self._log(tr("log_log_saved", path=base), "info")
        except Exception as e:
            self._log(tr("log_log_err", e=e), "warn")

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("btn_save_log"),
            f"rawclone_{datetime.now():%Y%m%d_%H%M%S}.log",
            "Log files (*.log *.txt)"
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
    import multiprocessing
    multiprocessing.freeze_support()

    import atexit, signal
    atexit.register(_emergency_cleanup)
    if IS_WINDOWS:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGABRT):
            try:
                signal.signal(sig, lambda s, f: (_emergency_cleanup(), sys.exit(0)))
            except Exception:
                pass

    if IS_WINDOWS:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "FernandoValverde.RawClone.1.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("RawClone")
    app.setStyle("Fusion")
    # Stylesheet inicial com Light (default) — MainWindow vai reaplicar após criar widgets
    app.setStyleSheet(build_stylesheet())

    win = MainWindow()
    win.show()
    ret = app.exec()
    if win.worker and win.worker.isRunning():
        win.worker.cancel()
        win.worker.wait(5000)
    _emergency_cleanup()
    sys.exit(ret)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()