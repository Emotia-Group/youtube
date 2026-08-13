# Manual de uso de ytstudio

<!-- MANUAL_VERSION: 0.56.0 -->

Guía completa para sacarle el máximo provecho al programa **ahorrando tiempo,
esfuerzo y dinero**. Está escrita para usarse mientras trabajas: busca tu
sección, sigue los pasos y listo.

> **Regla de oro del programa:** todo lo que cuesta dinero se avisa ANTES, se
> mide MIENTRAS y se registra DESPUÉS. Si algo va a gastar, lo verás en la
> estimación; si gastó, aparecerá en el reporte de la corrida.

---

## 1. Qué es esto (y qué no es)

ytstudio convierte **tu tema o tu narración grabada** en un video terminado
para YouTube: guion, escenas, imágenes, voz, música, ambiente, subtítulos,
montaje, miniatura y metadatos.

**Sí puede:**
- Partir de un tema escrito, de tu voz grabada o de ambos.
- Escribir el guion o respetar EXACTAMENTE tu narración palabra por palabra.
- Generar imágenes y clips de video con IA, y también usar TU material.
- Poner rótulos, insertos de archivo (fotos, cifras, mapas), música, ambiente
  y subtítulos sincronizados a tu voz real.
- Reanudar donde se quedó sin volver a pagar lo ya hecho.

**No puede:**
- Publicar solo en YouTube (la fase de publicación prepara todo; la subida la
  haces tú).
- Inventar hechos con garantía de verdad: **el guion es tuyo o de la IA, y la
  responsabilidad de verificar los datos es tuya**.
- Usar caras de personas reales en las imágenes generadas (los generadores lo
  rechazan). Para eso está el **banco de elementos** con fotos reales.
- Trabajar sin ffmpeg instalado.

---

## 2. Primeros pasos (una sola vez)

### 2.1 Arrancar
Doble clic en **`iniciar.bat`**. Se abre el navegador en la interfaz. Para
cerrarlo, cierra la ventana negra.

### 2.2 Claves de API — ⚙ Configuración → 🔑 Claves
Pega cada clave y pulsa **💾 Guardar claves** (se guardan en tu archivo `.env`
local y se activan al instante).

| Clave | Para qué | ¿Imprescindible? |
|---|---|---|
| `ANTHROPIC_API_KEY` | Concepto, guion, escenas, dirección de arte, metadatos | **Sí.** Sin ella todo sale de muestra |
| `REPLICATE_API_TOKEN` | Imágenes (FLUX), video IA, música, lipsync | Sí para imágenes de verdad |
| `OPENAI_API_KEY` | Transcribir tu voz (Whisper) y rótulos con texto legible | Sí si narras tú |
| `ELEVENLABS_API_KEY` | Voces premium (solo si NO narras tú) | Opcional |

> ⚠ **Si falta una clave, el programa NO falla: degrada a modo muestra** y te
> avisa. Eso significa imágenes de relleno o voz silenciosa. Si ves «modo
> vista previa», revisa las claves antes de dar por bueno un video.

### 2.3 ffmpeg: la única herramienta externa obligatoria
ffmpeg es el motor que corta, monta y mezcla el video. **Sin él el programa no
funciona.**

- **Windows:** descarga `ffmpeg-release-essentials.zip` de
  [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) y descomprímelo en
  **`C:\ffmpeg`** (debe quedar `C:\ffmpeg\bin\ffmpeg.exe`). No hace falta
  tocar el PATH del sistema: el programa lo busca ahí solo.
- **Linux:** `apt install ffmpeg` · **Mac:** `brew install ffmpeg`.

### 2.4 Comprobar que todo está sano
Doble clic en **`probar.bat`** (o `./probar.sh`). Corre las ~50 baterías de
prueba internas en unos 6 minutos.
- **No cuesta un centavo** (sin claves ni internet) y **no toca tus proyectos**.
- Te dice **TODO EN VERDE** o exactamente qué falló.
- Si dice **VERDE PARCIAL — sin ffmpeg**, instálalo (§2.3): no se
  comprobaron voz, audio ni montaje.
- Úsalo **después de cada actualización** y **antes de una generación
  importante**.

### 2.5 Actualizar el programa
Doble clic en **`pull.bat`**: trae la última versión de tu rama en segundos y
te dice qué cambió. Si el aviso menciona que cambiaron las dependencias, pasa
una vez por **`actualizar.bat`** (hace lo mismo y además reinstala las
librerías de Python, por eso tarda más). Luego vuelve a abrir `iniciar.bat` o
`panel.bat`. Arriba a la izquierda verás la versión; haz clic para leer las
**novedades**.

Dos avisos que pueden aparecer ahí, y qué significan:

| Aviso | Qué significa | Qué hacer |
|---|---|---|
| **⚠ Actualización descargada pero NO aplicada** | Bajaste una versión nueva pero el programa sigue corriendo la vieja | Cierra la ventana negra y abre `iniciar.bat` otra vez |
| **⚠ N archivo(s) del programa modificados** | Hay archivos del programa distintos a los del repositorio (pasa el ratón para ver cuáles) | Si no los tocaste tú, un `git checkout .` los restaura. Un `git pull` puede fallar mientras difieran |

> 💡 **Tu material propio NO cuenta como «modificado»**: la música, los
> efectos, los ambientes, el banco de elementos y tus proyectos viven en tu
> equipo y el programa los ignora a propósito. Si el aviso aparece, es por
> archivos del programa, no por tu contenido.

---

## 3. Antes de generar: las decisiones que ahorran dinero

Esta es la sección más rentable del manual. **Cinco minutos aquí te ahorran
dólares y horas.**

### 3.1 Elige el modo: ¿narras tú o narra la IA?

**Narración propia (recomendado para tu canal).** Subes tu grabación y el
programa la respeta ÍNTEGRA: las escenas se cortan a la medida de tu voz, los
subtítulos y rótulos se sincronizan a tu palabra exacta.
- Sale más barato (no pagas voz IA).
- Suena a ti, no a robot.
- **Cuidado:** el programa transcribe tu audio (~$0.16 por 18 min) y corrige
  tropiezos evidentes. Lee la sección 8.1 antes de tu primera vez.

**Voz IA.** Escribes el tema y el programa escribe y narra. Más rápido, útil
para probar formatos, pero menos personal.

### 3.2 Prepara tu material (📁 pestaña Material de cada proyecto)

| Tipo | Para qué sirve | Consejo |
|---|---|---|
| **Narración** (mp3/wav) | Tu voz, la base del video | Graba con buen volumen; evita cambios bruscos de distancia al micro |
| **Texto/guion** (txt, md, pdf, docx) | Tu guion o notas de referencia | Si ya tienes guion, súbelo: no se reinventa |
| **B-roll propio** (imágenes/videos) | Se reparten por el video | Nómbralos `scene_003.jpg`, `03_batalla.mp4`… y van a ESA escena |
| **Enlace de referencia** (YouTube) | El programa aprende el ritmo y la fórmula | Uno bueno vale más que tres regulares |

### 3.3 Llena el banco de elementos (📚 Biblioteca → 🗄 Banco)
Es lo que hace que tu video se vea profesional: cuando la narración menciona a
alguien o algo, aparece un **inserto** sobre el B-roll.

- **El nombre del archivo es la clave**: `elon-musk.jpg` encuentra la mención
  «Elon Musk» (no importan tildes ni mayúsculas).
- Categorías: personajes, lugares, entidades, mapas, stickers.
- Acepta **imágenes y clips cortos** (mp4, webm, mov).
- **Tu material siempre gana** sobre la búsqueda automática.
- Usa solo material **de uso libre o propio** (Pixabay, Pexels, Openverse,
  Wikimedia con licencia libre).

> 💡 **Consejo:** llénalo con los 10-20 nombres que se repiten en tu canal
> (personajes recurrentes, países, instituciones). Se reutiliza en todos los
> videos futuros: lo haces una vez y rinde para siempre.

### 3.4 Guarda un estilo de canal (📚 Biblioteca → Canales y estilos)
Cuando un video te guste, entra a su pestaña **Concepto** y pulsa
**💾 Guardar estilo**. Captura dirección visual, tono, música, ritmo y
fórmula narrativa **sin volver a pagar el análisis**. En los siguientes
proyectos eliges ese estilo y arrancas con la identidad ya puesta.

En cada estilo puedes fijar el **branding de rótulos**: tipografía, color de
acento, color de texto y **diseño del rótulo** (documental / minimal / bold).
Hay combos de un clic para empezar.

### 3.5 Revisa la estimación
Al abrir un proyecto verás **cuánto costará y cuánto tardará**, desglosado por
fase. El programa además fija un **tope de presupuesto** (estimado × 1.4): si
la generación intentara pasarse, se detiene sola.

---

## 4. Generar: el paso a paso

Pulsa **▶ Generar video**. Se ejecutan 11 fases en orden. Puedes acotar hasta
dónde con el desplegable de arriba («Solo el guion», «Hasta el guion
gráfico»).

| # | Fase | Qué hace | ¿Cuesta? |
|---|---|---|---|
| 1 | **Análisis** | Lee tu material, transcribe tu voz, analiza la referencia | Bajo |
| 2 | **Concepto** | Define estilo visual, tono y dirección musical | Bajo |
| 3 | **Guion** | Escribe el guion (o adopta el tuyo) | Bajo |
| 4 | **Escenas** | Divide en escenas, diseña prompts, rótulos, música, sonido, insertos | Medio |
| 5 | **Voz** | Monta la pista de voz con respiros naturales | Bajo o nulo |
| 6 | **Imágenes** | Genera imágenes/clips, resuelve insertos y controla calidad | **ALTO** |
| 7 | **Música** | Banda sonora por actos + cama de ambiente | Bajo |
| 8 | **Subtítulos** | Subtítulos sincronizados a tu voz real | Nulo |
| 9 | **Montaje** | Ensambla, anima, superpone y mezcla | Nulo |
| 10 | **Metadatos** | 3 títulos, 3 descripciones, 3 miniaturas | Bajo |
| 11 | **Publicación** | Prepara el paquete final | Nulo |

### 4.1 EL momento clave: el punto de control del storyboard
Al terminar la fase **Escenas**, el programa se detiene y te muestra:

```
📋 PUNTO DE CONTROL — storyboard listo: 84 escenas · ~18 min
   Revísalo en 04_scenes/storyboard.md
   💰 Falta por generar: ~$8.09-$16.91
   ⚠ Corregir AQUÍ no cuesta nada; corregir después cuesta volver a generar.
```

**Léelo siempre.** Es el último punto donde cambiar algo es gratis. Revisa el
`storyboard.md`: la biblia visual, el prompt de cada escena y los rótulos.

Para acotar la corrida a este punto, elige **«Hasta el guion gráfico»** antes
de pulsar Generar.

---

## 5. Durante la generación: qué vigilar

El panel muestra progreso, porcentaje y tiempo estimado. Abajo, el log en vivo.

**Mensajes normales (no te asustes):**
- `⏳ OpenAI limita… espero 12s y reintento` — normal, el programa se
  autorregula.
- `⏳ Anthropic no responde (429)… espero y reintento` — igual.
- `🔄 El contenido de N escenas cambió` — rehace solo esas.
- `🎬 Diseño de escenas (tanda 2/3)` — normal en videos largos.

**Mensajes que SÍ debes leer:**
- `🛡 Descarté una corrección propuesta…` — el programa evitó borrar algo de
  tu narración. Bien.
- `✂ Corregido en tu narración [12.3s, −1.4s]` — quitó un tropiezo. **Fíjate
  en los segundos**: si ves un número grande, escucha esa parte.
- `⚠ Sin foto de licencia libre para…` — esos insertos no salieron.
- `🔊 Detecté habla MUY BAJA en…` — se conserva, pero suena floja.

**Puedes cerrar el navegador**: la generación sigue en la ventana negra. Si
cierras la ventana negra, se detiene (y podrás reanudar).

---

## 6. Después: revisar y publicar

1. **Mira el video** en la pestaña **Video**.
2. **Elige metadatos**: 3 títulos, 3 descripciones y 3 miniaturas — clic para
   seleccionar. La descripción incluye **capítulos automáticos** y los
   **créditos** del material de archivo (obligatorio por licencia: no los
   borres).
3. **Revisa el gasto real** de la corrida al final del panel.
4. Los archivos están en `projects/<tu-proyecto>/09_final/`.

### 6.1 Corregir sin re-pagar todo
- **▶ Generar video** — reanuda donde se quedó. Lo hecho no se re-paga.
- **«Rehacer desde…»** — regenera ESE paso y los siguientes.

| Quiero cambiar… | Rehacer desde | ¿Pierdo lo pagado? |
|---|---|---|
| Una imagen concreta | Sube tu B-roll a esa escena | No |
| Todas las imágenes | Imágenes | Sí, las imágenes |
| Rótulos, transiciones, música, ambiente | Montaje | No |
| El texto del guion | Guion | Sí, de ahí en adelante |

> ⚠ **Nunca rehagas desde Concepto/Guion/Escenas para arreglar una imagen.**
> Eso cambia los prompts, **borra las imágenes ya pagadas** y las vuelve a
> cobrar.

---

## 7. Ahorrar dinero: la guía práctica

### 7.1 Qué cuesta de verdad (video de ~18 min, 84 escenas)

| Concepto | Costo aproximado |
|---|---|
| Inteligencia (guion, escenas, dirección, insertos, control de calidad) | $1-3 |
| **Imágenes con FLUX 1.1 Pro** | **$3.3-4.2** |
| Imágenes con gpt-image-1 | $5.8-20.8 ⚠ |
| Video IA (18 clips Kling) | $4.7-12.6 ⚠ |
| Transcribir tu voz (Whisper, 18 min) | $0.11-0.16 |
| Música, ambiente, insertos, mapas, subtítulos | $0-0.2 |

### 7.2 Las cinco reglas del ahorro
1. **Prueba con modelos baratos.** En ⚙ Configuración → Imágenes elige
   **FLUX schnell** (~$0.003/img): un video completo de prueba cuesta
   centavos. Cuando la estructura te guste, cambia a **FLUX 1.1 Pro** y
   «Rehacer desde Imágenes».
2. **El video IA es lo más caro.** `max_scenes: 0` lo apaga. Con 18 clips
   pagas más que por las 83 imágenes. Úsalo solo en videos importantes.
3. **Para en el punto de control.** Corregir el storyboard es gratis.
4. **Reutiliza estilos** (📚 Biblioteca): evitas re-analizar referencias.
5. **Llena el banco de elementos**: material gratis, para siempre, y evita que
   se ilustre con IA.

### 7.3 Interruptores de gasto en ⚙ Configuración
| Ajuste | Efecto |
|---|---|
| `providers.images.model` | El que más pesa en la factura |
| `providers.videogen.max_scenes` | 0 = sin video IA (el mayor ahorro) |
| `providers.images.fact_check` | Control de calidad con visión (centavos, muy recomendable) |
| `providers.images.fact_check_retries` | Rondas de corrección (2 por defecto). Cada ronda revisa SOLO lo regenerado; un clip de video infiel nunca se re-paga: baja a su imagen fija |
| `video.elements_ai` | Ilustrar insertos sin foto libre. **Apagado por defecto** |
| `providers.lipsync` + % de personaje | Se paga por SEGUNDO en pantalla |

---

## 8. Tu narración: lo que hay que saber

### 8.1 El corrector de tropiezos
El programa detecta y quita falsos arranques, repeticiones y muletillas
**evidentes**. Cada corrección se anuncia con su duración:
`✂ Corregido en tu narración [836.0s, −0.9s]: se quitó «no con violencia,»`.

**Cinco vallas protegen tu contenido** (ninguna corrección se aplica si no
cuadra con el audio real): coherencia texto-tiempo, ritmo de habla posible,
tope de 20 s por corte, el empalme debe caer en silencio medido, y un tope
global del 8 % de tu grabación.

- Para **apagarlo del todo**: `audio.fix_narration: false`.
- Para apagar **solo la revisión con IA** (la más atrevida):
  `audio.fix_narration_ai: false`.

> 💡 Tras la primera generación, **escucha los primeros 60 segundos** y
> compara con lo que grabaste. Si algo falta, revisa los avisos `✂` y
> desactiva la revisión IA.

### 8.2 Consejos de grabación
- Volumen parejo y constante; el programa avisa si hay habla muy baja.
- Pausas naturales entre frases: son las que usa para respirar el montaje.
- Si te equivocas, **para, respira y repite la frase completa** desde el
  principio: así el corrector la reconoce y la limpia bien.
- Máximo ~69 minutos por archivo. Si es más largo, divídelo.

---

## 9. Las funciones que quizá no conoces

| Función | Dónde | Para qué |
|---|---|---|
| **Encuadre documental** | Automático | Las escenas delicadas (un animal sin vida, una batalla, una herida) salen con registro clínico y sobrio a la PRIMERA, sin que el filtro del generador las rechace |
| **Texto en su lengua** | Automático | Si la escena muestra un papiro en arameo o una inscripción en latín, el texto se ve EN ESA lengua, no en la de tu narración |
| **Auditoría de fidelidad** | Automático, gratis | Antes de generar, avisa si un prompt se dejó fuera un hecho de tu narración (la cantidad exacta o el estado sin vida) |
| **Insertos documentales** | Automático | Foto real, cifra animada o mapa cuando se menciona algo |
| **Mapas localizadores** | Automático | Pin animado sobre el lugar narrado |
| **Cama de ambiente** | Automático | Viento, multitud, sala… según lo que se narra |
| **Efectos incidentales** | Automático | whoosh, riser, boom, papel, latido |
| **Rótulos con diseño** | Estilo del canal | Placa, filete y palabra clave en color |
| **Elenco de personajes** | Pestaña Personajes | Misma cara en todas sus escenas |
| **Personaje narrador (lipsync)** | Pestaña Personajes | Tu presentador en cámara |
| **B-roll manual por escena** | Pestaña Escenas | Sustituye la imagen de una escena concreta |
| **Formatos cortos** | Nuevo proyecto | Shorts, Reels, TikTok, Meta Ads |
| **Biblioteca de hooks** | Automático en cortos | 970 ganchos virales probados |
| **Música por actos** | Automático | Varias pistas según la intensidad |

**Para tu propia música y sonidos:**
`assets/music/` (pistas) · `assets/sfx/` (efectos) ·
`assets/sfx/ambientes/` (ambientes) · `assets/elements/` (banco).
Cada carpeta tiene su README con los nombres correctos.

---

## 10. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| «modo vista previa» | Falta una clave | ⚙ Configuración → Claves |
| Se detuvo con error 429 | Límite del proveedor | Ya reintenta solo; si persiste, baja `parallel_images` |
| Faltan trozos de mi narración | El corrector cortó de más | Mira los avisos `✂`; apaga `fix_narration_ai`; rehaz desde Análisis |
| El video costó más de lo estimado | Modelo caro o video IA activo | Revisa §7 |
| Imágenes que no respetan lo narrado | Prompt ambiguo | Deja `fact_check: true`; corrige el storyboard y rehaz desde Imágenes |
| Falta un inserto | Sin foto de licencia libre | Añade el archivo al banco y rehaz desde Imágenes |
| Los subtítulos van desfasados | Proyecto de versión antigua | «Rehacer desde Voz» |
| No arranca / falta ffmpeg | ffmpeg no instalado | Instálalo (en Windows, en `C:\ffmpeg\bin`) |

**Si algo falla de verdad:** ve a **🧾 Log de eventos → ⬇ Descargar** y
compárteme ese archivo. Ahí está todo lo necesario para diagnosticarlo.

---

## 11. Qué SÍ y qué NO hacer

**SÍ:**
- Correr `probar.bat` tras cada actualización.
- Parar en el punto de control del storyboard.
- Probar con modelos baratos antes de la versión final.
- Escuchar el video completo antes de publicar.
- Conservar los créditos de material de archivo en la descripción.
- Llenar el banco de elementos poco a poco.

**NO:**
- No borres carpetas dentro de `projects/` durante una generación.
- No rehagas desde Concepto/Guion/Escenas para arreglar una imagen.
- No subas material sin derechos: el programa no puede verificarlo por ti.
- No edites `config.yaml` a mano si puedes hacerlo desde ⚙ Configuración
  (tus ajustes viven en `config.local.yaml`, que no se pisa al actualizar).
- No des por bueno un video sin revisar los avisos ⚠ del panel.

---

## 12. Glosario mínimo

- **B-roll**: las imágenes o videos que se ven mientras hablas.
- **Storyboard**: el plan de todas las escenas antes de generar nada.
- **Inserto**: tarjeta que se superpone al B-roll (foto, cifra, mapa).
- **Rótulo**: el texto en pantalla (nombre, fecha, dato).
- **Fase**: cada uno de los 11 pasos de la generación.
- **Reanudar**: seguir donde se quedó sin re-pagar lo hecho.
- **Tope de presupuesto**: freno automático de gasto por corrida.

---

## 13. Torre de Control: el panel multicanal

ytstudio hace los videos; la **Torre de Control** administra los canales.
Se abre con doble clic en **`panel.bat`** (o `python -m ytpanel ui`) en
`http://localhost:8766`, y todo lo que ve y guarda vive **en tu equipo**
(`panel_data/`), no en ningún servicio de terceros.

### 13.1 Preparar Google Cloud (una sola vez, ~15 minutos)

1. Entra a [console.cloud.google.com](https://console.cloud.google.com) con tu
   cuenta principal y crea **UN** proyecto (p. ej. «emotia-panel»). Uno solo
   para todo el sistema: crear varios para sumar cuota va contra las normas
   de YouTube y sí es sancionable.
2. En **APIs y servicios → Biblioteca**, habilita **YouTube Data API v3** y
   **YouTube Analytics API**.
3. En **Pantalla de consentimiento OAuth**: tipo **Externo**, rellena nombre y
   correos. Mientras la app esté «En pruebas», añade en **Usuarios de prueba**
   los correos de TODAS las cuentas de Google dueñas de tus canales.
4. En **Credenciales → Crear credenciales → ID de cliente de OAuth**, tipo
   **«App de escritorio»**, y descarga el JSON como `client_secrets.json` en
   la carpeta del programa (el mismo archivo sirve para la publicación de
   ytstudio).

> ⚠ **Mientras la app esté «En pruebas», Google caduca los tokens a los
> 7 días**: el panel marcará los canales como «Reconectar» cada semana. Es
> molesto pero esperado. La solución definitiva es **Publicar la app** y pasar
> la verificación de Google (gratuita; pide una página web con política de
> privacidad y un video demo, tarda de días a semanas). Con la app verificada,
> los tokens duran hasta que tú los revoques.

> 💡 **Si Google responde «Error 400: redirect_uri_mismatch»** al conectar un
> canal: crea la credencial como tipo **«Aplicación web»** en vez de «App de
> escritorio» y añade en **URIs de redireccionamiento autorizados** exactamente
> `http://localhost:8766/oauth/callback` (si cambiaste el puerto en
> `config.yaml`, usa ese número). Descarga ese JSON como `client_secrets.json`:
> el panel acepta los dos formatos sin tocar nada más.

### 13.2 Conectar los canales

Botón **«＋ Conectar canal»** → eliges la cuenta de Google → si la cuenta
tiene canales de marca, Google te deja elegir **la identidad del canal** →
aceptas los permisos. Repite por cada canal: **un token por canal**, da igual
de qué cuenta sea. El panel pide desde el día uno los permisos de gestión y
lectura de ingresos que usarán las fases siguientes, para no tener que
reconectar los 20 canales cuando llegue la edición de metadatos.

Al conectar, el panel trae la primera foto: 90 días de métricas diarias y los
últimos 50 videos. Los **ingresos** solo aparecen en canales dentro del
Programa de Socios (YPP); en los demás la tarjeta dice «ingresos sin acceso»
y no es un error. Y son **estimados**: se ajustan a fin de mes, la cifra de
pago real vive en AdSense.

### 13.3 Sincronizar cada día

- **A mano**: botón «⟳ Sincronizar» (verás el avance arriba).
- **Programado** (recomendado): tarea diaria con
  `py -m ytpanel sync` (Programador de tareas de Windows) o
  `python3 -m ytpanel sync` (cron). Cada corrida es incremental y re-pide los
  últimos 3 días porque Analytics los re-consolida.

**Cuota**: leer métricas casi no gasta (≈3 unidades de Data API por canal y
corrida, de 10 000 diarias; Analytics tiene cuota aparte). El medidor de la
cabecera muestra lo gastado hoy por el panel.

### 13.4 Seguridad y datos

- Los tokens se guardan **cifrados** (paquete `cryptography`; si falta, el
  panel avisa con «⚠ Tokens sin cifrar» — instálalo con
  `pip install cryptography`).
- El panel solo escucha en tu equipo (127.0.0.1), nunca en la red.
- **Desconectar un canal borra** su token y todas sus métricas locales; el
  canal en YouTube no se toca.
- ¿Quieres verlo amueblado sin conectar nada? «Cargar demo» crea 4 canales
  ficticios (no llaman a ninguna API); «Quitar demo» los borra de raíz.

### 13.5 Editar desde el panel (fase 2): metadatos, miniaturas y playlists

Cada video de un canal conectado tiene un lápiz **✎** en su fila: se abre el
editor con **título, descripción y etiquetas** (con contadores de los límites
reales de YouTube: 100 caracteres el título, 5 000 *bytes* la descripción —
tildes y emojis cuentan más de uno — y ~500 caracteres el total de etiquetas)
y la **miniatura** (JPG/PNG hasta 2 MB; el canal debe estar verificado por
teléfono). En la sección **Playlists** puedes crear listas y abrir cualquiera
para añadir, quitar o reordenar videos.

**Edición en lote**: el botón «☑ Edición en lote» activa casillas en la tabla.
Marcas videos, eliges la operación — buscar y reemplazar en título o
descripción, añadir texto al final de la descripción, añadir etiquetas, o
añadir a una playlist — y pulsas **Vista previa**: verás el antes → después y
el costo en cuota ANTES de confirmar. Nada se aplica sin que lo veas.

**Todo pasa por la cola** (chip «📋 Cola» en la cabecera). Por qué: cada
edición cuesta ~51 unidades de las 10 000 diarias, y un lote grande sobre
20 canales puede no caber hoy. La cola ejecuta lo que cabe, deja el resto
**en espera con su motivo** y lo retoma sola tras el reinicio de cuota
(medianoche, hora del Pacífico). Además reserva unidades
(`panel.quota_reserve`, 500 por defecto) para que las ediciones jamás dejen
sin cuota al sync nocturno. Los errores pasajeros (cortes de red, 5xx de
Google) se reintentan solos hasta 3 veces; los definitivos quedan en la cola
con el mensaje de Google legible y un botón **Reintentar**.

Detalles finos que el panel ya maneja por ti: antes de cada edición se relee
el video **tal como está en YouTube** en ese momento (la API borra todo campo
que no se reenvíe: sin esa lectura, cambiar el título borraría las
etiquetas), y la edición en lote se calcula en el servidor sobre esos datos —
lo encolado es exactamente lo que la vista previa enseñó. Desde la terminal:
`py -m ytpanel cola` (ver) y `py -m ytpanel cola --procesar` (ejecutar, ideal
junto al sync programado).

### 13.6 Reportes y alertas (fase 3)

Botón **📊 Reportes** en la cabecera. Todo lo que hay ahí se calcula sobre el
histórico que ya tienes guardado: **no gasta cuota**, así que puedes preguntar
lo que quieras las veces que quieras.

**Comparativa entre canales.** Eliges una métrica (vistas, horas vistas,
suscriptores netos, ingresos, me gusta o comentarios) y un periodo, y ves
todos los canales en el mismo gráfico. Clic en un canal de la fila de arriba
para incluirlo o quitarlo. Dos detalles pensados para que no te engañe:

- **Nunca hay dos ejes.** Comparar vistas e ingresos en un mismo gráfico con
  dos escalas hace que cualquier par de líneas parezca relacionado. Aquí se
  ve una métrica a la vez.
- **Un hueco en la línea es «no hay dato», no «cero»**. Un canal que aún no
  existía, o que no has sincronizado tan atrás, deja hueco en vez de mentir
  con una línea plana en cero.
- Pasados 8 canales se pintan los 7 mayores y el resto se suma en «Otros»:
  con veinte líneas de colores el gráfico deja de ser legible (y los colores
  dejan de distinguirse para quien no ve bien el color).

**Tabla dinámica.** Los mismos datos agrupados **por canal, día, semana o
mes**, con totales de la red al pie. Clic en cualquier encabezado para
ordenar. Incluye el **RPM** (ingresos por cada mil vistas), que es *la*
métrica para comparar canales de tamaños distintos: dice cuánto rinde la
audiencia, no cuánta hay. Un «—» significa sin datos (canal fuera del
Programa de Socios), que no es lo mismo que cero.

**Mejores videos de la red**: ranking de todos tus canales juntos. Ojo, sus
contadores son **acumulados desde que se publicó cada video**, no del periodo
elegido — es lo que entrega la API, y por eso está dicho en la propia tabla.

**Exportar a Excel.** Tres CSV: el resumen agrupado, el ranking de videos y el
**detalle día a día** (la materia prima para armar tus propias tablas
dinámicas en Excel). Se abren de un doble clic: separador «;», decimales con
coma y UTF-8 con BOM, que es lo que espera el Excel en español.

**Alertas.** En la portada, encima de las tarjetas, el panel te dice qué
merece tu atención hoy en vez de obligarte a revisar 20 canales:

| Alerta | Cuándo salta |
|---|---|
| ⛔ Hay que reconectar el canal | La autorización cayó: no entran métricas ni ediciones |
| ⚠ N días sin sincronizar | Los números que ves están congelados |
| ⚠ Las vistas cayeron X % | 7 días contra los 7 anteriores |
| ⚠ Los ingresos cayeron X % | Igual, con los ingresos estimados |
| ⚠ N días sin publicar | El canal se apagó y el alcance se resiente |
| ⚠ Ediciones fallaron en la cola | Esos cambios NO están en YouTube |
| ▲ Las vistas subieron X % | Para que sepas qué está funcionando |
| ▲ Un video va N× sobre su media | Oportunidad con fecha de caducidad |

Los umbrales se ajustan en `config.yaml`, bloque `panel.alertas` (por ejemplo
`caida_vistas_pct` o `dias_sin_publicar`). Y desde la terminal,
`py -m ytpanel alertas` las imprime — pensado para programarlo por la mañana:
solo devuelve error si hay algo **crítico**, así no te da la lata por una
buena noticia. Para exportar sin abrir el panel:
`py -m ytpanel exportar --que diario --dias 90`.
