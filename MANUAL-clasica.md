# Manual de uso de ytstudio

<!-- MANUAL_VERSION: 0.65.4 -->
<!-- PLANTILLA: clasica -->

Este manual está escrito para **cualquier persona**, sin conocimientos
técnicos. Si sabes usar el navegador y arrastrar un archivo, sabes usar este
programa.

> 🎨 **Estás leyendo el manual de la plantilla CLÁSICA** (la interfaz oscura,
> con el menú lateral y las pestañas Guion · Storyboard · Editor · Video ·
> Concepto · Archivos). Si cambias a la plantilla nueva en **⚙ Configuración**,
> este mismo menú te mostrará el manual de la otra, con sus propias capturas.
> Ver el capítulo 2.6.

**Cómo leerlo:**

- ¿Es tu primera vez? Lee los capítulos **1, 2 y 3** y haz tu primer video.
- ¿Quieres hacer un tipo concreto de video (un Short, un anuncio, un video
  con tu cara)? Ve directo al capítulo **4**.
- ¿Buscas algo puntual («cómo cambio la miniatura», «por qué salió caro»)?
  Usa el **buscador** del manual dentro del programa (**📖 Manual de uso** →
  🔎) o el índice de la derecha.

> **La regla de oro:** todo lo que cuesta dinero se te avisa **antes** (con
> una estimación), se mide **mientras** (con un tope automático que frena el
> gasto) y se registra **después** (con el gasto real de la corrida). Nunca
> hay una sorpresa silenciosa.

> **Segunda regla de oro:** el momento de corregir es **antes de generar las
> imágenes**. Ahí todo es gratis. Después, corregir cuesta volver a generar.

---

## 1. Qué hace este programa (y qué no hace)

ytstudio toma **tu idea o tu voz grabada** y devuelve un **video terminado
para YouTube y redes sociales**: guion, escenas, imágenes, voz, música,
sonido ambiente, subtítulos, montaje, miniatura (la imagen de portada) y los
textos para publicar.

### 1.1 Lo que sí hace

| Puede… | Detalle |
|---|---|
| Partir de casi cualquier cosa | Una idea de una línea, un guion completo, tu voz grabada, una foto, un video, o un enlace de YouTube que quieras imitar |
| Respetar tu voz palabra por palabra | Si subes tu grabación, esa es la voz del video: no se sustituye por una voz artificial |
| Crear las imágenes | Genera con inteligencia artificial la imagen (o el clip de video) de cada escena, siempre con el mismo estilo visual |
| Usar TU material | Tus fotos, tus videos, tu música y tus efectos entran en el montaje con prioridad sobre lo generado |
| Poner texto en pantalla | Rótulos (los letreros con el nombre, la fecha o el dato), subtítulos sincronizados y tarjetas informativas |
| Sonar bien | Música por tramos, ambiente (viento, multitud, lluvia), efectos en los cortes y mezcla con el volumen estándar de YouTube |
| Continuar donde se quedó | Si lo detienes, lo retomas sin volver a pagar lo ya hecho |
| Trabajar en 10 idiomas | Español, inglés, chino, hindi, francés, árabe, bengalí, portugués, ruso y alemán |

### 1.2 Lo que no hace

- **No publica solo** (salvo que lo actives a propósito): prepara el paquete
  final y tú lo subes. Ver el capítulo 8.
- **No garantiza que los datos sean ciertos.** El guion lo escribes tú o lo
  escribe la inteligencia artificial: **verificar los hechos es tu
  responsabilidad**.
- **No genera caras de personas reales** con IA (los generadores lo
  rechazan). Para eso está el **banco de elementos**: fotos reales que tú
  aportas (capítulo 5.4).
- **No funciona sin ffmpeg**, un programa gratuito que hace el montaje. Se
  instala una sola vez (capítulo 2.3).

### 1.3 El recorrido completo, en una imagen

```
TÚ APORTAS                    EL PROGRAMA HACE                   TÚ RECIBES
─────────────                 ────────────────────               ──────────
idea escrita        →   1 Análisis      lee tu material
guion               →   2 Concepto      define el estilo
tu voz grabada      →   3 Guion         escribe o adopta el tuyo
tus fotos/videos    →   4 Escenas   ◄── PUNTO DE CONTROL (gratis)
enlace de ejemplo   →   5 Voz           monta la pista de voz
                        6 Imágenes  ◄── aquí está casi todo el gasto
                        7 Música        banda sonora y ambiente
                        8 Subtítulos    sincronizados a la voz real
                        9 Montaje       une, anima y mezcla        →  video.mp4
                       10 Metadatos     3 títulos y 3 miniaturas   →  miniatura
                       11 Publicación   deja el paquete listo      →  textos
```

---

## 2. Instalación y primer arranque (una sola vez)

### 2.1 Abrir el programa

Doble clic en **`iniciar.bat`** (en Windows) o `./iniciar.sh` (Mac/Linux).

Ocurren dos cosas:

1. Se abre una **ventana negra** (la consola). **No la cierres**: es el motor
   del programa. Cerrarla apaga todo.
2. Se abre el navegador en la interfaz. Si no se abre solo, entra a
   **http://localhost:8765**.

Para cerrar el programa: cierra la ventana negra.

![La pantalla de inicio del programa](docs/manual/clasica/01-nuevo-proyecto.png)

A la izquierda está el menú fijo, y lo vas a usar todo el tiempo:

| Menú | Para qué |
|---|---|
| **＋ Nuevo proyecto** | Empezar un video |
| **📺 Canales y estilos** | Guardar la identidad de tus canales y el banco de elementos |
| **📖 Manual de uso** | Este manual, con buscador |
| **🧾 Log de eventos** | El historial de todo lo que pasó (para diagnosticar problemas) |
| **⚙ Configuración** | Plantilla, claves, idioma, calidad, modelos y ahorro |
| **Proyectos** | La lista de tus videos, con buscador y filtro |
| **Versión (abajo)** | Qué versión tienes; clic para ver las novedades |

### 2.2 Las claves de API: la «llave» de cada servicio

Una **clave de API** es una contraseña larga que le das al programa para que
pueda usar un servicio de inteligencia artificial **en tu nombre y con tu
cuenta**. Se pega una vez y se queda guardada en tu equipo.

Ve a **⚙ Configuración → 🔑 Claves de API**, pega cada clave y pulsa
**💾 Guardar claves**. El punto verde ● confirma que quedó configurada.

![El selector de plantilla y las claves de API](docs/manual/clasica/09-plantilla-y-claves.png)

| Clave | Para qué sirve | ¿Es imprescindible? | Dónde se consigue |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Piensa el video: concepto, guion, escenas, dirección de arte, metadatos | **Sí.** Sin ella todo sale de ejemplo | console.anthropic.com → API Keys |
| `REPLICATE_API_TOKEN` | Crea las imágenes, los clips de video, el escalado, la música y el lipsync | Sí, para tener imágenes de verdad | replicate.com → API tokens |
| `OPENAI_API_KEY` | Transcribe tu voz (Whisper) y genera las imágenes donde se lee un texto | Sí, si narras tú | platform.openai.com → API keys |
| `ELEVENLABS_API_KEY` | Voces de máxima calidad y música con licencia comercial limpia | Opcional | elevenlabs.io → perfil |
| `CARTESIA_API_KEY` | Voz artificial mucho más barata que ElevenLabs | Opcional | cartesia.ai |
| `ASSEMBLYAI_API_KEY` | Transcripción más barata y con mejores tiempos por palabra | Opcional | assemblyai.com |

> ⚠ **Si falta una clave el programa no se rompe: cambia a «modo vista
> previa» y te avisa con un cartel amarillo.** En ese modo las imágenes son
> de relleno y la voz es un silencio con la duración correcta. Sirve para
> aprender a usarlo sin gastar, pero **no publiques un video hecho así**.

### 2.3 ffmpeg: la única instalación obligatoria

ffmpeg es un programa gratuito que corta, une y mezcla video y audio. Es el
«taller de montaje». **Sin él, ytstudio no funciona.**

- **Windows:** descarga `ffmpeg-release-essentials.zip` de
  [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) y descomprímelo en
  `C:\ffmpeg`, de modo que exista el archivo `C:\ffmpeg\bin\ffmpeg.exe`.
  No hace falta tocar nada más: el programa lo busca ahí solo.
- **Mac:** en la Terminal, `brew install ffmpeg`.
- **Linux:** `sudo apt install ffmpeg`.

### 2.4 Comprobar que todo está sano (gratis)

Doble clic en **`probar.bat`** (o `./probar.sh` en Mac/Linux). Ejecuta unas
60 baterías de comprobaciones internas en unos minutos.

- **No gasta un centavo**: no usa claves ni internet.
- **No toca tus proyectos**: trabaja en carpetas temporales.
- Termina diciendo **TODO EN VERDE** o exactamente qué falló y dónde.
- Si dice **VERDE PARCIAL — sin ffmpeg**, instálalo (punto 2.3): no se
  comprobaron ni la voz, ni el audio, ni el montaje.

Úsalo **después de cada actualización** y **antes de una generación cara**.

### 2.5 Actualizar el programa

| Archivo | Qué hace | Cuándo usarlo |
|---|---|---|
| **`pull.bat`** | Trae la última versión en segundos y te dice qué cambió | Siempre, es el normal |
| **`actualizar.bat`** | Lo mismo + reinstala las librerías (tarda más) | Solo si el aviso menciona que cambiaron las dependencias |

Después de actualizar, **cierra la ventana negra y vuelve a abrir
`iniciar.bat`**. Abajo a la izquierda verás la versión; haz clic para leer
las **novedades**.

Dos avisos que pueden aparecer ahí:

| Aviso | Qué significa | Qué hacer |
|---|---|---|
| **⚠ Actualización descargada pero NO aplicada** | Bajaste la versión nueva pero el programa sigue corriendo la vieja | Cierra la ventana negra y abre `iniciar.bat` otra vez |
| **⚠ N archivo(s) del programa modificados** | Hay archivos del programa distintos a los originales (pasa el ratón para ver cuáles) | Si no los tocaste tú, la orden `git checkout .` los restaura. Mientras difieran, actualizar puede fallar |

> 💡 **Tu material propio nunca cuenta como «modificado»**: tu música, tus
> efectos, tus ambientes, tu banco de elementos y tus proyectos viven en tu
> equipo y el programa los ignora a propósito.

### 2.6 Las dos plantillas de la interfaz

El programa se puede ver de **dos maneras distintas**, y eliges cuál usar sin
perder la otra. Las dos hablan con el mismo motor y con los mismos proyectos:
cambiar de una a otra **no toca nada de tu trabajo**.

| Plantilla | Cómo se ve | Sus pestañas |
|---|---|---|
| **Clásica** (la de este manual) | Oscura, con menú lateral | Guion · Storyboard · Editor · Video · Concepto · Archivos |
| **Nueva** | Editorial, con modo claro y oscuro | Corrida · Material · Guion · Escenas · Personajes · Metadatos |

**Para cambiar:** ve a **⚙ Configuración → 🎨 Plantilla de la interfaz**. Cada
plantilla se presenta en una **ficha con su miniatura**, su nombre y en qué se
nota, para que veas cómo es antes de probarla. Pulsa **«Usar esta plantilla»**
en la que quieras y aparece un **aviso de confirmación**: hasta que respondas
**«Sí, cambiar…»** no cambia nada. Entonces la página se recarga sola y el
**manual también cambia**, para que sus capturas coincidan con lo que tienes
delante.

![El selector de plantillas, con una ficha por plantilla](docs/manual/clasica/09-plantilla-y-claves.png)

> 💡 **Un clic suelto ya no te cambia de interfaz.** Hasta la v0.61.0 bastaba
> con pulsar el botón de la otra plantilla por curiosidad para acabar en una
> interfaz distinta. Desde la v0.62.0 hay que elegir y confirmar; si te
> arrepientes, **Cancelar** deja todo como estaba.

**Las dos tienen los mismos controles.** Desde la v0.61.0 no hay ninguna
función que solo esté en una: la estimación de costo antes de generar, la
parada en el punto de control, la presencia del personaje, duplicar y borrar
proyectos, el arco musical y el resto están en las dos. Lo que cambia es
**cómo se distribuye en pantalla**:

| Diferencia | Clásica | Nueva |
|---|---|---|
| Modo claro y oscuro | No (siempre oscura) | Sí |
| Material, personajes y escenas | Todo en pestañas de un mismo panel | En pantallas separadas |
| Subir tu material **al crear** el proyecto | Sí, en el propio formulario | No: se sube después, en Material |
| Ficha completa del concepto (ángulo, audiencia, estructura, paleta) | Sí, en la pestaña Concepto | No (pero sí «Guardar estilo») |
| Filtrar proyectos por estado (en curso, completos, con errores) | Sí | No (solo buscador) |

> 💡 **Elige la que te resulte más cómoda de leer.** Son dos vistas del mismo
> programa y los proyectos son los mismos: puedes ir y volver tantas veces
> como quieras, incluso a mitad de un video.

---

## 3. Tu primer video, paso a paso

Esta es una prueba completa que **cuesta centavos** y te enseña todo el
recorrido. Reserva 20 minutos.

**Paso 1 — Prepara el modo económico.** Ve a **⚙ Configuración**:

- En **Imágenes IA**, elige **FLUX schnell** (unos $0.003 por imagen: un
  video entero de prueba cuesta menos que un café).
- En **Video generativo por escena**, elige **Ninguno — Ken Burns**
  (movimiento de cámara sobre las imágenes: gratis y queda muy bien).
- En **Video → Duración objetivo**, pon **3 minutos**.
- Pulsa **💾 Guardar configuración**.

**Paso 2 — Crea el proyecto.** Menú **＋ Nuevo proyecto**:

1. **Nombre**: algo corto y sin acentos, por ejemplo `prueba-faros`.
2. **¿Para dónde es este video?**: deja **🎬 YouTube — video largo**.
3. **Escribe tu idea** en el recuadro grande. Una o dos frases bastan:
   «Un documental sobre los fareros que salvaron miles de vidas en el siglo
   XIX: soledad, tormentas y la luz que nunca se apagó».
4. **Estilo del video**: elige **Documental cinematográfico**.
5. Pulsa **Crear proyecto →**.

**Paso 3 — Mira lo que va a costar.** Ya dentro del proyecto verás la línea
**💰 Estimado antes de generar**. Haz clic para desplegar el detalle por
pasos. Ese número es tu presupuesto aproximado.

![El panel de un proyecto: los 11 pasos y la estimación](docs/manual/clasica/04-panel-del-proyecto.png)

**Paso 4 — Genera solo hasta el guion gráfico.** En el desplegable de arriba
elige **«Hasta el guion gráfico»** y pulsa **▶ Generar video**. En unos
minutos tendrás concepto, guion y todas las escenas planificadas, **sin
haber generado ninguna imagen** (que es lo que cuesta).

**Paso 5 — Revisa.** Abre la pestaña **📝 Guion** y léelo; corrige lo que
quieras y pulsa **💾 Guardar guion**. Luego abre **🎞 Storyboard** y mira
escena por escena qué se va a ilustrar.

**Paso 6 — Genera el video completo.** Vuelve a poner el desplegable en
**«Generar el video completo»** y pulsa **▶ Generar video**. Ahora sí se
crean las imágenes, la voz, la música y el montaje. Puedes cerrar el
navegador: **el trabajo sigue** en la ventana negra.

**Paso 7 — Míralo y elige.** Al terminar se abre sola la pestaña **▶ Video**.
Reproduce el resultado, elige entre las 3 miniaturas, los 3 títulos y las 3
descripciones, y descarga los archivos.

Ya está: ese es el ciclo completo. Todo lo demás en este manual es para
hacerlo **mejor** y **más barato**.

---

## 4. Elige el tipo de video: una receta para cada uno

Lo primero que eliges al crear un proyecto es **para dónde es el video**.
Esa elección cambia sola la forma de la pantalla, la duración, el tamaño del
texto y el estilo del guion.

![Los seis formatos y las plantillas de corto](docs/manual/clasica/02-formatos-y-plantillas.png)

| Formato | Forma de la pantalla | Duración a la que apunta | Subtítulos |
|---|---|---|---|
| 🎬 **YouTube — video largo** | Horizontal 16:9 | La que pongas en Configuración (10 min por defecto) | Pista activable |
| 📱 **YouTube Short** | Vertical 9:16 | ~55 segundos | Quemados (siempre visibles) |
| 📱 **Instagram Reel** | Vertical 9:16 | ~85 segundos | Quemados |
| 📱 **TikTok** | Vertical 9:16 | ~60 segundos | Quemados |
| 🟦 **Meta Ads cuadrado** | Cuadrado 1:1 | ~40 segundos | Quemados |
| 🟦 **Meta Ads / Feed IG** | Retrato 4:5 | ~40 segundos | Quemados |

> **«Subtítulos quemados»** significa que el texto va pintado dentro de la
> imagen y siempre se ve (imprescindible en redes, donde la gente mira sin
> sonido). **«Pista activable»** es el subtítulo que el espectador enciende o
> apaga en YouTube.

### 4.1 Receta A — Documental largo con TU voz (la mejor para tu canal)

Es la combinación más barata y la que suena a ti.

1. **Graba tu narración** completa en un solo archivo (mp3, wav o m4a).
   Consejos de grabación en el capítulo 13.2. Máximo ~69 minutos por
   archivo; si es más largo, divídelo en dos.
2. **＋ Nuevo proyecto** → formato **🎬 YouTube — video largo**.
3. Sube tu grabación en la casilla **🎙 Tu voz / narración**.
4. Si tienes guion escrito, súbelo también en **📄 Guion o idea** (así el
   programa no reinventa nada).
5. Elige el **estilo** (Documental cinematográfico suele ser el acierto
   seguro) o un **estilo guardado** de tu canal.
6. Crea el proyecto y genera **«Hasta el guion gráfico»**.
7. Revisa el storyboard y **luego** genera el video completo.

**Qué hace el programa con tu voz:** la transcribe con tiempos exactos,
limpia los tropiezos evidentes (capítulo 13), corta cada escena a la medida
de lo que dices y sincroniza subtítulos y rótulos a tu palabra exacta.

**Costo típico**: unos **$5-7** en total para 18 minutos con 84 escenas
(un plano cada ~13 segundos) e imágenes FLUX 1.1 Pro. Con el **modo híbrido**
(capítulo 11.2) el mismo video baja a **$2-3**. La transcripción de tu voz
cuesta unos **$0.11**.

### 4.2 Receta B — Video largo con voz artificial

Útil para probar formatos rápido o para canales sin locutor.

1. **⚙ Configuración → Voz en off**: elige el proveedor.
   - **Edge TTS**: **gratis** y sorprendentemente natural. Elige una voz
     **del idioma del video** (la voz no traduce).
   - **Cartesia Sonic**: la más barata con calidad de narración.
   - **OpenAI TTS**: muy barato (~$0.20-0.50 por video de 18 min).
   - **ElevenLabs**: la mejor calidad; se descuenta de tu plan.
2. Crea el proyecto escribiendo solo **la idea** o pegando tu guion.
3. Genera **«Solo el guion (revisar antes)»**, corrígelo a tu gusto en la
   pestaña 📝 Guion, guarda, y continúa.

> 💡 Con voz artificial puedes **alargar o acortar escenas** una por una en
> la pestaña ✂ Editor. Con tu voz grabada no: ahí manda tu narración.

### 4.3 Receta C — Short, Reel o TikTok (video vertical corto)

Los formatos cortos verticales (Shorts de YouTube, Reels de Instagram y
TikToks) comparten el mismo lenguaje: gancho en los dos primeros segundos,
texto grande, ritmo alto y subtítulos siempre visibles. El programa los
genera ya con esas reglas puestas.

1. **＋ Nuevo proyecto** → elige **📱 YouTube Short**, **📱 Instagram Reel**
   o **📱 TikTok**.
2. Aparece un nuevo desplegable: **🎬 Plantilla del corto**. Elige la
   estructura que quieres (tabla abajo). Es lo que más cambia el resultado.
3. Escribe el tema en una o dos frases. Cuanto más concreto, mejor.
4. Genera el video completo: un corto son unas 18 escenas, así que es
   rápido y barato (**alrededor de $1** con FLUX 1.1 Pro; céntimos con
   FLUX schnell).

**Las 7 plantillas de corto:**

| Plantilla | Cómo estructura el video | Ideal para |
|---|---|---|
| ✨ **Libre** | Gancho + desarrollo + cierre, decidido según el tema | Cuando no sabes cuál elegir |
| 🏆 **Top 3 / Ranking** | Cuenta regresiva 3 → 2 → 1, el mejor al final, con la música subiendo | Listas y comparativas |
| 🎭 **Historia con giro** | Empieza en mitad de la acción y suelta un giro inesperado al 70% | Relatos y casos reales |
| 🔁 **Antes / Después** | El problema, el proceso y el resultado, con pantalla dividida | Transformaciones y resultados |
| ❌✅ **Mito vs Realidad** | Enuncia el mito como si fuera cierto y lo desmonta con hechos | Divulgación y desmentidos |
| ⚡ **Tutorial en pasos** | Promete un resultado y da 3-5 pasos concretos | Cómo se hace algo |
| 🤯 **Dato impactante** | Abre con la cifra que rompe la cabeza y luego la explica | Curiosidades y estadísticas |

En los cortos el programa además usa una **biblioteca de 970 ganchos
virales probados** para escribir la primera frase, que es la que decide si
alguien se queda o pasa de largo.

### 4.4 Receta D — Anuncio para Meta (Facebook e Instagram)

1. Elige **🟦 Meta Ads — cuadrado 1:1** (para el muro) o
   **🟦 Meta Ads / Feed IG — retrato 4:5** (ocupa más pantalla en el móvil).
2. Elige la plantilla **⚡ Tutorial en pasos**, **🔁 Antes / Después** o
   **🤯 Dato impactante**, según lo que vendas.
3. En el texto de la idea, di **qué vendes, a quién y qué quieres que haga**
   el espectador. Ejemplo: «Curso de fotografía para principiantes; público
   de 25-40 años; quiero que se apunten a la clase gratuita».
4. Sube tus fotos de producto en **🎬 Tu B-roll**: en un anuncio, tu
   material real convence más que cualquier imagen generada.

### 4.5 Receta E — Video con un presentador en cámara (lipsync)

**«Lipsync»** significa que una foto de una persona se anima para que
**mueva la boca** al ritmo de la narración: parece que habla a cámara.

1. Consigue una **foto frontal, nítida y bien iluminada** del personaje.
2. Al crear el proyecto, súbela en la casilla **🧑 Personaje narrador**.
3. Elige la **presencia en pantalla**: 15%, 30% (recomendado), 45% o 60%.
   Es el porcentaje del video en el que se le ve hablando; el resto son
   imágenes ilustrativas.
4. Opcional: marca **🫧 Personaje en burbuja** para que aparezca en un
   círculo pequeño sobre las imágenes, al estilo de las reacciones de TikTok.
5. Sube también **tu voz grabada**: la boca se moverá con TU voz.
6. En **⚙ Configuración → Personaje narrador con lipsync**, empieza con
   **SadTalker**.

> ⚠ **Esto se cobra por segundo de personaje en pantalla, y es lo más caro
> del programa.** Un video de 10 minutos al 30% son 180 segundos de
> personaje: con SadTalker son unos $1-4; con **Hedra Character-3** unos
> $9-16; con **OmniHuman** $18-29. **Estrategia: itera con SadTalker y deja
> el modelo caro para la versión final.**

### 4.6 Receta F — Video de reacción

1. Grábate reaccionando al contenido, con o sin fondo verde (el programa
   detecta el fondo verde solo).
2. Sube ese archivo en la casilla **🎭 Tu video de reacción**.
3. Con fondo verde te recorta la silueta; sin él te pone en una burbuja
   circular. En los dos casos apareces **durante todo el video**.

### 4.7 Receta G — Copiar el estilo de un video que te gusta

1. Al crear el proyecto, pega la dirección del video (YouTube, Vimeo…) en
   **4 · Enlaces de referencia**.
2. El programa lo descarga, escucha su narración y mira sus imágenes para
   aprender el **ritmo de los cortes, la estructura y el estilo visual**.
3. Un solo enlace bueno vale más que tres regulares.
4. Cuando el resultado te guste, **guarda ese estilo** (capítulo 5.5) y
   reutilízalo gratis para siempre.

---

## 5. Antes de generar: preparar el material

Este es el capítulo más rentable del manual. **Cinco minutos aquí te ahorran
dólares y horas de corrección.**

### 5.1 Las seis casillas de archivos

![Las seis categorías de archivos](docs/manual/clasica/03-categorias-de-archivos.png)

Cada archivo va en su casilla, porque de eso depende cómo se usa. Puedes
subir varios a la vez y quitarlos con ✕. El límite es **300 MB por archivo**.

| Casilla | Qué poner ahí | Cómo se usa |
|---|---|---|
| 📄 **Guion o idea** | PDF, Word, PowerPoint, Excel, txt, md | Si es un guion, se respeta; si son notas, se usan como base |
| 🎙 **Tu voz / narración** | mp3, wav, m4a, ogg, opus | Es la voz del video, tal cual, con las escenas ajustadas a ella |
| 🎬 **Tu B-roll** | Tus imágenes y videos | Se reparten por el video en lugar de imágenes generadas |
| 🎨 **Referencia de estilo** | Imagen, video o documento | Se analiza para copiar su estilo y su tema |
| 🧑 **Personaje narrador** | Foto frontal de una persona | Habla en cámara con lipsync |
| 🎭 **Tu video de reacción** | Video tuyo reaccionando | Te compone sobre el video todo el rato |

> 💡 **Truco del nombre de archivo:** si nombras tu B-roll `scene_003.jpg` o
> `03_batalla.mp4`, ese archivo va exactamente a **esa** escena. Si no,
> se reparten de forma uniforme.

Después de crear el proyecto puedes **añadir o quitar material** en la
pestaña **📎 Archivos**. Ten en cuenta que al hacerlo se vuelve a analizar
todo y los pasos se regeneran.

### 5.2 El elenco: que un personaje tenga siempre la misma cara

Un problema clásico de las imágenes generadas es que el mismo personaje sale
con una cara distinta en cada escena. El **elenco** lo resuelve.

En la pestaña **📎 Archivos**, en el bloque «🧑 Elenco del video»:

1. Escribe el **nombre** del personaje (ej. «Alejandro»).
2. Escribe una **descripción breve**: rasgos, época, vestuario.
3. Pulsa **📷 fotos** y sube **una o varias** fotos de referencia.
4. Marca **narrador** si es quien habla a cámara.
5. Pulsa **＋ Crear personaje**.
6. **Importante: después de cambiar el elenco, usa «Rehacer desde →
   Escenas»** para que el director reparta bien los personajes.

Un personaje sin fotos recibe una referencia generada una sola vez, y esa se
reutiliza en todas sus escenas.

### 5.3 Cuánto va a costar y el freno automático

Al abrir un proyecto verás la línea **💰 Estimado antes de generar**. Haz
clic para ver el desglose por pasos: cuánto cuesta y cuánto tarda cada uno.

Además, el programa se pone a sí mismo un **tope de presupuesto** por
corrida: coge la estimación alta y la multiplica por 1.4 (`budget.margin`).
Si la generación intentara pasarse de ahí, **se detiene sola**. Ese margen
absorbe reintentos normales, pero frena un desbocamiento real.

- ¿Quieres un candado más estricto? Pon un número en `budget.max_usd`
  (0 = sin techo manual). Solo manda cuando es **más** restrictivo que el
  automático: nunca sirve para gastar más.
- El tope se recalcula antes de cada paso, así que en cuanto existen las
  escenas reales el cálculo se vuelve exacto.

### 5.4 El banco de elementos: material tuyo, gratis y para siempre

Cuando tu narración menciona a una persona, un lugar o una institución, el
programa puede superponer un **inserto**: una tarjeta con la foto real, la
cifra animada o el mapa, encima de la imagen de fondo. Es lo que hace que un
video parezca profesional.

El **banco de elementos** es tu archivo propio para esos insertos. Vive en
**📺 Canales y estilos**, al final de la página.

![El banco de elementos](docs/manual/clasica/13-banco-de-elementos.png)

**Cómo llenarlo, paso a paso:**

1. Ve a **📺 Canales y estilos** y baja hasta **🗄 Banco de elementos**.
2. Elige la categoría: 👤 Personajes, 📍 Lugares, 🏛 Entidades y marcas,
   🗺 Mapas o ✨ Stickers y adornos.
3. Pulsa **＋ Añadir archivos** y sube imágenes o clips cortos (mp4, webm,
   mov).
4. **El nombre del archivo es la clave**: `elon-musk.jpg` se encuentra
   cuando la narración dice «Elon Musk». No importan tildes ni mayúsculas.

**Reglas de oro del banco:**

- **Tu material siempre gana** sobre la búsqueda automática en internet.
- Usa solo material **de uso libre o propio** (Pixabay, Pexels, Openverse,
  Wikimedia con licencia libre). El programa no puede verificarlo por ti.
- **Llénalo una vez, rinde para siempre**: pon los 10-20 nombres que se
  repiten en tu canal (personajes recurrentes, países, instituciones) y se
  reutilizarán en todos tus videos futuros, gratis.

### 5.5 Estilos de canal: la identidad, guardada y reutilizable

Cuando un video te guste, **guarda su estilo** y arranca los siguientes con
la misma identidad **sin pagar el análisis otra vez**.

**Guardarlo:** entra al proyecto → pestaña **💡 Concepto** → botón
**💾 Guardar estilo** → ponle nombre y asígnalo a un canal.

![La pestaña Concepto y el botón de guardar estilo](docs/manual/clasica/08-concepto-y-guardar-estilo.png)

**Gestionarlos:** menú **📺 Canales y estilos**. Ahí creas canales (para
agrupar), editas estilos o creas uno desde cero.

![Canales y estilos guardados](docs/manual/clasica/12-canales-y-estilos.png)

Un estilo guarda: la descripción visual, el prefijo que se antepone a cada
imagen, la paleta de colores, el tono de la narración, la música, el ritmo,
las transiciones, la **fórmula narrativa** de tu canal y el **branding de
los rótulos**:

| Ajuste del rótulo | Opciones |
|---|---|
| **Tipografía** | Moderna (limpia) · Editorial (con aire de prensa) · Impacto (gruesa, viral) · Mono (técnica, de datos) |
| **Diseño** | Documental (placa oscura sobria) · Minimal (solo una línea de acento) · Bold (placa de color, máxima presencia) |
| **Colores** | Color de acento y color del texto |

Hay **cuatro combinaciones de un clic** para empezar: 🎞 Documental clásico,
⚡ Impacto viral, 🖥 Tech / datos y ◻ Minimalista.

**Usarlo:** al crear el proyecto, en «5 · Canal y estilo guardado», elige el
canal y el estilo. Ese proyecto nace con la identidad ya puesta.

---

## 6. Generar: los 11 pasos y el punto de control

### 6.1 Los tres controles de arriba

| Control | Qué hace |
|---|---|
| **Desplegable «Generar el video completo»** | Hasta dónde llegar: todo, «Solo el guion (revisar antes)» o «Hasta el guion gráfico» |
| **▶ Generar video** | Empieza (o **reanuda** donde se quedó, sin volver a pagar lo hecho) |
| **Desplegable «Rehacer desde…»** | Vuelve a hacer un paso concreto **y todos los siguientes** |

### 6.2 Los 11 pasos, y cuál cuesta dinero

| # | Paso | Qué hace | ¿Cuesta? |
|---|---|---|---|
| 1 | **Análisis** | Lee tu material, transcribe tu voz, estudia la referencia | Bajo |
| 2 | **Concepto** | Define estilo visual, tono y dirección musical | Bajo |
| 3 | **Guion** | Escribe el guion, o adopta el tuyo | Bajo |
| 4 | **Escenas** | Divide en escenas y diseña prompts, rótulos, música, sonido e insertos | Medio |
| 5 | **Voz** | Monta la pista de voz con respiros naturales | Bajo o nulo |
| 6 | **Imágenes** | Genera imágenes y clips, resuelve insertos y revisa la calidad | **ALTO — aquí está casi todo el gasto** |
| 7 | **Música** | Banda sonora por tramos + cama de ambiente | Bajo |
| 8 | **Subtítulos** | Subtítulos sincronizados a la voz real | Nulo |
| 9 | **Montaje** | Une, anima, superpone y mezcla (en tu PC) | Nulo |
| 10 | **Metadatos** | 3 títulos, 3 descripciones y 3 miniaturas | Bajo |
| 11 | **Publicación** | Deja el paquete final listo | Nulo |

### 6.3 EL momento clave: el punto de control del storyboard

Al terminar el paso **Escenas**, el programa escribe esto en el registro en
vivo, justo antes del paso que gasta el dinero:

```
📋 PUNTO DE CONTROL — storyboard listo: 84 escenas · ~18 min
   Revísalo en 04_scenes/storyboard.md
   💰 Falta por generar: ~$8.09-$16.91
   ⚠ Corregir AQUÍ no cuesta nada; corregir después cuesta volver a generar.
```

**Léelo siempre.** Es el último punto en el que cambiar algo es gratis.

⚠ **El programa no se para solo ahí**: si pediste el video completo, sigue de
largo hacia las imágenes. Para detenerte justo en ese punto, elige
**«Hasta el guion gráfico»** en el desplegable **antes** de pulsar Generar.
Es la costumbre que más dinero ahorra. Después aprovecha para:

1. Leer el **guion** (pestaña 📝 Guion) y corregir lo que no te guste.
2. Revisar el **storyboard** escena por escena (pestaña 🎞 Storyboard).
3. Subir **tu propio B-roll** a las escenas que quieras (capítulo 10.2).
4. Ajustar rótulos y movimiento en el **✂ Editor** (capítulo 10.3).

---

## 7. Durante la generación: qué vigilar

El panel muestra la barra de progreso, el porcentaje, el tiempo restante
estimado y, abajo, el registro en vivo.

**Puedes cerrar el navegador**: la generación continúa en la ventana negra.
Si cierras la ventana negra, se detiene (y luego se reanuda sin perder nada).

**Mensajes normales — no te asustes:**

| Mensaje | Qué significa |
|---|---|
| `⏳ OpenAI limita… espero 12s y reintento` | El proveedor pide ir más despacio; el programa se autorregula |
| `⏳ Anthropic no responde (429)… espero y reintento` | Lo mismo: **429** es «demasiadas peticiones». Se resuelve solo |
| `🔄 El contenido de N escenas cambió` | Rehace solo esas, no todas |
| `🎬 Diseño de escenas (tanda 2/3)` | Normal en videos largos: se trabaja por tandas |

**Mensajes que SÍ debes leer:**

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| `✂ Corregido en tu narración [12.3s, −1.4s]` | Se quitó un tropiezo de tu grabación | Mira los segundos: si el número es grande, escucha esa parte |
| `🛡 Descarté una corrección propuesta…` | El programa evitó borrar algo tuyo | Nada: es una buena noticia |
| `⚠ Sin foto de licencia libre para…` | Ese inserto no se pudo ilustrar | Añade el archivo a tu banco de elementos |
| `🔊 Detecté habla MUY BAJA en…` | Un tramo tuyo suena flojo | Se conserva igual; valóralo al revisar |
| `💰 Hay N resultados ya PAGADOS que no se descargaron` | Se cobró algo que no llegó | Pulsa **▶ Generar video** dentro de la hora siguiente: se recuperan **sin volver a cobrar** |

---

## 8. Después: revisar, elegir y publicar

Al terminar, el programa abre solo la pestaña **▶ Video**.

![El video terminado con las 3 miniaturas y los 3 títulos](docs/manual/clasica/07-video-y-metadatos.png)

**Paso a paso:**

1. **Mira el video entero.** Sí, entero, antes de publicarlo.
2. **Elige la miniatura**: hay 3 diseños (🎬 Cine, 💥 Impacto, ◧ Panel).
   Un clic la selecciona; el ✓ marca la elegida.
3. **Elige el título**: 3 estrategias distintas para que la gente haga clic
   (curiosidad, dato concreto, contradicción).
4. **Elige la descripción**: 3 enfoques. Incluyen **capítulos automáticos**
   (los minutos marcados) y los **créditos** del material de archivo.
   ⚠ **No borres los créditos**: son obligatorios por la licencia de las
   fotos libres.
5. **Descarga los archivos** desde los enlaces de abajo: `video_final.mp4`,
   `subtitulos.srt` y `miniatura.jpg`.
6. **Revisa el gasto real** en el bloque «📊 Gasto real de este proyecto».
   Eso es lo que de verdad se consumió, no una predicción.

Todo queda también en la carpeta `projects/<tu-proyecto>/09_final/`.

**Subir el video:** entra a YouTube Studio y sube el mp4, la miniatura y el
archivo de subtítulos, y pega el título y la descripción que elegiste.
(Existe una subida automática opcional: se activa poniendo
`publish.enabled` en verdadero y requiere las credenciales de Google del
capítulo 18.1. Por defecto está apagada.)

---

### 8.1 Los verticales llevan una revisión técnica aparte

Un Short, un Reel o un TikTok no se ven en una pantalla limpia: **la app dibuja
su interfaz ENCIMA de tu video**. Arriba el título, a la derecha la columna de
botones (me gusta, comentarios, compartir) y abajo el nombre de tu canal y el
**enlace al video largo**. Ese enlace es lo único que convierte a alguien que
ve un Short en alguien que ve tu video de diez minutos.

Al rectángulo del centro que sí es tuyo se le llama **zona segura** (el
espacio donde ningún botón de la app te va a tapar el texto). Por eso el
programa ahora trata la franja de abajo como terreno prohibido:

- **Los subtítulos de los verticales suben.** Antes se quemaban pegados al
  borde inferior, justo encima del enlace: lo tapaban. Ahora se colocan por
  encima de esa franja, sin que tengas que hacer nada.
- **En los videos horizontales no cambia nada.** Ahí no hay interfaz encima.

En la pestaña **Video**, debajo del reproductor, los proyectos verticales
muestran una tarjeta de **Revisión técnica del vertical**:

| Qué mide | Por qué importa |
|---|---|
| Tamaño y proporción | Si no es vertical, YouTube no lo trata como Short |
| Duración | Pasando de 3 minutos deja de ser Short; pasando de 60 segundos, una reclamación de música **bloquea el video en todo el mundo** (no lo desmoneta: lo bloquea) |
| Sonoridad (LUFS) | Lo importante. Ver abajo |
| Pico de sonido | Por encima del límite, se oye distorsión después de que YouTube recomprima |

**Lo de la sonoridad conviene entenderlo, porque es el error más caro y el más
barato de arreglar.** YouTube **baja** los videos que suenan demasiado alto,
pero **no sube** los que suenan bajo. Si tu video sale apagado, sale apagado
para siempre: sonará a la mitad de volumen que el anterior del feed, en un
teléfono, con altavoz, probablemente en la calle. Y el espectador no piensa
«esto está bajo»: desliza y se va.

Antes el programa **suponía** que la mezcla acababa en el nivel correcto.
Ahora lo **mide** en el archivo terminado y, si no está, lo corrige subiendo o
bajando todo por igual (las pausas y los silencios de tu montaje quedan
exactamente como estaban). Lo verás en el registro como
«🔊 Sonoridad corregida».

**El botón «Medir el archivo»** vuelve a medir cuando quieras. Es gratis: solo
lee el archivo, no gasta ni un centavo ni llama a ninguna IA.

**Lo que ninguna medición puede ver, y tienes que mirar tú:**

- ¿Hay **texto en pantalla desde el primer fotograma**? La mayoría de la gente
  ve los Shorts sin sonido: si tu gancho solo se oye, no existe.
- ¿El final **cierra**, o corta en seco?
- ¿La franja de abajo quedó libre?

**Míralo en un teléfono de verdad**, no en el ordenador: la interfaz de la app
cambia entre iPhone y Android, y solo ahí ves qué tapa qué.

> 📐 **Si editas algo a mano en otro programa** (Premiere, DaVinci, CapCut),
> tienes la guía en `assets\plantillas\PLANTILLA_ZonaSegura_1080x1920.png`:
> arrástrala a una pista por encima del video, pon tu texto dentro del
> rectángulo verde y **apaga esa pista antes de exportar**. Las instrucciones
> están en `assets\plantillas\README.md`. Para lo que genera el programa no
> hace falta: ya lo hace solo.

---

## 8.2 Sacar Shorts de un video largo

Cuando tienes un video largo terminado, el programa puede leerlo entero y
sacarle los Shorts que lleven gente a verlo.

### Lo primero, porque casi todo el mundo se equivoca aquí

**Un Short viral NO arrastra tu video largo.** YouTube usa dos sistemas de
recomendación separados, uno para vídeo corto y otro para largo. Que un Short
haga un millón de visitas no empuja nada hacia tu documental de diez minutos.

Lo único que construye ese puente es el **enlace a video relacionado**: un
enlace que aparece en el Short, debajo del nombre de tu canal, y que lleva al
video largo. Lo pones tú, a mano, y **es gratis**. Un Short sin ese enlace es
una vista regalada: entretiene a alguien y lo deja donde estaba.

Todo lo que hace esta función está pensado alrededor de eso.

### Cómo se hace

1. Abre el **proyecto del video largo** y entra en la pestaña **📱 Shorts**.
2. Elige **cuántos** quieres (3 a 7) y pon la **fecha** en que publicas —o
   publicaste— el video largo. De esa fecha sale el calendario.
3. Pulsa **📱 Proponer Shorts**. Tarda menos de un minuto y cuesta unos pocos
   céntimos: es una sola consulta al director.
4. Te salen las piezas propuestas. De cada una ves el guion completo, qué
   texto va en pantalla y de qué minuto del video largo sale. **Desmarca las
   que no te convenzan.**
5. Pulsa **＋ Crear los proyectos**. Se crean como borradores con el guion ya
   escrito. **Todavía no se genera ningún video ni se gasta nada.**
6. Abre cada uno y pulsa **▶ Generar video** cuando quieras.

> 💡 **También funciona con cualquier video de YouTube**, no solo con los
> tuyos: pega el enlace en la casilla de abajo. Si el video tiene subtítulos,
> el programa los lee con sus minutos y saca los Shorts igual, sin descargar
> el video (que puede ser de horas).

### Qué escribe exactamente

Cada pieza sale con la estructura completa, no con un trozo recortado:

| Bloque | Qué es |
|---|---|
| **Gancho** | La primera frase, dicha antes del medio segundo. Sin saludos ni «en este video te voy a explicar» |
| **Texto en pantalla** | El mismo gancho, escrito, desde el primer fotograma. La mayoría ve los Shorts **sin sonido**: si tu gancho solo se oye, no existe |
| **Promesa** | Qué se lleva quien se quede |
| **Desarrollo** | **Una sola idea.** Si un momento tiene dos, son dos Shorts |
| **Pago** | Se cumple lo prometido. Es el bloque que casi todos se saltan, y por el que luego no entienden por qué no reciben «me gusta»: el «me gusta» se decide justo ahí |
| **Llamada a la acción** | Una sola, al final, **hacia tu video largo** — nunca «suscríbete» |
| **Cierre de bucle** | La última frase enlaza con la primera. Los Shorts se repiten solos: así la gente lo ve dos veces sin darse cuenta |

### Los ganchos se rotan, y no es por gusto

El programa exige al director que use al menos **cuatro estructuras de gancho
distintas** en cada tanda, y te avisa si no lo consigue. La razón no es
estética: publicar siempre con la misma fórmula es exactamente lo que las
normas de YouTube describen como **producción en masa**, y eso sí tiene
consecuencias. Variar es la defensa.

### El calendario

Las piezas no salen todas de golpe. Cada una recibe un día alrededor del
video largo (D0 = el día que publicas el largo):

| Día | Función |
|---|---|
| **D−4** | Posicionamiento — por qué existe tu canal |
| **D−2** | Promesa — una curiosidad que el video largo resolverá |
| **D0** | Activación — pregunta directa, para que haya comentarios el día clave |
| **D+2** | Profundización — el concepto central |
| **D+4** | Emoción — la pieza con más carga |
| **D+7** | Expansión — la que funciona fuera de tu tema: trae público nuevo |
| **D+9** | Puente — enlaza con tu siguiente video largo |

El orden va de lo general a lo específico a propósito: las piezas que
necesitan contexto van **después** del video largo, cuando ese contexto ya
existe para recibir el clic.

**Publica tres o cuatro Shorts por semana, no a diario.** El riesgo del diario
no es que YouTube te castigue el algoritmo: es que la calidad del gancho se
degrada cuando el calendario aprieta, y que la cadencia diaria con plantilla
fija es el patrón de producción en masa otra vez.

### ⚠ El único paso que hay que hacer a mano

**Poner el enlace al video largo.** No se puede hacer desde fuera de YouTube:
no hay forma. Al subir cada Short:

1. Entra en **YouTube Studio** → **Contenido**
2. Haz clic en el Short
3. Busca **Video relacionado** y elige tu video largo
4. Guarda

El programa te dice exactamente qué video enlazar: está en la pestaña
**Shorts** de cada Short creado, junto con el título, la descripción y los
hashtags que le tocan.

> 💡 **Se puede añadir DESPUÉS de publicar**, y esto casi nadie lo aprovecha:
> el feed de Shorts no caduca. Cuando saques un video largo nuevo, puedes
> volver a tus Shorts antiguos —los que ya acumularon visitas— y reapuntarlos
> al video nuevo. Tu catálogo de Shorts se convierte en algo que puedes
> reutilizar en vez de en piezas de un solo uso.

---

### 8.3 Antes de publicar un vertical: la lista de comprobación

Cuando un proyecto vertical tiene su video terminado, debajo de la revisión
técnica aparece la tarjeta **«Antes de publicar»**. Es una lista con tres
tipos de punto:

| Marca | Qué significa |
|---|---|
| ✔ | La máquina lo comprobó y está bien |
| ✖ | La máquina lo comprobó y está **mal** — arréglalo antes de subir |
| ☐ | **Solo lo puedes mirar tú.** Son justo los que más se olvidan |

Lo que se comprueba solo: la revisión técnica del archivo, que el título
tenga entre 40 y 70 caracteres, que no lleve el hashtag de Shorts (no hace
falta: YouTube clasifica solo por proporción y duración), que la descripción
tenga 2-3 hashtags y enlace al video largo, que haya como mucho 5 tags y que
el archivo de subtítulos esté generado.

Lo que miras tú (los ☐): poner el **enlace a video relacionado** en Studio,
que el gancho se entienda **con el sonido apagado**, declarar **contenido
sintético** si aplica, y revisarlo **en un teléfono real**.

La lista se actualiza sola: si cambias el título elegido en Metadatos, se
recalcula.

**Los metadatos de los verticales ya salen con las reglas del formato.** Y si
el Short salió de un video largo (apartado 8.2), el título y la descripción
que decidió el plan editorial aparecen como primera opción — el resto son
variantes.

**Al publicar desde el programa** (con `publish.enabled` activado), además:
el archivo de subtítulos se sube aparte automáticamente, y si la miniatura de
Short todavía no está disponible en tu canal (YouTube la está desplegando
poco a poco), se avisa sin estropear nada: el video ya queda subido.

> 🔑 **Un aviso sobre permisos.** Para subir los subtítulos hizo falta pedir
> un permiso más en la autorización de Google. Si publicas con una
> autorización antigua y los subtítulos fallan, el arreglo es: borra el
> archivo `token.json` de la carpeta del programa y vuelve a publicar (te
> pedirá autorizar de nuevo, una sola vez). El video y la miniatura suben
> igual que siempre aunque no lo hagas.

---

### Comprobar que la actualización llegó de verdad

Actualizar tiene **dos pasos**, y saltarse el segundo es el despiste más
común:

1. **`actualizar.bat`** trae los archivos nuevos.
2. **Cerrar el programa y volver a abrirlo** con `iniciar.bat`. Mientras no lo
   hagas, sigue corriendo la versión vieja aunque los archivos ya sean nuevos.

**Cómo saber en qué versión estás:** míralo **arriba a la izquierda** en la
interfaz, junto al nombre `ytstudio`. Ese número sale de los archivos de tu
equipo, así que es la verdad.

> ⚠ **«Actualicé pero sigo en la versión de antes».** Desde la v0.65.3,
> `actualizar.bat` te dice si funcionó o no, y en qué versión te deja. Si
> sale **«NO SE PUDO ACTUALIZAR»**, la causa casi siempre es una de tres, y
> el propio archivo te da el comando para cada una. Si sale **«YA ESTABAS AL
> DÍA»** pero esperabas algo más nuevo, es que estás en otra **rama**: el
> archivo te dice en cuál.
>
> En ambos casos: **copia todo lo que salga en la ventana negra y pásamelo.**

---

## 9. Corregir sin volver a pagar

Esta es la tabla que más dinero te va a ahorrar. **Rehacer desde un paso
regenera ese paso y todos los siguientes**: por eso importa elegir bien
desde dónde.

| Quiero cambiar… | Qué hago | ¿Pierdo lo ya pagado? |
|---|---|---|
| Una imagen concreta | Subo mi propia imagen a esa escena (pestaña 🎞 Storyboard) | No |
| Rótulos, movimiento de cámara, transiciones, efectos, música | Los cambio en la pestaña ✂ Editor y remonto | No |
| El sonido de los insertos o el volumen de la música | Lo cambio en ⚙ Configuración y rehago desde **Montaje** | No |
| Todas las imágenes (cambiar de modelo) | Rehacer desde **Imágenes** | Sí, solo las imágenes |
| El texto del guion | Lo edito en la pestaña 📝 Guion y guardo | Sí, de ahí en adelante |
| El estilo visual completo | Rehacer desde **Concepto** | Sí, casi todo |

> ⚠ **Nunca rehagas desde Concepto, Guion o Escenas para arreglar una
> imagen.** Eso reescribe los prompts, **borra las imágenes que ya pagaste** y
> las vuelve a cobrar. Para una imagen concreta: sube la tuya, o rehaz desde
> **Imágenes**.

**Otras acciones útiles** (pasa el ratón por el nombre del proyecto en la
lista de la izquierda):

| Icono | Acción |
|---|---|
| ⧉ | **Duplicar** el proyecto (para probar una variante sin perder la buena) |
| ✎ | **Renombrar** |
| 🗑 | **Borrar** (no se puede deshacer) |

---

## 10. Las pantallas del programa, una por una

### 10.1 Pestaña 📝 Guion

El texto completo de la narración. Edítalo libremente y pulsa **💾 Guardar
guion**. Al guardar, los pasos posteriores se regeneran (porque las escenas
dependen del texto).

### 10.2 Pestaña 🎞 Storyboard

El plan de todas las escenas: imagen, narración, el prompt (la descripción
en inglés con la que se genera la imagen), el rótulo, la duración y la voz
de cada escena para escucharla.

![El storyboard, escena por escena](docs/manual/clasica/05-storyboard.png)

**Subir tu propia imagen o video a una escena:**

1. Busca la escena.
2. Pulsa **⬆ Subir imagen para esta escena** (algunas escenas aceptan también
   video, según lo que planificó el director).
3. Si te arrepientes, pulsa **✕ Quitar**: esa escena volverá a generarse.

Arriba hay dos casillas que controlan qué hace el programa con tu material:

| Casilla | Si está marcada | Si la desmarcas |
|---|---|---|
| **El director revisa con visión IA si tu B-roll encaja** | Comprueba que tu imagen tenga que ver con la escena y te avisa | Tu material se usa tal cual (gasta menos) |
| **Dejar que el director reemplace por IA lo que no encaje** | Sustituye tu imagen si cree que no pega | Se respeta siempre tu elección y solo te avisa |

### 10.3 Pestaña ✂ Editor de escenas

Aquí ajustas lo que se puede rehacer **barato**: solo hay que volver a
montar, no a generar. Es rápido y **no cuesta nada de inteligencia
artificial**.

![El editor de escenas](docs/manual/clasica/06-editor-de-escenas.png)

| Control | Qué cambia |
|---|---|
| 🧑 **B-roll / Personaje** | Quién ocupa la pantalla en esa escena (solo si hay personaje; el personaje se cobra por segundo) |
| 🎥 **Movimiento** | Zoom in, Zoom out, Paneo ←, Paneo → o Estática |
| 🔀 **Transición** | Corte seco o Fundido |
| 🔊 **Efecto** | Ninguno, Whoosh, Riser o Boom en la entrada de la escena |
| 🎵 **Intensidad musical** | De 0 (mínima) a 1 (clímax): dibuja el arco dramático |
| ⏱ **Duración** | Solo con voz artificial (con tu voz manda tu narración) |
| 🔤 **Rótulo** | El texto en pantalla, su encabezado y su tipo (personaje, lugar, fecha, dato, lista, conclusión) |

Cuando termines: **💾 Aplicar cambios** y acepta remontar.

### 10.4 Pestaña ▶ Video

El resultado, las 3 miniaturas, los 3 títulos, las 3 descripciones y las
descargas. Ver el capítulo 8.

### 10.5 Pestaña 💡 Concepto

La ficha de identidad del video: títulos propuestos, ángulo, audiencia,
tono, música, estructura, estilo visual y paleta de colores. Desde aquí se
guarda el estilo (capítulo 5.5).

### 10.6 Pestaña 📎 Archivos

Tu material subido, el elenco de personajes y el formulario para añadir más
archivos.

### 10.7 📺 Canales y estilos

Los canales, los estilos guardados y, al final de la página, el **banco de
elementos** (capítulo 5.4).

### 10.8 ⚙ Configuración

Se divide en seis bloques. Al terminar, **💾 Guardar configuración**.

**a) 🎨 Plantilla de la interfaz** — capítulo 2.6.

**b) 🔑 Claves de API** — capítulo 2.2.

**c) Estilo por defecto** — el que se propone en los proyectos nuevos:

| Estilo | Qué aspecto da |
|---|---|
| **Documental cinematográfico** | Estilo BBC/Netflix: luz natural dramática, colores sobrios, aire de cine |
| **Cine épico** | Gran escala: paisajes monumentales, contraluces, orquesta |
| **Misterio / true crime** | Sombras profundas, luz puntual, tensión constante |
| **Histórico / vintage** | Tonos sepia, grano de película, texturas de época |
| **Moderno / divulgación** | Limpio, colorido y ágil |
| **Automático** | La IA decide según el tema |

**d) Video:**

![Los ajustes de video e idioma](docs/manual/clasica/10-configuracion-video.png)

| Ajuste | Qué hace | Recomendación |
|---|---|---|
| **Duración objetivo** | A cuántos minutos apunta el guion | La normal de tu canal |
| **Resolución** | Full HD, 2K o 4K | Full HD: 2K y 4K tardan mucho más y casi no se nota |
| **Subtítulos** | Pista activable o quemados | Pista activable en YouTube; quemados en redes |
| **Idioma del video** | Guion, voz, subtítulos y metadatos | El tuyo. Con Edge TTS elige además una voz de ese idioma |
| **Ritmo visual** | Cada cuánto cambia la imagen | ~6 s dinámico · ~8-10 s estándar · ~15 s contemplativo |

> 💰 **El ritmo visual es un interruptor de gasto**: planos más cortos = más
> imágenes = más costo. En un video de 18 minutos, un plano cada 6 segundos
> son ~180 imágenes; cada 10 segundos, ~108; cada 13 segundos, ~84.

**e) Módulo de integraciones (los modelos de IA).** Cada bloque muestra las
opciones con su precio y su punto fuerte y débil, y un punto verde ● o rojo
● según tengas la clave.

![La elección del modelo de imágenes](docs/manual/clasica/11-configuracion-modelos-imagen.png)

**f) Audio:**

| Ajuste | Qué hace |
|---|---|
| **Volumen de música** | Cuánto suena la música por debajo de la voz |
| **Ducking automático** | Baja la música sola cuando hablas (déjalo activado) |
| **Sonido de los insertos** | El acento sonoro de las tarjetas: Automático, Archivo (papel y proyector), Sobrio, Épico, Registro (sello), Moderno (pop) o Sin sonido |

### 10.9 🧾 Log de eventos

El historial completo: novedades, avisos, errores y el tiempo de cada paso.
Se filtra por Todo / Avisos / Errores.

![El log de eventos](docs/manual/clasica/14-log-de-eventos.png)

---

## 11. Ahorrar dinero sin perder calidad

### 11.1 Cuánto cuesta de verdad

La referencia es un video de **~18 minutos con 84 escenas** (un plano cada
~13 segundos). Ojo: el número de escenas manda sobre todo lo demás. Con un
plano cada 6 segundos ese mismo video tendría ~180 escenas y las imágenes
costarían el doble.

| Concepto | Costo aproximado |
|---|---|
| Inteligencia: guion, escenas, dirección de arte, control de calidad | $1-3 |
| **Modo híbrido** (FLUX schnell + escalado) — la opción más rentable | **$0.40-0.60** |
| Imágenes con SDXL Lightning (borradores) | $0.13-0.17 |
| Imágenes con FLUX schnell (sin escalar) | $0.25-0.35 |
| Imágenes con FLUX 2 Flash | $1.3-2.1 |
| Imágenes con FLUX dev | $2.0-2.5 |
| Imágenes con Ideogram v3 Turbo (buena tipografía) | ~$2.5 |
| **Imágenes con FLUX 1.1 Pro** (la referencia de la casa) | **$3.4-4.2** |
| Imágenes con FLUX 2 Pro | $4.6-6.3 |
| Imágenes con GPT Image 2, calidad media | $2.5-5 ⚠ |
| Video generativo, 18 clips (Kling v1.6) | $2.3-6.3 ⚠ |
| Video generativo, 18 clips (Veo 3.1 Fast, con audio propio) | ~$13.5 ⚠ |
| Transcribir tu voz, 18 min (Whisper) | ~$0.11 |
| Transcribir tu voz, 18 min (AssemblyAI) | ~$0.05 |
| Voz artificial de OpenAI | $0.20-0.50 |
| Voz artificial de Cartesia | ~$0.19 |
| Voz artificial de Edge | gratis |
| Música generada (MusicGen) | $0.05-0.15 |
| Montaje, subtítulos, insertos, mapas y ambiente | gratis (se hacen en tu PC) |

### 11.2 El modo híbrido: la mayor palanca de ahorro

Genera las imágenes con un modelo barato y **súbeles la resolución después**
con un escalador (~$0.002 por imagen). Las 84 imágenes pasan de ~$4 a menos
de $0.60: un **90% menos**.

**Cómo activarlo:** **⚙ Configuración → Imágenes IA** → elige **FLUX
schnell** como modelo y activa **MODO HÍBRIDO: escalar las imágenes tras
generarlas**.

**Lo que el escalado hace y lo que no:** recupera **resolución**, no calidad
de origen. No inventa la microtextura ni la iluminación fina de un modelo
caro. Pruébalo con tu tema antes de adoptarlo para la versión final.

Las imágenes que **ya dan la talla** (tu B-roll, los respaldos locales) se
saltan solas: activarlo nunca cobra de más por ellas.

### 11.3 Las siete reglas del ahorro

1. **Prueba barato, publica caro.** Genera el video completo con **FLUX
   schnell** (centavos). Cuando la estructura te convenza, cambia al modelo
   bueno y usa «Rehacer desde → Imágenes».
2. **Usa el modo híbrido** para el trabajo del día a día (capítulo 11.2).
3. **Deja apagado el video generativo.** Con `providers.videogen.max_scenes`
   en 0 no se genera ningún clip. 18 clips pueden costar tanto o más que las
   84 imágenes del video entero, y en un documental largo el movimiento de
   cámara (Ken Burns) casi no se distingue de un clip animado.
4. **Párate en el punto de control.** Corregir el storyboard es gratis.
5. **Reutiliza estilos** guardados: evitas volver a analizar referencias.
6. **Llena el banco de elementos**: material gratis, tuyo, para siempre.
7. **Narra tú.** Es gratis (solo pagas la transcripción, centavos) y suena
   mejor que cualquier voz artificial.

### 11.4 Los interruptores de gasto, uno por uno

| Ajuste | Efecto en la factura |
|---|---|
| `providers.images.model` | **El que más pesa.** De schnell a FLUX 2 Pro hay 20 veces de diferencia |
| `providers.images.upscale` | El modo híbrido: −90% en imágenes |
| `providers.videogen.max_scenes` | 0 = sin video generativo. **El mayor ahorro individual** |
| `providers.lipsync` y el % de presencia | Se cobra **por segundo** de personaje en pantalla |
| `video.scene_seconds` | Menos segundos por escena = más imágenes = más costo |
| `video.elements_ai` | Ilustrar con IA los insertos sin foto libre. **Apagado por defecto**; cada uno cuesta como una imagen |
| `video.elements_ai_max` | Tope de esas ilustraciones por video (3 por defecto) |
| `providers.images.fact_check` | Control de calidad: cuesta centavos y **ahorra** regeneraciones. Déjalo encendido |
| `providers.images.fact_check_retries` | Rondas de corrección (2). Cada ronda revisa **solo** lo corregido antes |
| `providers.images.quality` | Solo con GPT Image: de `low` a `high` el precio se multiplica por 40 |
| `providers.llm.model` | Haiku para probar, Sonnet para producción normal, Opus para la máxima calidad narrativa |

---

## 12. Subir la calidad: los ajustes que de verdad se notan

1. **Narra tú mismo.** Ninguna voz artificial transmite lo que la tuya.
2. **Usa un estilo guardado** con tu fórmula narrativa: los videos del canal
   dejan de parecer de canales distintos.
3. **Llena el banco de elementos.** Las fotos reales de personas y lugares
   son la diferencia entre «video de IA» y «documental».
4. **Deja `providers.images.fact_check` encendido.** Compara cada imagen con
   los hechos de tu narración (si algo está vivo o muerto, la especie, las
   cantidades) y corrige la que se contradiga.
5. **Ritmo según el género**: ~5-6 s para divulgación ágil, ~8-10 s para
   documental, ~15 s para contemplativo.
6. **Elige bien el estilo de rótulo**: Editorial para historia, Impacto para
   viral, Mono para datos.
7. **Sube tu propia música** a `assets/music/` con el nombre del ambiente
   (por ejemplo `cinematic-tension.mp3`) y elige «Biblioteca local»: música
   tuya, sin costo y sin problemas de derechos.
8. **Deja el ambiente encendido** (`audio.ambience`): el viento, la multitud
   o la lluvia de fondo hacen que la escena se sienta real.
9. **Revisa el storyboard**: cinco minutos leyendo prompts evitan diez
   imágenes equivocadas.
10. **Escucha los primeros 60 segundos** del video terminado comparando con
    tu grabación original, sobre todo la primera vez.
11. **Para los cortos, elige plantilla**: la estructura es la mitad del
    resultado.
12. **Para el gancho, un clip con audio nativo.** Veo 3.1 Fast trae su propio
    ambiente sincronizado; con `providers.videogen.max_scenes` en 1 o 2 pagas
    poco y el arranque gana mucho.

---

## 13. Tu narración grabada: todo lo que hay que saber

### 13.1 El corrector de tropiezos

Al usar tu voz, el programa detecta y elimina los **tropiezos evidentes**:
falsos arranques («El registró… El registro veterinario es…»), palabras
repetidas, muletillas sueltas y correcciones que anuncias en voz alta («voy
de nuevo», «corrijo»). Corta el audio además del texto y **anuncia cada
corrección con su duración**:

```
✂ Corregido en tu narración [836.0s, −0.9s]: se quitó «no con violencia,»
```

**Cinco protecciones impiden que se coma algo tuyo:** que el texto y el
tiempo cuadren, que el ritmo de habla sea posible, un tope de 20 segundos
por corte, que el empalme caiga en un silencio medido de verdad, y un tope
global del 8% de tu grabación.

**Cómo controlarlo:**

| Quiero… | Ajuste |
|---|---|
| Apagarlo del todo | `audio.fix_narration` en falso |
| Apagar solo la revisión con IA (la más atrevida) | `audio.fix_narration_ai` en falso |
| Que no se corrijan las palabras mal transcritas | `audio.polish_transcript` en falso |

> 💡 **La primera vez, escucha los primeros 60 segundos** y compáralos con
> lo que grabaste. Si notas que falta algo, busca los avisos `✂` y apaga
> `audio.fix_narration_ai`.

### 13.2 Cómo grabar para que salga bien

- **Volumen parejo**: no te acerques y te alejes del micrófono. El programa
  avisa si detecta habla muy baja.
- **Pausas naturales entre frases**: son las que usa el montaje para
  respirar y para colocar los cambios de imagen.
- **Si te equivocas, para, respira y repite la frase completa** desde el
  principio. Así el corrector la reconoce y la limpia bien.
- **Un solo archivo** por video, de máximo ~69 minutos.
- **Sin música de fondo** en la grabación: la música la pone el programa,
  y así puede bajarla sola cuando hablas.

---

## 14. Las funciones automáticas, explicadas una por una

Todo esto ocurre solo, sin que tengas que pedirlo.

| Función | Qué hace | Dónde se ajusta |
|---|---|---|
| **Insertos documentales** | Cuando la narración menciona a alguien o algo, superpone una tarjeta con la foto real, una cifra que sube contando o una fecha | `video.elements` |
| **Fotos libres de internet** | Si no está en tu banco, busca en Wikimedia una foto de licencia libre y añade el crédito a la descripción | `video.elements_web` |
| **Mapas localizadores** | Un punto animado sobre un mapa real cuando se nombra un lugar; si el servicio no responde, usa una imagen del sitio (nunca una ficha vacía) | `video.elements_map_zoom` |
| **Rótulos con diseño** | El letrero en pantalla con placa de fondo, línea de acento y palabra clave en color | `video.overlays`, y el estilo del canal |
| **Cama de ambiente** | Fondo sonoro por tramos: viento, multitud, sala, lluvia, mar, fuego o tensión, según lo que se narra | `audio.ambience` |
| **Efectos incidentales** | Whoosh, riser, boom, papel y latido en los cortes | `audio.sfx` |
| **Acento de los insertos** | La paleta sonora de las tarjetas (archivo, sobrio, épico, registro, moderno o mudo) | `audio.element_sfx` |
| **Música por tramos** | Con tu biblioteca local y videos de más de 3 minutos, una pista distinta por tramo de intensidad, unidas con fundido | `providers.music.multi_track` |
| **Ducking** | La música baja sola cuando hablas | `audio.duck` |
| **Volumen estándar de YouTube** | La mezcla final se deja al nivel que espera la plataforma | automático |
| **Texto legible en la imagen** | Si en la escena se lee algo (un periódico, un cartel, una lápida), esa imagen se genera con el modelo que mejor escribe | automático |
| **Texto en su propia lengua** | Un papiro en arameo o una inscripción en latín se ven en esa lengua, no en la de tu narración | automático |
| **Encuadre documental** | Las escenas delicadas (un animal sin vida, una batalla, una herida) salen con un registro clínico y sobrio a la primera, sin que el generador las rechace | automático |
| **Auditoría de fidelidad** | Antes de generar, avisa si un prompt se dejó fuera un hecho de tu narración | automático, gratis |
| **Control de calidad factual** | Compara cada imagen ya generada con los hechos narrados y regenera la que se contradiga | `providers.images.fact_check` |
| **Escalado del modo híbrido** | Sube la resolución de las imágenes baratas y se salta las que ya dan la talla | `providers.images.upscale` |
| **Identidad de personajes** | Un personaje del elenco sale con la misma cara en todas sus escenas | pestaña 📎 Archivos |
| **Personaje narrador (lipsync)** | Tu presentador habla a cámara con tu voz | `providers.lipsync` |
| **Ganchos virales** | 970 plantillas probadas para la primera frase de los cortos | automático en formatos cortos |
| **Pantalla dividida** | Dos imágenes a la vez cuando la escena compara algo (el antes y el después) | automático |
| **Stickers de red social** | Imitación animada de los stickers de encuesta, pregunta o cuenta atrás (decorativos: no se pueden pulsar) | automático en formatos cortos |
| **Subtítulos** | Líneas cortas de estilo cine, cortadas al terminar cada frase | `subtitles.max_chars_per_line` |
| **Capítulos automáticos** | Los minutos marcados en la descripción de YouTube | automático |
| **Créditos automáticos** | El crédito obligatorio del material de archivo, en la descripción | automático |

**Para poner tu propio material de audio:**

- `assets/music/` — tus pistas de música (nombra el archivo con el ambiente).
- `assets/sfx/` — tus efectos de sonido.
- `assets/sfx/ambientes/` — tus fondos ambientales.
- `assets/elements/` — el banco de elementos (mejor desde la interfaz).

Cada carpeta tiene dentro un archivo README con los nombres que reconoce.

---

## 15. Problemas frecuentes y cómo resolverlos

| Síntoma | Causa probable | Solución |
|---|---|---|
| Sale el cartel «modo vista previa» | Falta una clave de API | ⚙ Configuración → 🔑 Claves de API |
| «**No encontrado**» al abrir un proyecto | Le pasaba a los proyectos cuyo nombre llevaba **tilde o eñe**. Arreglado en la v0.65.2: actualiza con `actualizar.bat` y vuelven a abrirse solos, sin tocar nada. Los proyectos nuevos ya se guardan con nombres simples (el nombre bonito, con sus tildes, se sigue viendo igual en pantalla) |
| «**voice ID must be a valid UUID**» u otro error de voz al generar | **Cambiaste de proveedor de voz y la voz del anterior se quedó puesta.** Cada casa nombra sus voces distinto. Ve a **Ajustes → Voz en off** y elige una voz de la lista del proveedor que tengas puesto. Desde la v0.65.4 el programa te avisa antes de empezar y, si llega el caso, usa su voz por defecto en vez de tirar la corrida |
| «**Error 429** al pedir Shorts de un enlace de YouTube» | YouTube limita las consultas desde tu conexión cuando se hacen varias seguidas. **No es un fallo del programa.** Espera unos minutos; o mejor, si el video largo es un proyecto de este programa, **deja la casilla del enlace vacía**: así el material se lee de tu propio proyecto, que es mejor fuente y no toca YouTube |
| «Ese video no tiene subtítulos disponibles» | El programa lee lo que se dice en el video a través de sus subtítulos. Si el video es tuyo, actívalos en YouTube Studio; si no, saca los Shorts desde el proyecto de este programa |
| `ConnectionAbortedError` **en la ventana negra** | Ruido inofensivo: el navegador cerró la conexión (recargaste, cerraste la pestaña…). Desde la v0.65.1 ya no se imprime |
| Se detuvo con un error **429** | El proveedor pide ir más despacio | Ya reintenta solo; si insiste, baja `performance.parallel_images` a 2 |
| Faltan trozos de mi narración | El corrector cortó de más | Busca los avisos `✂`, apaga `audio.fix_narration_ai` y rehaz desde **Análisis** |
| Costó más de lo estimado | Modelo caro o video generativo activo | Revisa el capítulo 11.4 |
| Las imágenes no respetan lo que digo | El prompt era ambiguo | Deja `providers.images.fact_check` encendido, corrige el prompt en el storyboard y rehaz desde **Imágenes** |
| Falta un inserto | No había foto de licencia libre | Añade el archivo a tu banco de elementos y rehaz desde **Imágenes** |
| Las imágenes escaladas se ven planas | El escalado recupera resolución, no microtextura | Genera la versión final con FLUX 1.1 Pro o FLUX 2 |
| El personaje sale recortado o desincronizado | Clips de una versión anterior | «Rehacer desde → Imágenes»: solo se rehacen los clips antiguos |
| Los subtítulos van desfasados | Proyecto de una versión antigua | «Rehacer desde → Voz» |
| El sonido de los insertos no pega | La paleta por defecto no encaja | ⚙ Configuración → Audio → Sonido de los insertos |
| Un modelo falla con «no encontrado» | El proveedor lo renombró o lo retiró | Elige otro modelo de la lista en ⚙ Configuración |
| No arranca / dice que falta ffmpeg | ffmpeg no está instalado | Instálalo (capítulo 2.3); en Windows, en `C:\ffmpeg\bin` |
| Rutas nuevas responden «No encontrado» | Actualizaste sin reiniciar | Cierra la ventana negra y abre `iniciar.bat` otra vez |
| El video se ve recortado | El proyecto se creó con otro formato | Crea un proyecto nuevo con el formato correcto (se fija al crearlo) |
| La interfaz no es la que esperaba | Está activa la otra plantilla | ⚙ Configuración → 🎨 Plantilla de la interfaz (capítulo 2.6) |

---

## 16. Qué SÍ y qué NO hacer

**SÍ:**

- Ejecutar **`probar.bat`** después de cada actualización.
- Pararte en el **punto de control** del storyboard.
- Probar con modelos baratos antes de la versión final.
- Ver y escuchar el video completo antes de publicarlo.
- Conservar los créditos del material de archivo en la descripción.
- Llenar el banco de elementos poco a poco.
- Guardar el estilo de los videos que te gusten.

**NO:**

- No borres carpetas de `projects/` mientras se está generando.
- **Nunca rehagas** desde Concepto, Guion o Escenas para arreglar una imagen.
- No subas material del que no tengas derechos: el programa no puede
  verificarlo por ti.
- No edites `config.yaml` a mano si puedes hacerlo desde ⚙ Configuración
  (tus ajustes se guardan aparte, en `config.local.yaml`, para que una
  actualización no los pise).
- No des por bueno un video sin leer los avisos ⚠ del panel.
- No cierres la ventana negra durante una generación larga si no quieres
  detenerla.

---

## 17. Glosario en palabras normales

- **B-roll**: las imágenes o los videos que se ven mientras alguien habla.
- **Storyboard (guion gráfico)**: el plan de todas las escenas, con lo que
  se verá en cada una, hecho **antes** de generar nada.
- **Prompt**: la descripción con la que se le pide una imagen a la IA.
- **Inserto**: la tarjeta que se superpone al B-roll (una foto, una cifra,
  un mapa).
- **Rótulo**: el texto que aparece en pantalla (un nombre, una fecha, un
  dato).
- **Miniatura**: la imagen de portada del video en YouTube.
- **Metadatos**: el título, la descripción y las etiquetas.
- **Fase o paso**: cada uno de los 11 tramos de la generación.
- **Corrida**: una ejecución del programa sobre un proyecto.
- **Reanudar**: seguir donde se quedó **sin volver a pagar** lo ya hecho.
- **Tope de presupuesto**: el freno automático de gasto de cada corrida.
- **Modo híbrido**: generar barato y subir la resolución después.
- **Ken Burns**: el movimiento lento de cámara sobre una foto fija.
- **Lipsync**: animar una foto para que mueva la boca al hablar.
- **Ducking**: bajar la música automáticamente cuando entra la voz.
- **Clave de API**: la contraseña que permite usar un servicio de IA con tu
  cuenta.
- **Plantilla de la interfaz**: cómo se ve el programa (clásica o nueva); no
  cambia lo que produce.
- **Modo vista previa**: el modo sin claves, con contenido de relleno y
  costo cero.

---

## 18. Torre de Control: el panel de todos tus canales

ytstudio **hace** los videos; la **Torre de Control** **administra** los
canales. Se abre con doble clic en **`panel.bat`** (o `./panel.sh`) y vive
en http://localhost:8766. Todo lo que ve y guarda está **en tu equipo**, no
en ningún servicio de terceros.

![La portada de la Torre de Control](docs/manual/panel/01-torre-de-control.png)

### 18.1 Preparar Google (una sola vez, ~15 minutos)

1. Entra a [console.cloud.google.com](https://console.cloud.google.com) con
   tu cuenta principal y crea **UN** proyecto (por ejemplo «mi-panel»). Uno
   solo para todo: crear varios para sumar cuota va contra las normas de
   YouTube y es sancionable.
2. En **APIs y servicios → Biblioteca**, activa **YouTube Data API v3** y
   **YouTube Analytics API**.
3. En **Pantalla de consentimiento OAuth**: tipo **Externo**, rellena nombre
   y correos. Mientras la aplicación esté «En pruebas», añade en **Usuarios
   de prueba** los correos de **todas** las cuentas dueñas de tus canales.
4. En **Credenciales → Crear credenciales → ID de cliente de OAuth**, tipo
   **«App de escritorio»**. Descarga el archivo como `client_secrets.json` y
   déjalo en la carpeta del programa.

> ⚠ **Mientras la aplicación esté «En pruebas», Google caduca los permisos
> cada 7 días** y el panel te pedirá reconectar los canales. Es molesto pero
> normal. La solución definitiva es **publicar la aplicación** y pasar la
> verificación de Google (gratuita; pide una web con política de privacidad
> y un video de demostración, y tarda de días a semanas).

> 💡 Si Google responde **«Error 400: redirect_uri_mismatch»**, crea la
> credencial como **«Aplicación web»** y añade en URIs de redireccionamiento
> exactamente `http://localhost:8766/oauth/callback`. El panel acepta los dos
> formatos.

### 18.2 Conectar los canales

Pulsa **＋ Conectar canal**, elige la cuenta de Google, elige la identidad
del canal si esa cuenta tiene varios, y acepta los permisos. Repite por cada
canal: **un permiso por canal**, sin importar de qué cuenta sea.

Al conectar, el panel trae la primera foto: 90 días de métricas diarias y
los últimos 50 videos. Los **ingresos** solo aparecen en canales dentro del
Programa de Socios; en los demás dirá «ingresos sin acceso», y no es un
error. Además son **estimados**: la cifra real de pago vive en AdSense.

> 💡 ¿Quieres ver el panel amueblado sin conectar nada? Pulsa **Cargar
> demo**: crea 4 canales ficticios que no llaman a ninguna API. **Quitar
> demo** los borra.

### 18.3 Sincronizar cada día

- **A mano**: botón **⟳ Sincronizar**.
- **Programado** (recomendado): una tarea diaria que ejecute
  `py -m ytpanel sync` (Programador de tareas de Windows) o
  `python3 -m ytpanel sync` (cron en Mac/Linux).

Leer métricas casi no consume cuota (unas 3 unidades por canal y corrida, de
10 000 diarias). El medidor de la cabecera muestra lo gastado hoy.

### 18.4 Editar sin salir del panel

Cada video tiene un lápiz **✎** en su fila. Se abre el editor con:

- **Título** (límite 100 caracteres), **descripción** (límite 5 000 bytes;
  las tildes y los emojis cuentan más de un carácter) y **etiquetas**
  (~500 caracteres en total), con contadores en vivo.
- **Miniatura** (JPG o PNG de hasta 2 MB; el canal debe estar verificado por
  teléfono).
- **Playlists**: crear listas y añadir, quitar o reordenar videos.

**Edición en lote:** el botón **☑ Edición en lote** activa casillas en la
tabla. Marcas varios videos, eliges la operación (buscar y reemplazar,
añadir texto al final de la descripción, añadir etiquetas o añadir a una
playlist) y pulsas **Vista previa**: verás el antes → después y el costo en
cuota **antes** de confirmar.

**Todo pasa por una cola** (el chip «📋 Cola» de la cabecera). Cada edición
consume unas 51 unidades de las 10 000 diarias, así que un lote grande
puede no caber hoy: la cola ejecuta lo que cabe, deja el resto en espera con
su motivo y lo retoma sola tras el reinicio de cuota (medianoche, hora del
Pacífico). Además reserva unidades (`panel.quota_reserve`) para que las
ediciones nunca dejen sin cuota a la sincronización nocturna.

### 18.5 Reportes y alertas

El botón **📊 Reportes** abre el análisis de toda tu red. Se calcula sobre
el histórico que ya tienes guardado: **no gasta cuota**, así que puedes
preguntar lo que quieras las veces que quieras.

![Los reportes comparando todos los canales](docs/manual/panel/02-reportes-de-la-red.png)

- **Comparativa entre canales**: una métrica (vistas, horas vistas,
  suscriptores netos, ingresos, me gusta o comentarios) y un periodo, con
  todos los canales en el mismo gráfico. Un hueco en la línea significa «no
  hay dato», no «cero».
- **Tabla dinámica**: los mismos datos agrupados por canal, día, semana o
  mes, con el **RPM** (ingresos por cada mil vistas), que es la métrica para
  comparar canales de tamaños distintos.
- **Mejores videos de la red**: ranking de todos tus canales juntos.
- **Exportar a Excel**: tres archivos CSV listos para abrir con doble clic
  (separador «;», decimales con coma).

En la portada, encima de las tarjetas, el panel te dice qué merece tu
atención hoy:

| Alerta | Cuándo aparece |
|---|---|
| ⛔ Hay que reconectar el canal | El permiso caducó: no entran métricas ni ediciones |
| ⚠ N días sin sincronizar | Los números que ves están congelados |
| ⚠ Las vistas cayeron X % | 7 días contra los 7 anteriores |
| ⚠ Los ingresos cayeron X % | Igual, con los ingresos estimados |
| ⚠ N días sin publicar | El canal se apagó y el alcance se resiente |
| ⚠ Ediciones fallaron en la cola | Esos cambios **no** están en YouTube |
| ▲ Las vistas subieron X % | Para que sepas qué está funcionando |
| ▲ Un video va N× sobre su media | Una oportunidad con fecha de caducidad |

Los umbrales se ajustan en el bloque `panel.alertas` de `config.yaml`
(por ejemplo `panel.alertas.caida_vistas_pct` o
`panel.alertas.dias_sin_publicar`).

### 18.6 Tus datos y tu seguridad

- Los permisos de acceso se guardan **cifrados**. Si ves «⚠ Tokens sin
  cifrar», instala el componente con `pip install cryptography`.
- El panel solo escucha en tu propio equipo, nunca en la red.
- **Desconectar un canal borra** su permiso y todas sus métricas locales; el
  canal en YouTube no se toca.

---

## 19. Si algo falla: cómo pedir ayuda

1. Ve a **🧾 Log de eventos**.
2. Pulsa **⬇ Descargar**.
3. Comparte ese archivo describiendo qué esperabas y qué pasó.

Ahí está todo lo necesario para diagnosticarlo: cada aviso, cada error y el
tiempo de cada paso, con la fecha y el proyecto al que pertenece.

Y antes de nada, si algo se comporta raro después de una actualización:
cierra la ventana negra, vuelve a abrir `iniciar.bat` y ejecuta
**`probar.bat`**. Muchas rarezas se explican solas ahí.
