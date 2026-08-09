# 🎬 ytstudio — Sistema inteligente de creación de videos largos para YouTube

Pipeline completo que, a partir de **cualquier input** — un guion listo, una
idea en texto, una nota de voz, una imagen o un video de referencia — produce
un **video largo listo para subir a YouTube**: concepto, guion, escenas,
voz en off, B-roll generado con IA, música, animaciones, subtítulos, montaje,
metadatos SEO, miniatura y (opcionalmente) la subida automática al canal.

```
INPUT (guion | idea | nota de voz | imagen | video de referencia)
  │
  ├─ 1. ingest      Detección del tipo de input + transcripción/análisis visual → brief
  ├─ 2. concept     Concepto: títulos, ángulo, tono, estructura de retención,
  │                 guía de estilo visual y dirección musical
  ├─ 3. script      Guion completo de narración (editable antes de continuar)
  ├─ 4. scenes      Storyboard: escenas de 10-25 s con prompt de B-roll,
  │                 animación y texto en pantalla
  ├─ 5. voiceover   Voz en off con TTS (duraciones exactas por escena)
  ├─ 6. broll       Imágenes/clips IA por escena, con estilo consistente
  ├─ 7. music       Música de fondo (biblioteca, MusicGen o mock)
  ├─ 8. subtitles   Subtítulos .srt + .ass estilizado, sincronizados
  ├─ 9. assembly    Montaje ffmpeg: Ken Burns, fundidos, textos, ducking,
  │                 normalización -14 LUFS, subtítulos
  ├─ 10. metadata   Título, descripción con capítulos reales, tags y miniatura
  └─ 11. publish    Subida a YouTube (opcional, YouTube Data API)
  │
  └─→ 09_final/video_final.mp4 + miniatura.jpg + metadata.json
```

## Instalación

```bash
# Requisitos del sistema
sudo apt install ffmpeg        # Linux  ·  brew install ffmpeg (macOS)

# Dependencias Python (mínimas: anthropic, pyyaml, pillow)
pip install -r requirements.txt

# Claves de API
cp .env.example .env   # y completa las claves de los proveedores que uses
```

### Windows

```powershell
git clone https://github.com/Emotia-Group/youtube.git
cd youtube
py -m pip install -r requirements.txt
py -m ytstudio ui
```

Después de la primera instalación, basta con **doble clic en `iniciar.bat`**
(abre el programa y el navegador solos) y **`actualizar.bat`** para traer la
última versión. Las claves de API se configuran desde la propia interfaz
(⚙ Configuración → Claves de API).

Para ffmpeg en Windows: descarga `ffmpeg-release-essentials.zip` de
https://www.gyan.dev/ffmpeg/builds/ y descomprímelo en `C:\ffmpeg`
(debe existir `C:\ffmpeg\bin\ffmpeg.exe`). No hace falta tocar el PATH:
ytstudio lo detecta ahí automáticamente. En Windows los comandos usan
`py` en lugar de `python`.

**Sin claves de API el sistema sigue funcionando**: cada proveedor se degrada
a un *mock* (guion de ejemplo, voz silenciosa con duración realista, tarjetas
placeholder, música sintética) para que puedas validar el pipeline y el
montaje de punta a punta antes de gastar en generación real.

## Interfaz gráfica (recomendada)

```bash
python -m ytstudio ui          # abre http://localhost:8765
```

La UI web local permite hacer todo sin tocar la terminal:

- **Crear proyectos** desde texto y/o varios archivos a la vez, organizados por categoría: **Guion** (PDF, Word .docx, PowerPoint, Excel, txt, md), **Nota de voz/narración** (mp3, wav, m4a…), **Tu B-roll** (tus propias imágenes y videos, que se usan directamente en el montaje) y **Referencia de estilo** (imagen o video que se analiza con IA). Los archivos se pueden borrar y añadir en cualquier momento desde la pestaña Archivos
- **Configurar las claves de API desde la interfaz** (⚙ Configuración → Claves de API): se guardan en tu `.env` local y se activan al instante
- **Elegir el estilo cinematográfico** por proyecto: documental cinematográfico, cine épico, misterio/true crime, histórico/vintage o divulgación moderna (los presets guían la dirección visual, el tono, la música y fijan 24 fps para look de cine)
- **Ejecutar el pipeline** completo o por tramos, con progreso y log en vivo
- **Revisar y editar el guion** antes de producir (al guardar se regeneran las fases posteriores)
- **Ver el storyboard** escena por escena: imagen de B-roll, narración, prompt, animación y audio de la voz
- **Previsualizar el video final**, la miniatura y los metadatos, con descargas directas
- **Módulo de integraciones** (⚙ Configuración): selecciona proveedor y modelo para cada categoría — Claude (Opus/Sonnet/Haiku), ElevenLabs/OpenAI/Edge TTS con selector de voces en español, FLUX/gpt-image-1/Recraft/SD 3.5 para imágenes, Kling/Wan/Hailuo/LTX para video generativo, MusicGen/biblioteca para música — con indicador de qué claves de API están disponibles

## Uso por línea de comandos

```bash
# 1) Crear un proyecto desde cualquier input
python -m ytstudio new mi-video --text "La historia de los faros y los fareros"
python -m ytstudio new mi-video --file guion.md            # guion listo
python -m ytstudio new mi-video --file nota_de_voz.m4a     # nota de voz
python -m ytstudio new mi-video --file referencia.jpg      # imagen de referencia
python -m ytstudio new mi-video --file video_ref.mp4       # video de referencia

# 2) Ejecutar el pipeline completo
python -m ytstudio run mi-video

# Flujo recomendado con revisión humana del guion:
python -m ytstudio run mi-video --to script      # genera hasta el guion
#   → edita projects/mi-video/03_script/guion.md a tu gusto
python -m ytstudio run mi-video                  # continúa desde donde quedó

# Re-ejecutar desde una fase (invalida las posteriores)
python -m ytstudio run mi-video --from scenes

# Utilidades
python -m ytstudio status mi-video
python -m ytstudio list
python -m ytstudio phases
```

El pipeline es **reanudable**: cada fase guarda su estado en
`projects/<slug>/project.json` y los artefactos ya generados (voces, imágenes,
escenas renderizadas) no se regeneran al relanzar.

## Revisar la salud del programa (antes de gastar)

Generar un video cuesta dinero real. Antes de una corrida importante —o tras
actualizar— puedes comprobar que el programa está sano:

### Windows
Doble clic en **`probar.bat`**.

### Linux / Mac
```bash
./probar.sh
```

Corre las baterías de prueba (una por versión, con su historia de fallos ya
corregidos) y termina con un veredicto claro: **TODO EN VERDE**, o qué falló y
dónde. Tarda unos minutos.

- **No usa ninguna clave de API ni internet**: proveedores falsos, audio
  sintético y ffmpeg local. No gasta un centavo.
- **No toca tus proyectos**: todo ocurre en carpetas temporales.

```bash
py tests/probar_todo.py            # todas
py tests/probar_todo.py 42         # solo las baterías de la v0.42.x
py tests/probar_todo.py --lista    # ver qué hay, sin correr nada
```

Si algo sale en rojo, copia el resumen y pásaselo a Claude: identifica la
batería, la comprobación exacta y el valor medido que falló.

## Tipos de input

| Input | Detección | Qué hace el sistema |
|---|---|---|
| Guion listo | `.txt/.md` largo o `--type script` | Lo respeta; solo pule fluidez oral y lo estructura |
| Idea en texto | `--text "…"` o `.txt/.md` corto | Desarrolla concepto y guion completos |
| Tu voz / narración | `.mp3/.m4a/.wav/.ogg/.opus` | **Usa tu voz tal cual**: recorta silencios largos, transcribe con tiempos y alinea cada escena a tu narración |
| Imagen | `.jpg/.png/.webp` | Analiza con visión (Claude) y deriva tema + estilo visual |
| Video de referencia | `.mp4/.mov/.mkv/.webm` | Transcribe el audio + analiza fotogramas para tema y estilo |

## Proveedores (config.yaml)

| Categoría | Opciones | Notas |
|---|---|---|
| `llm` | `anthropic` / `mock` | Claude (`claude-opus-4-8`) para concepto, guion, escenas, metadatos y análisis visual |
| `tts` | `elevenlabs` / `openai` / `edge` / `mock` | `edge` es gratuito (voces neuronales, ej. `es-MX-JorgeNeural`) |
| `stt` | `openai` (Whisper) / `mock` | Notas de voz y video de referencia |
| `images` | `openai` (gpt-image-1) / `replicate` (FLUX) / `mock` | B-roll y base de la miniatura |
| `videogen` | `replicate` (Kling/Wan) / `none` | Video IA solo para las N escenas clave (`max_scenes`); el resto usa Ken Burns |
| `music` | `library` / `replicate` (MusicGen) / `mock` | `library` usa `assets/music/` (nombra archivos por mood) |

Ajustes clave en `config.yaml`: idioma (`language`), duración objetivo
(`video.target_minutes`), subtítulos quemados o pista soft
(`video.burn_subtitles`), volumen y ducking de música (`audio.*`).
Cada proyecto puede tener su propio `config.yaml` dentro de su carpeta que
sobreescribe el global.

## Estructura de un proyecto

```
projects/mi-video/
├── project.json          # estado del pipeline (reanudable)
├── config.yaml           # overrides opcionales del proyecto
├── 01_input/             # input original, transcripción, brief.json
├── 02_concept/           # concept.json + concept.md (revisable)
├── 03_script/            # guion.md  ← edítalo antes de continuar
├── 04_scenes/            # scenes.json + storyboard.md
├── 05_voiceover/         # vo_001.mp3, vo_002.mp3, …
├── 06_broll/             # scene_001.jpg / .mp4, …
├── 07_music/             # musica.mp3
├── 08_subtitles/         # subtitulos.srt + subtitulos.ass
└── 09_final/             # video_final.mp4, miniatura.jpg, metadata.json
```

## Publicación en YouTube (opcional)

1. Crea un proyecto en Google Cloud, habilita **YouTube Data API v3** y
   descarga las credenciales OAuth como `client_secrets.json` en la raíz.
2. En `config.yaml`: `publish.enabled: true` (y `privacy: private|unlisted|public`).
3. `python -m ytstudio run mi-video` — la primera vez abre el flujo OAuth en
   el navegador; sube el video, la miniatura y aplica título/descripción/tags.

Si `publish.enabled: false` (por defecto), la última fase solo imprime las
rutas del paquete final para subirlo manualmente.

## Cómo funciona el montaje

- Cada escena se renderiza por separado (reanudable): imagen sobreescalada +
  `zoompan` (zoom in/out, paneos alternados) o clip de video IA recortado a
  16:9, texto en pantalla con `drawtext`, fundidos de entrada/salida y su voz
  en off exacta con padding configurable.
- Las escenas se concatenan sin re-encodear (`concat` demuxer).
- La música se mezcla con **sidechain ducking** bajo la narración y el master
  se normaliza a **-14 LUFS** (estándar de YouTube).
- Subtítulos: quemados (`.ass` estilizado) o como pista soft `mov_text` que
  YouTube reconoce; el `.srt` también queda disponible para subirlo aparte.

## Costos aproximados por video de 10 min

| Concepto | Proveedor | Costo aprox. |
|---|---|---|
| Guion + concepto + escenas + metadatos | Claude Opus | ~$1–3 |
| Voz en off (~1 500 palabras) | ElevenLabs / OpenAI TTS / edge | ~$1–2 / ~$0.20 / gratis |
| B-roll (~35 imágenes) | FLUX / gpt-image-1 | ~$1.5–3 |
| Video IA (opcional, por escena de 5 s) | Kling | ~$0.15–0.5 c/u |
| Música | biblioteca local / MusicGen | gratis / centavos |
