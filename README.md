<p align="center">
  <a href="https://github.com/AndresBlancoSierra/fallout-wallpaper">
    <img src="https://raw.githubusercontent.com/AndresBlancoSierra/fallout-wallpaper/main/profile.svg" alt="VAULT-TEC Wallpaper — fallout-wallpaper@arch">
  </a>
</p>

# VAULT-TEC Wallpaper

Wallpaper interactivo de **Fallout/Vault-Tec** para Hyprland: un servidor local
sirve una página de stats (SPECIAL del Pip-Boy), y Brave en modo app se coloca
como capa de fondo detrás de todas las ventanas mediante `hyprwinwrap`.

Combina el estado de tu vida real (gym, meditación, dibujo, vóley, push/pull/leg
leídos del vault de Obsidian) en un Pip-Boy funcional.

---

## 🚀 Cómo correrlo

```bash
cd ~/Proyects/fallout-wallpaper
python3 serve.py    # servidor HTTP en :8123 (endpoint /api/gym)
python3 fallout.py  # lanza Brave como capa de fondo
```

O simplemente relanza el wallpaper (matando procesos previos):

```bash
~/.local/bin/fallout-wallpaper-toggle.sh
```

En Hyprland se arranca solo desde `~/.config/hypr/autostart.conf`:
`exec-once = ~/Proyects/fallout-wallpaper/serve.py` y `fallout.py`.

---

## 🧠 Cómo funciona

- **serve.py**: sirve `fallout-stats.html` (http.server) y expone
  `/api/gym`, que lee los `.md` de `~/Documents/obsidian/Me/GYM`
  (grupos Push/Pull/Leg) y calcula el progreso de kg entre la primera y la
  última sesión, más los stats manuales (PUSH/PULL/LEG/VOLLEY/MEDITATION/DRAW)
  desde `~/Documents/obsidian/Me/points.md`.
- **fallout.py**: lanza Brave con `--app=http://127.0.0.1:8123/fallout-stats.html`
  y clase `org.fallout.wallpaper`; `hyprwinwrap` lo deja en la capa de fondo.
  Lo relanza si muere.

### Interactividad

Enfoca el fondo para hacer clic con:

```bash
hyprctl dispatch hyprwinwrap_interactivity
```

(atajo configurado en `bindings.conf`: **SUPER+B**). Al hacer clic en otra
ventana, el fondo vuelve a su sitio.

---

## ⚙️ Configuración (variables de entorno)

| Variable | Default | Qué es |
| --- | --- | --- |
| `FALLOUT_PORT` | `8123` | Puerto del servidor |
| `FALLOUT_URL` | `http://127.0.0.1:8123/fallout-stats.html` | URL que abre Brave |
| `FALLOUT_CLASS` | `org.fallout.wallpaper` | Clase de ventana para hyprwinwrap |
| `GYM_ROOT` | `~/Documents/obsidian/Me/GYM` | Vault de gym |
| `POINTS_FILE` | `~/Documents/obsidian/Me/points.md` | Stats manuales |

---

## 📁 Estructura

```
fallout-wallpaper/
├── serve.py              ← servidor HTTP + API /api/gym
├── fallout.py            ← orquestador (lanza/relanza Brave como wallpaper)
└── fallout-stats.html    ← página del Pip-Boy con las stats
```
