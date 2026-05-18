#!/usr/bin/env python3
"""
plugin GIMP continu + panneau flottant GTK
Installer dans : ~/Library/Application Support/GIMP/3.2/plug-ins/Plugin3/Plugin3.py
Rendre exécutable : chmod +x Plugin3.py
"""

from __future__ import annotations

import base64
import json
import logging
import os
import struct
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zlib
from collections import deque
from datetime import datetime
from typing import Optional

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")

from gi.repository import GLib, Gimp, GimpUi, GObject, Gtk, Gio

# Configuration
SERVER_URL: str = "http://127.0.0.1:8000/predict"
CAPTURE_INTERVAL: int = 10
DELTA_THRESHOLD: float = 1.5
DIFF_GAIN: int = 15
COOLDOWN_SECONDS: int  = 60
PANEL_WIDTH: int = 320
MAX_HISTORY: int = 50

# résolution de la thumbnail utilisée pour le calcul du delta 
# et pour l'envoi au serveur (le triptyque sera à 896×448).
THUMB_W: int = 448   # inf 1024 (limite de get_thumbnail_data)
THUMB_H: int = 224   # ratio 2:1 pour coller au format triptyque

COMMAND_LABELS: dict[str, str] = {
    "brightness_contrast": "Brightness-Contrast",
    "colorize":            "Colorize",
    "desaturate":          "Desaturate",
    "edge_detect":         "Edge Detect",
    "flip":                "Flip",
    "gaussian_blur":       "Gaussian Blur",
    "hue_saturation":      "Hue-Saturation",
    "invert":              "Invert",
    "posterize":           "Posterize",
    "red_eye_removal":     "Red Eye Removal",
    "rotation":            "Rotation",
    "sharpen":             "Sharpen",
    "threshold":           "Threshold",
}

COMMAND_PATHS: dict[str, str] = {
    "brightness_contrast": "Colors → Brightness-Contrast",
    "colorize":            "Colors → Hue-Saturation (Colorize mode)",
    "desaturate":          "Colors → Desaturate",
    "edge_detect":         "Filters → Detect → Edge Detect",
    "flip":                "Image → Transform → Flip",
    "gaussian_blur":       "Filters → Blur → Gaussian Blur",
    "hue_saturation":      "Colors → Hue-Saturation",
    "invert":              "Colors → Invert",
    "posterize":           "Colors → Posterize",
    "red_eye_removal":     "Filters → Enhance → Red Eye Removal",
    "rotation":            "Image → Transform → Rotate",
    "sharpen":             "Filters → Enhance → Unsharp Mask",
    "threshold":           "Colors → Threshold",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [plugin3] %(levelname)s %(message)s",
)
logger = logging.getLogger("plugin3")


# Capture canvas -> raw RGB bytes via get_thumbnail_data()
def _capture_canvas() -> Optional[tuple[bytearray, int, int]]:
    """
    capture l'image courante en exportant via Gimp.file_save().
    retourne (rgb_flat, width, height) ou None.
    """
    images = Gimp.get_images()
    if not images:
        return None

    source = images[0]
    full_w = source.get_width()
    full_h = source.get_height()

    scale   = min(THUMB_W / full_w, THUMB_H / full_h, 1.0)
    thumb_w = max(1, int(full_w * scale))
    thumb_h = max(1, int(full_h * scale))

    work = source.duplicate()

    for layer in work.get_layers():
        try:
            layer.merge_filters()
        except Exception:
            pass 

    work.flatten()
    work.scale(thumb_w, thumb_h)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        success = Gimp.file_save(
            Gimp.RunMode.NONINTERACTIVE,
            work,
            Gio.File.new_for_path(tmp_path),
            None,
        )
        if not success or not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            logger.error("file_save() pour capture échoué.")
            return None

        with open(tmp_path, "rb") as f:
            png_bytes = f.read()

    except Exception as exc:
        logger.error("Capture canvas échouée : %s", exc, exc_info=True)
        return None
    finally:
        work.delete()
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    result = _png_to_raw_rgb(png_bytes)
    if result is None:
        logger.error("Décodage PNG de la capture échoué.")
        return None

    return result

def _export_hires_png(image: "Gimp.Image") -> Optional[bytes]:
    """
    export image en png high res via Gimp.file_save().
    return des bytes png ou None.
    utilisé pour construire le triptyque envoyé au server.
    """
    work = image.duplicate()
    work.flatten()   

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        gio_file = Gio.File.new_for_path(tmp_path)
        success  = Gimp.file_save(
            Gimp.RunMode.NONINTERACTIVE,
            work,
            gio_file,
            None,   
        )
        if not success:
            logger.error("Gimp.file_save() a retourné False.")
            return None
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            logger.error("PNG temporaire vide après export.")
            return None
        with open(tmp_path, "rb") as f:
            return f.read()
    except Exception as exc:
        logger.error("Export hires échoué : %s", exc, exc_info=True)
        return None
    finally:
        work.delete()
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# PNG pur stdlib
def _rgb_to_png(rgb: bytearray, width: int, height: int) -> bytes:
    """encode un buffer RGB plat en png minimal (stdlib seulement)."""
    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    rows = bytearray()
    for y in range(height):
        rows.append(0)  
        rs = y * width * 3
        rows.extend(rgb[rs:rs + width * 3])

    return (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', zlib.compress(bytes(rows), level=1))
            + _chunk(b'IEND', b''))


def _png_to_raw_rgb(png_bytes: bytes) -> Optional[tuple[bytearray, int, int]]:
    """décode un png en bytearray RGB plat. gère RGB/RGBA/gris en 8 bits."""
    if png_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        return None

    pos = 8
    width = height = 0
    idat: list[bytes] = []
    color_type = 0

    while pos + 8 <= len(png_bytes):
        length     = struct.unpack('>I', png_bytes[pos:pos+4])[0]
        chunk_type = png_bytes[pos+4:pos+8]
        data       = png_bytes[pos+8:pos+8+length]
        pos       += 12 + length
        if chunk_type == b'IHDR':
            width, height = struct.unpack('>II', data[:8])
            color_type    = data[9]
        elif chunk_type == b'IDAT':
            idat.append(data)
        elif chunk_type == b'IEND':
            break

    if not idat or width == 0 or height == 0:
        return None

    raw      = zlib.decompress(b''.join(idat))
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type, 3)
    stride   = width * channels + 1

    rgb      = bytearray(width * height * 3)
    prev_row = bytearray(width * channels)

    for y in range(height):
        rs  = y * stride
        fb  = raw[rs]
        row = bytearray(raw[rs+1:rs+stride])

        if fb == 1:
            for i in range(channels, len(row)):
                row[i] = (row[i] + row[i-channels]) & 0xFF
        elif fb == 2:
            for i in range(len(row)):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif fb == 3:
            for i in range(len(row)):
                a = row[i-channels] if i >= channels else 0
                row[i] = (row[i] + (a + prev_row[i]) // 2) & 0xFF
        elif fb == 4:
            for i in range(len(row)):
                a = row[i-channels] if i >= channels else 0
                b = prev_row[i]
                c = prev_row[i-channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[i] = (row[i] + pr) & 0xFF

        prev_row = row
        ob = y * width * 3
        if channels == 3:
            rgb[ob:ob+width*3] = row[:width*3]
        elif channels == 4:
            for x in range(width):
                rgb[ob+x*3:ob+x*3+3] = row[x*4:x*4+3]
        elif channels == 1:
            for x in range(width):
                v = row[x]; rgb[ob+x*3:ob+x*3+3] = bytes([v, v, v])
        elif channels == 2:
            for x in range(width):
                v = row[x*2]; rgb[ob+x*3:ob+x*3+3] = bytes([v, v, v])

    return rgb, width, height


def _mean_delta(rgb_a: bytearray, rgb_b: bytearray) -> float:
    """difference absolue moyenne par pixel, échantillonnée sur <= 10k pixels."""
    n = min(len(rgb_a), len(rgb_b)) // 3
    if n == 0:
        return 0.0
    step  = max(1, n // 10_000)
    total = 0.0
    count = 0
    for i in range(0, n * 3, step * 3):
        for c in range(3):
            total += abs(int(rgb_a[i+c]) - int(rgb_b[i+c]))
        count += 1
    return total / (count * 3) if count else 0.0


def _resize_raw(rgb: bytearray, sw: int, sh: int, dw: int, dh: int) -> bytearray:
    """nn resize d'un buffer RGB plat."""
    out = bytearray(dw * dh * 3)
    xr, yr = sw / dw, sh / dh
    for dy in range(dh):
        sy = int(dy * yr)
        for dx in range(dw):
            sx = int(dx * xr)
            si = (sy * sw + sx) * 3
            di = (dy * dw + dx) * 3
            out[di:di+3] = rgb[si:si+3]
    return out


def _build_triptych_png(before_rgb: bytearray, bw: int, bh: int,
                        after_rgb:  bytearray, aw: int, ah: int) -> bytes:
    """
    construit un triptyque 896x448 [AVANT | APRÈS | DIFFx15].
    accepte directement des buffers RGB (pas des png) pour éviter
    un aller-retour encode/decode inutile quand on vient de get_thumbnail_data.
    """
    TW, TH = 896, 448
    PW = TW // 3        # 298
    LW = TW - 2 * PW   # 300

    ra   = _resize_raw(before_rgb, bw, bh, PW, TH)
    rb   = _resize_raw(after_rgb,  aw, ah, PW, TH)
    ra_d = _resize_raw(before_rgb, bw, bh, LW, TH)
    rb_d = _resize_raw(after_rgb,  aw, ah, LW, TH)

    diff = bytearray(LW * TH * 3)
    for i in range(len(diff)):
        diff[i] = min(255, abs(int(ra_d[i]) - int(rb_d[i])) * DIFF_GAIN)

    canvas = bytearray(TW * TH * 3)
    for y in range(TH):
        rd  = y * TW * 3
        sab = y * PW * 3
        sd  = y * LW * 3
        canvas[rd:rd+PW*3]             = ra[sab:sab+PW*3]
        canvas[rd+PW*3:rd+PW*6]        = rb[sab:sab+PW*3]
        canvas[rd+PW*6:rd+PW*6+LW*3]  = diff[sd:sd+LW*3]

    return _rgb_to_png(canvas, TW, TH)


# HTTP
def _post_json(url: str, payload: dict, timeout: int = 120) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(str(exc)) from exc


# État global
class _State:
    def __init__(self):
        self.running: bool = False
        self.timer_id: Optional[int] = None
        self.prev_rgb: Optional[bytearray] = None
        self.prev_w: int = 0
        self.prev_h: int = 0
        self.last_suggestion_time: dict[str, float] = {}
        self.panel: Optional["AI2DPanel"] = None
        self.lock = threading.Lock()
        self.prev_dirty_count: int = -1

_state = _State()


# Panneau GTK flottant
class AI2DPanel:
    def __init__(self):
        self.window = Gtk.Window(title="Assistant GIMP")
        self.window.set_keep_above(True)
        self.window.set_default_size(PANEL_WIDTH, 480)
        self.window.set_resizable(True)
        self.window.connect("delete-event", self._on_close)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window.add(outer)

        # En-tête
        hrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hrow.set_halign(Gtk.Align.CENTER)
        hrow.set_margin_top(10); hrow.set_margin_bottom(6)
        self._status_dot = Gtk.Label()
        self._status_dot.set_markup("<span foreground='#2ecc71'>●</span>")
        hrow.pack_start(self._status_dot, False, False, 0)
        lbl = Gtk.Label(); lbl.set_markup("<b>Assistant GIMP</b>")
        hrow.pack_start(lbl, False, False, 0)
        outer.pack_start(hrow, False, False, 0)
        outer.pack_start(Gtk.Separator(), False, False, 0)

        # Suggestion
        sbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sbox.set_margin_start(12); sbox.set_margin_end(12)
        sbox.set_margin_top(8);    sbox.set_margin_bottom(8)
        t = Gtk.Label(); t.set_markup("<small><b>SUGGESTION ACTUELLE</b></small>")
        t.set_halign(Gtk.Align.START); sbox.pack_start(t, False, False, 0)
        self._suggestion_label = Gtk.Label(label="En attente d'un changement…")
        self._suggestion_label.set_line_wrap(True)
        self._suggestion_label.set_halign(Gtk.Align.START)
        self._suggestion_label.set_margin_top(2)
        sbox.pack_start(self._suggestion_label, False, False, 0)
        crow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        crow.pack_start(Gtk.Label(label="Confiance :"), False, False, 0)
        self._conf_bar = Gtk.ProgressBar()
        self._conf_bar.set_hexpand(True); self._conf_bar.set_valign(Gtk.Align.CENTER)
        crow.pack_start(self._conf_bar, True, True, 0)
        self._conf_pct_label = Gtk.Label(label="—"); self._conf_pct_label.set_width_chars(5)
        crow.pack_start(self._conf_pct_label, False, False, 0)
        sbox.pack_start(crow, False, False, 0)
        self._path_label = Gtk.Label(label="")
        self._path_label.set_halign(Gtk.Align.START)
        self._path_label.set_line_wrap(True); self._path_label.set_margin_top(2)
        sbox.pack_start(self._path_label, False, False, 0)
        outer.pack_start(sbox, False, False, 0)
        outer.pack_start(Gtk.Separator(), False, False, 0)

        # Historique
        hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        hbox.set_margin_start(12); hbox.set_margin_end(12); hbox.set_margin_top(8)
        th = Gtk.Label(); th.set_markup("<small><b>HISTORIQUE</b></small>")
        th.set_halign(Gtk.Align.START); hbox.pack_start(th, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(180); scroll.set_vexpand(True)
        self._history_buffer = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=self._history_buffer)
        tv.set_editable(False); tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR); tv.set_monospace(True)
        self._history_buffer.create_tag("mono", family="Monospace", size_points=9)
        scroll.add(tv); hbox.pack_start(scroll, True, True, 0)
        outer.pack_start(hbox, True, True, 0)
        outer.pack_start(Gtk.Separator(), False, False, 0)

        # Statut + Stop
        self._status_label = Gtk.Label(label="Surveillance active")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_margin_start(12); self._status_label.set_margin_end(12)
        self._status_label.set_margin_top(4);    self._status_label.set_margin_bottom(4)
        outer.pack_start(self._status_label, False, False, 0)
        btn = Gtk.Button(label="Arrêter la surveillance")
        btn.set_margin_start(12); btn.set_margin_end(12); btn.set_margin_bottom(10)
        btn.connect("clicked", self._on_stop_clicked)
        outer.pack_start(btn, False, False, 0)

        self.window.show_all()

    def update_suggestion(self, command: str, confidence: float):
        GLib.idle_add(self._update_suggestion_gtk, command, confidence)

    def add_history_entry(self, command: str, confidence: float, suppressed: bool):
        ts    = datetime.now().strftime("%H:%M:%S")
        label = COMMAND_LABELS.get(command, command)
        flag  = " [suppressed]" if suppressed else f"  {confidence:.0%}"
        GLib.idle_add(self._append_history_gtk, f"{ts}  {label:<24}{flag}\n")

    def set_status(self, text: str):
        GLib.idle_add(self._status_label.set_text, text)

    def set_monitoring_state(self, active: bool):
        color = "#2ecc71" if active else "#e74c3c"
        GLib.idle_add(self._status_dot.set_markup,
                      f"<span foreground='{color}'>●</span>")

    def _update_suggestion_gtk(self, command: str, confidence: float):
        label = COMMAND_LABELS.get(command, command)
        path  = COMMAND_PATHS.get(command, "")
        self._suggestion_label.set_markup(f"<b><big>{label}</big></b>")
        self._conf_bar.set_fraction(confidence)
        self._conf_pct_label.set_text(f"{confidence:.0%}")
        self._path_label.set_markup(f"<small><i>{path}</i></small>")
        return False

    def _append_history_gtk(self, line: str):
        it = self._history_buffer.get_end_iter()
        self._history_buffer.insert_with_tags_by_name(it, line, "mono")
        self._history_buffer.place_cursor(self._history_buffer.get_end_iter())
        return False

    def _on_stop_clicked(self, _btn): stop_monitoring()
    def _on_close(self, _win, _event): stop_monitoring(); return False
    def destroy(self): self.window.destroy()


# Thread HTTP
def _send_to_server(before_rgb: bytearray, bw: int, bh: int,
                    after_rgb:  bytearray, aw: int, ah: int):
    try:
        triptych = _build_triptych_png(before_rgb, bw, bh, after_rgb, aw, ah)
        data = _post_json(SERVER_URL, {"image_b64": base64.b64encode(triptych).decode()})

        command: str = data["command"]
        confidence: float = data["confidence"]
        suppressed: bool = data["suppressed"]

        logger.info("Serveur → %s (conf=%.3f, supprimé=%s)", command, confidence, suppressed)

        if _state.panel:
            _state.panel.add_history_entry(command, confidence, suppressed)

        if suppressed:
            return

        now = time.time()
        with _state.lock:
            if now - _state.last_suggestion_time.get(command, 0.0) < COOLDOWN_SECONDS:
                logger.info("Cooldown actif pour '%s'.", command)
                return
            _state.last_suggestion_time[command] = now

        logger.info("✅ Suggestion affichée : %s (conf=%.3f)", command, confidence)
        if _state.panel:
            _state.panel.update_suggestion(command, confidence)
            _state.panel.set_status(f"Mise à jour : {datetime.now().strftime('%H:%M:%S')}")

    except ConnectionError:
        logger.warning("Serveur inaccessible : %s", SERVER_URL)
        if _state.panel:
            _state.panel.set_status("! Serveur inaccessible")
    except Exception as exc:
        logger.error("Erreur _send_to_server : %s", exc, exc_info=True)


# Timer GLib
def _timer_tick() -> bool:
    if not _state.running:
        return False

    images = Gimp.get_images()
    if images:
        try:
            is_dirty = images[0].is_dirty()
            logger.info("image.is_dirty()=%s", is_dirty)
        except Exception:
            pass

    result = _capture_canvas()
    if result is None:
        return True

    curr_rgb, w, h = result

    if _state.prev_rgb is None:
        _state.prev_rgb = curr_rgb
        _state.prev_w = w
        _state.prev_h = h
        logger.info("Snapshot initial capturé (%dx%d via thumbnail).", w, h)
        return True

    delta = _mean_delta(_state.prev_rgb, curr_rgb)
    logger.info("Δ = %.2f (seuil = %.1f).", delta, DELTA_THRESHOLD)

    if delta >= DELTA_THRESHOLD:
        before_rgb = _state.prev_rgb
        bw, bh = _state.prev_w, _state.prev_h
        after_rgb = curr_rgb
        aw, ah = w, h

        _state.prev_rgb = curr_rgb
        _state.prev_w = w
        _state.prev_h = h

        threading.Thread(
            target=_send_to_server,
            args=(before_rgb, bw, bh, after_rgb, aw, ah),
            daemon=True,
        ).start()
    else:
        _state.prev_rgb = curr_rgb
        _state.prev_w   = w
        _state.prev_h   = h

    return True


# Démarrer / Arrêter
def start_monitoring():
    if _state.running:
        Gimp.message("Plugin3 est déjà en cours d'exécution.")
        return

    GimpUi.init("plugin3")
    _state.running = True
    _state.prev_rgb = None
    _state.last_suggestion_time.clear()

    _state.panel = AI2DPanel()
    _state.panel.set_monitoring_state(True)
    _state.panel.set_status(f"Surveillance active : toutes les {CAPTURE_INTERVAL}s")

    _state.timer_id = GLib.timeout_add_seconds(CAPTURE_INTERVAL, _timer_tick)
    logger.info("Plugin3 démarré (intervalle=%ds, seuil=%.1f).",
                CAPTURE_INTERVAL, DELTA_THRESHOLD)
    Gtk.main()


def stop_monitoring():
    if not _state.running:
        return
    _state.running = False
    if _state.timer_id is not None:
        GLib.source_remove(_state.timer_id)
        _state.timer_id = None
    if _state.panel:
        _state.panel.set_monitoring_state(False)
        _state.panel.set_status("Surveillance arrêtée.")
    logger.info("Plugin3 arrêté.")
    Gtk.main_quit()


# Enregistrement GIMP
class Plugin3(Gimp.PlugIn):
    __gtype_name__ = "Plugin3"

    def do_query_procedures(self):
        return ["plug-in-plugin3-start", "plug-in-plugin3-stop"]

    def do_create_procedure(self, name: str):
        is_start = (name == "plug-in-plugin3-start")
        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN,
            self._run_start if is_start else self._run_stop,
            None,
        )
        procedure.set_menu_label(
            "Démarrer la surveillance" if is_start else "Arrêter la surveillance"
        )
        procedure.add_menu_path("<Image>/Filters/Plugin3")
        procedure.set_documentation(
            ("Plugin3 : démarrer la surveillance continue"
             if is_start else
             "Plugin3 : arrêter la surveillance"),
            ("Capture le canvas toutes les 10s et suggère des commandes GIMP optimales."
             if is_start else
             "Arrête le moniteur en arrière-plan."),
            name,
        )
        procedure.set_attribution(
            "pai2d vlm", "pai2d", "2025"
        )
        return procedure

    @staticmethod
    def _run_start(_procedure, _run_mode, _image, _drawables, _config, _run_data):
        start_monitoring()
        return Gimp.ValueArray.new_from_values([
            GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS)
        ])

    @staticmethod
    def _run_stop(_procedure, _run_mode, _image, _drawables, _config, _run_data):
        stop_monitoring()
        return Gimp.ValueArray.new_from_values([
            GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS)
        ])


Gimp.main(Plugin3.__gtype__, sys.argv)
