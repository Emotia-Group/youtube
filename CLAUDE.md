# Cómo trabajar en este proyecto

## Cómo hablarle al creador (obligatorio, en todas las sesiones)

El creador **no es programador**. Nunca supongas que sabe usar Git, la consola
ni las herramientas de desarrollo. En cada respuesta que implique que él haga
algo en su equipo:

1. **Da las indicaciones exactas, paso a paso.** Dónde hacer clic, qué ventana
   abrir, qué escribir *literalmente* y qué debería ver después de cada paso.
   Nada de «haz un checkout de la rama» a secas.
2. **Los comandos, listos para copiar y pegar**, uno por línea, en bloque de
   código, y di antes en qué ventana se pegan (la ventana negra `cmd` abierta
   **en la carpeta del programa**, que se abre escribiendo `cmd` en la barra de
   direcciones del explorador de Windows).
3. **Trabaja en Windows.** Rutas con barra invertida, archivos `.bat` con doble
   clic (`iniciar.bat`, `pull.bat`, `actualizar.bat`, `probar.bat`, `panel.bat`).
   Los `.sh` son para Linux/Mac: no se los ofrezcas como opción principal.
4. **Explica el porqué en una línea**, sin jerga. Si hay un término técnico
   inevitable, tradúcelo la primera vez que aparezca.
5. **Avisa de lo que NO se toca.** Sus proyectos, sus claves (`.env`),
   `config.local.yaml` y su material propio viven fuera del repositorio: dilo
   cuando una operación pueda dar miedo.
6. **Si algo puede salir mal, di antes qué hacer si sale mal** (el mensaje de
   error probable y la salida), en vez de dejarlo bloqueado.

Cuando pegue la salida de un error, diagnostícalo y arréglalo: no le pidas que
investigue él.

## El programa

- `ytstudio` hace los videos; `ytpanel` («Torre de Control») administra canales.
- Dos plantillas de interfaz, ambas vivas: `webui/static/index.html` (nueva) e
  `index-clasica.html` (clásica). **Todo lo que se añada a una hay que añadirlo
  a la otra**, y cada una tiene su manual: `MANUAL.md` y `MANUAL-clasica.md`.
- Cada versión lleva su entrada en `CHANGELOG.md` (de ahí sale la versión que
  muestra la interfaz), su batería `tests/test_vX_Y_Z.py`, y la marca
  `MANUAL_VERSION` de los dos manuales al día. Las capturas del manual viven en
  `docs/manual/<plantilla>/`.
- Antes de dar algo por hecho, corre las baterías: `py tests/probar_todo.py`
  (en Windows, doble clic en `probar.bat`). No usan claves ni internet.
