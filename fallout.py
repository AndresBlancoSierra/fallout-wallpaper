#!/usr/bin/env python3
"""
VAULT-TEC WALLPAPER — orquestador del fondo de pantalla de Fallout.

Lanza Brave en modo app con la página de stats de Fallout
(fallout-stats.html servida por http.server en :8123) y lo relanza si muere.
El plugin `hyprwinwrap` de Hyprland coloca la ventana (class
org.fallout.wallpaper) como capa de fondo detrás de todas las ventanas.

Interactividad: el fondo se puede enfocar para hacer clic con
    hyprctl dispatch hyprwinwrap_interactivity
(atajo configurado en bindings.conf: SUPER+B). Al hacer clic en otra
ventana, el fondo vuelve a su sitio.
"""

import os
import subprocess
import time

URL = os.environ.get('FALLOUT_URL', 'http://127.0.0.1:8123/fallout-stats.html')
CLASS = os.environ.get('FALLOUT_CLASS', 'org.fallout.wallpaper')
PROFILE = os.path.join(os.path.expanduser('~'), '.config', 'fallout-wallpaper')

# Cache-busting: query param distinto en cada lanzamiento para forzar que Brave
# vuelva a descargar el HTML (aunque http.server ahora ya manda no-store).
APP_URL = f"{URL}{'&' if '?' in URL else '?'}v={int(time.time())}"

CMD = [
    'brave',
    f'--app={APP_URL}',
    f'--class={CLASS}',
    f'--user-data-dir={PROFILE}',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-infobars',
    '--disable-component-update',
    '--disable-background-networking',
    '--disable-session-crashed-bubble',
    '--disable-translate',
    '--lang=es',
    '--disable-features=Translate,TranslateUI,TranslateUI2',
    '--remote-debugging-port=9222',
    '--ozone-platform=x11',
]


def _wallpaper_window_exists() -> bool:
    try:
        import json
        out = subprocess.run(
            ['hyprctl', 'clients', '-j'],
            capture_output=True, text=True, timeout=5,
        )
        clients = json.loads(out.stdout or '[]')
        return any(c.get('class') == CLASS for c in clients)
    except Exception:
        return False


def main():
    print('[fallout-wallpaper] lanzando Brave...', flush=True)
    proc = subprocess.Popen(CMD, start_new_session=True)
    print(f'[fallout-wallpaper] pid {proc.pid}', flush=True)
    try:
        while True:
            time.sleep(5)
            # Brave con el mismo perfil delega en la instancia existente y el
            # proceso lanzado sale de inmediato; por eso solo se relanza si NO
            # hay ninguna ventana del wallpaper viva (evita acumular ventanas).
            if proc.poll() is not None and not _wallpaper_window_exists():
                print('[fallout-wallpaper] sin ventana viva, relanzando...', flush=True)
                proc = subprocess.Popen(CMD, start_new_session=True)
                print(f'[fallout-wallpaper] nuevo pid {proc.pid}', flush=True)
    except KeyboardInterrupt:
        proc.terminate()
        print('\n[fallout-wallpaper] apagado')


if __name__ == '__main__':
    main()
