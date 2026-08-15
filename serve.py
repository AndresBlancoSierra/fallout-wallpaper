#!/usr/bin/env python3
"""
VAULT-TEC SERVER — sirve fallout-stats.html desde $HOME (como el http.server
anterior) y expone un endpoint /api/gym que lee el vault de Obsidian de GYM
y devuelve el progreso en kg por ejercicio.

Cada .md dentro de GYM/{Push,Pull,Leg} es un ejercicio; cada fila de su tabla
es una sesión (columna 1 = peso en kg). Se calcula el aumento de kg entre la
primera y la última sesión con peso numérico.
"""

import json
import os
import re
import subprocess
import tempfile
import threading
import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("FALLOUT_PORT", "8123"))
GYM_ROOT = Path(os.environ.get(
    "GYM_ROOT", os.path.expanduser("~/Documents/obsidian/Me/GYM")))
POINTS_FILE = Path(os.environ.get(
    "POINTS_FILE", os.path.expanduser("~/Documents/obsidian/Me/points.md")))
READ_FILE = Path(os.environ.get(
    "READ_FILE", os.path.expanduser("~/Documents/obsidian/Me/Read/Read.md")))
GROUPS = ("Push", "Pull", "Leg")

# Stats que admiten clic manual (mismo orden/llaves que SPECIAL en el HTML).
# Racha = días consecutivos: barra 0-365. GERMAN/HACKERMAN son de Anki (sin clic).
MANUAL_STATS = ("GYM", "VOLLEY", "MEDITATION", "DRAW", "COOL SHOWER", "READ")
# Fechas en ISO local (YYYY-MM-DD)
_today = datetime.date.today
_today_str = lambda: _today().isoformat()
_yesterday_str = lambda: (_today() - datetime.timedelta(days=1)).isoformat()


def _num(value):
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_gym():
    result = {}
    for group in GROUPS:
        folder = GYM_ROOT / group
        result[group] = []
        if not folder.is_dir():
            continue
        for md in sorted(folder.glob("*.md")):
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rows = []
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("|"):
                    rows.append([c.strip() for c in s.strip("|").split("|")])
            sessions = []
            for r in rows[2:]:
                if not r:
                    continue
                w = _num(r[0])
                if w is not None:
                    sessions.append(w)
            if sessions:
                entry = {
                    "name": md.stem,
                    "initial": sessions[0],
                    "last": sessions[-1],
                    "delta": round(sessions[-1] - sessions[0], 2),
                    "sessions": len(sessions),
                }
            else:
                entry = {
                    "name": md.stem,
                    "initial": None,
                    "last": None,
                    "delta": None,
                    "sessions": 0,
                }
            result[group].append(entry)
    return result


def parse_read():
    """Lee Read/Read.md: líneas con checkbox. [x]=terminado, [ ]=en progreso."""
    done, progress = [], []
    try:
        text = READ_FILE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"done": [], "progress": []}
    for line in text.splitlines():
        m = re.match(r"^\s*-\s*\[([ xX])\]\s*(.+?)\s*$", line)
        if m:
            title = m.group(2).strip()
            if m.group(1) in ("x", "X"):
                done.append(title)
            else:
                progress.append(title)
    return {"done": done, "progress": progress}


def default_points():
    return {"streaks": {s: {"n": 0, "last": None} for s in MANUAL_STATS},
            "done": {}}


def parse_points():
    """Lee el bloque ```json ... ``` de points.md y devuelve streaks/done."""
    data = default_points()
    try:
        text = POINTS_FILE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return data
    block = None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("```json"):
            block = []
            for rest in lines[i + 1:]:
                if rest.strip().startswith("```"):
                    break
                block.append(rest)
            break
    if block is None:
        return data
    try:
        raw = json.loads("\n".join(block))
    except (TypeError, ValueError):
        return data
    streaks = raw.get("streaks") or {}
    done = raw.get("done") or {}
    norm = {}
    for s in MANUAL_STATS:
        v = streaks.get(s) or {}
        try:
            n = int(v.get("n", 0) or 0)
        except (TypeError, ValueError):
            n = 0
        norm[s] = {"n": max(0, n), "last": v.get("last")}
    data["streaks"] = norm
    data["done"] = {str(k): str(v) for k, v in done.items()}
    return data


def write_points(data):
    """Escribe points.md de forma atómica (tmp + rename) preservando el bloque json."""
    streaks = data.get("streaks") or {}
    done = data.get("done") or {}
    payload = {"streaks": {s: streaks.get(s, {"n": 0, "last": None}) for s in MANUAL_STATS},
               "done": done}
    content = (
        "# Vault-Tec Points\n"
        "\n"
        "Base de datos de puntos (contadores diarios). No editar a mano.\n"
        "Se actualiza automáticamente al hacer clic en el wallpaper.\n"
        "\n"
        "```json\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        "```\n"
    )
    POINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(POINTS_FILE.parent),
                               prefix=".points.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, str(POINTS_FILE))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Handler(SimpleHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle_alert(self):
        # El wallpaper avisa cuando cambia el estado de error y aquí cambiamos
        # el tema de TODO el escritorio a rojo (on) o lo revertimos (off).
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, TypeError):
            payload = {}
        state = bool(payload.get("state"))
        mode = "on" if state else "off"
        script = os.path.expanduser("~/.local/bin/fallout-alert-mode.sh")
        try:
            subprocess.Popen([script, mode],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            pass
        self._send_json({"ok": True, "mode": mode})

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, TypeError):
            return {}

    def _handle_read(self):
        # Toggle de una checkbox de libro en Read/Read.md: [ ] <-> [x].
        payload = self._read_body()
        book = str(payload.get("book") or "").strip()
        if not book:
            self._send_json({"error": "falta 'book'"}, status=400)
            return
        try:
            text = READ_FILE.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        lines = text.split("\n")
        target = book.casefold()
        found = False
        for i, line in enumerate(lines):
            m = re.match(r"^(\s*-\s*\[)([ xX])(\]\s*)(.*?)\s*$", line)
            if not m:
                continue
            if m.group(4).casefold() != target:
                continue
            new_box = " " if m.group(2) in ("x", "X") else "x"
            lines[i] = f"{m.group(1)}{new_box}{m.group(3)}{m.group(4).strip()}"
            found = True
            break
        if found:
            READ_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(READ_FILE.parent),
                                       prefix=".read.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                os.replace(tmp, str(READ_FILE))
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        self._send_json(parse_read())

    def do_GET(self):
        if self.path.startswith("/api/gym"):
            try:
                self._send_json(parse_gym())
            except Exception:
                self._send_json({"error": "no se pudo leer el vault"})
            return
        if self.path.startswith("/api/read"):
            try:
                self._send_json(parse_read())
            except Exception:
                self._send_json({"error": "no se pudo leer Read/Read.md"}, status=500)
            return
        if self.path.startswith("/api/points"):
            try:
                self._send_json(parse_points())
            except Exception:
                self._send_json({"error": "no se pudo leer points.md"}, status=500)
            return
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/alert"):
            self._handle_alert()
            return
        if self.path.startswith("/api/read"):
            self._handle_read()
            return
        if not self.path.startswith("/api/points"):
            self.send_response(404)
            self.end_headers()
            return
        payload = self._read_body()
        stat = str(payload.get("stat") or "").upper()
        action = str(payload.get("action") or "").lower()
        if stat not in MANUAL_STATS or action not in ("inc", "dec"):
            self._send_json({"error": "stat/action inválidos"}, status=400)
            return
        try:
            data = parse_points()
            sdata = data["streaks"].get(stat, {"n": 0, "last": None})
            prev = int(sdata.get("n") or 0)
            if action == "inc":
                n = prev + 1 if sdata.get("last") == _yesterday_str() else 1
                data["streaks"][stat] = {"n": n, "last": _today_str()}
                data["done"][stat] = _today_str()
            else:
                # Deshacer hoy NO destruye la racha: se vuelve al valor de ayer.
                data["streaks"][stat] = {"n": max(0, prev - 1), "last": _yesterday_str()}
                if data.get("done", {}).get(stat) == _today_str():
                    data["done"].pop(stat, None)
            write_points(data)
            self._send_json(data)
        except Exception:
            self._send_json({"error": "no se pudo escribir points.md"}, status=500)

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        # Sin caché: evita que Chromium/Brave sirva el HTML viejo por caching
        # heurístico (http.server no manda Cache-Control por defecto).
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


# Directorio desde el que se sirven los estáticos (fallout-stats.html + img/).
# En el despliegue original es $HOME; se puede apuntar a un checkout del repo
# (p. ej. FALLOUT_WEB_ROOT=$HOME/FalloutWallpaper-Anki-GYM).
WEB_ROOT = os.environ.get(
    "FALLOUT_WEB_ROOT", os.path.expanduser("~"))


def main():
    os.chdir(WEB_ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[vault-tec-serve] escuchando en http://127.0.0.1:{PORT} "
          f"(static root={WEB_ROOT})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()