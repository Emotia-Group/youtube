# Novedades de ytstudio

Versionado semántico (SemVer): **Mayor.Menor.Revisión**.
- **Mayor**: cambios que rompen compatibilidad (aún en 0.x — programa de
  un solo usuario en desarrollo activo, puede cambiar sin previo aviso).
- **Menor**: funciones nuevas.
- **Revisión**: arreglos que no añaden función nueva.

La versión activa se muestra arriba a la izquierda en la interfaz (junto a la
fecha de actualización) — clic para ver este historial completo.

## v0.54.0 — 2026-08-14
Los seis detalles que encontraste en el video de prueba. Dos de ellos eran
fallos de verdad en el personaje con lipsync — y el segundo explicaba por qué
«la mayoría de las escenas» sonaban a destiempo.

- 🧑 EL ENCUADRE DEL PERSONAJE, ARREGLADO DE RAÍZ (creías haberlo arreglado, y
  con razón): el reencuadre de la foto al formato del video **existía, pero
  solo se aplicaba a las escenas cuyo lipsync FALLABA**. Las que salían bien
  seguían generándose con tu foto 9:16 tal cual, y el montaje tenía que
  recortarlas hasta el mentón. Ahora la foto se adapta al formato **antes** de
  generar ningún clip, y es esa la que se le entrega al modelo: los clips
  nacen ya en 16:9. Si no hay modelo de identidad disponible, el montaje
  compone el clip ENTERO sobre su propio fondo desenfocado — la cara no se
  corta ni en el peor caso (antes ese respaldo solo existía para imágenes
  fijas, no para clips).
- 🎙 Y LA SINCRONÍA CON TUS PAUSAS: el clip del personaje se generaba con el
  tramo de tu grabación **ORIGINAL**, no con el de la pista final. Como el
  director te ajustó 79 pausas, la boca iba por un lado y la voz por otro en
  casi todas las escenas habladas. Ahora el audio que mueve los labios se
  corta de la **pista que de verdad se oye**, con la duración exacta de la
  escena. Además, un clip de lipsync más corto que su escena ya **no se
  ralentiza** (eso desincronizaba por sí solo): se congela el último cuadro.
- 🔁 Y LOS CLIPS VIEJOS SE DETECTAN: cada clip guarda la firma de la foto y el
  audio con que se hizo. Al «Rehacer desde Imágenes», los que se generaron
  con la foto sin adaptar o con el audio anterior se rehacen (con aviso: son
  los únicos que cuestan); los demás se conservan.
- 🔤 TEXTO LEGIBLE COMO ESTÁNDAR (lo que pediste): hasta ahora el ruteo a
  gpt-image-1 solo miraba el texto que el director declaraba, y la norma que
  tenía era «pide texto borroso e ilegible» — justo lo que ves como defecto.
  Ahora: (1) se detecta que la escena muestra un objeto escrito aunque el
  director no lo declare (periódico, cartel, documento, lápida, pizarra…) y
  esa imagen se genera con el modelo de mejor tipografía; (2) toda petición
  de «unreadable/blurred text» del prompt se **invierte** a texto nítido y
  legible; (3) al director se le prohíbe pedir texto ilegible: o no hay texto
  en el plano, o el texto es correcto y legible; (4) el control con visión
  ahora reporta el **texto inventado** como defecto y lo manda regenerar.
- 🔊 EL SONIDO DE LOS INSERTOS, A TU GUSTO: todos entraban con el mismo «pop»
  de aplicación. Ahora hay **paletas** (⚙ Configuración → Audio): *archivo*
  (roce de papel + tic de proyector), *sobrio* (un soplo de aire), *épico*
  (cuerdas breves), *registro* (sello y clic), *moderno* (el pop de siempre) y
  *sin sonido*. En «Automático» manda el estilo del video, y dentro de cada
  paleta la foto, la cifra y el mapa suenan **distinto** — no el mismo golpe
  veinte veces. Cuatro efectos nuevos sintetizados en local (clic, aire,
  cuerda, sello), sin descargas ni costo.
- 🔡 SUBTÍTULOS SIN VIÑETAS: cada frase empezaba con «• ». La causa: al
  transcribir, tu guion se le pasa a Whisper como contexto de vocabulario y
  **Whisper copia el formato** — con un guion en viñetas, devuelve viñetas. El
  contexto ahora va limpio (solo palabras) y, por si acaso, se quitan las
  viñetas del texto Y de cada palabra con sus tiempos. Los guiones de diálogo
  («—No lo sabía») no se tocan.
- 🗺 LOCALIZADORES CON MATERIAL REAL: el mapa vacío con coordenadas que viste
  en «Nueva Inglaterra» era el respaldo local — una retícula con un punto que
  no aporta nada. **Se ha eliminado.** Ahora, si no hay cartografía real (el
  servicio de teselas no respondió), la mención se resuelve con una **imagen
  real del lugar** (tu banco → foto libre de Wikimedia → ilustración de época
  si autorizaste `elements_ai`) y, si tampoco la hay, el inserto simplemente
  no se pone. Además se prueban dos servidores de teselas antes de rendirse y
  se exige mayoría de teselas (un mapa a trozos parecía un error).

Batería nueva (`tests/test_v0_54_0.py`, 38 comprobaciones con clips, pistas de
voz y montajes reales de ffmpeg). Total: 56 baterías en verde.

## v0.53.0 — 2026-08-11
Cierra los **tres huecos** que declaré en la v0.52.0 y añade el idioma del
texto en pantalla que pediste.

- 🎥 LA VISIÓN YA MIRA DENTRO DE LOS CLIPS: hasta ahora el control factual
  revisaba la imagen fija de cada escena, pero un clip de video IA **se aleja
  de ella al animarla** — un animal que tu narración da por muerto podía
  acabar moviéndose. Ahora las escenas de video se revisan por un fotograma
  del INTERIOR del clip, y al revisor se le pide expresamente comprobar que
  el movimiento no contradiga lo narrado.
- 💰 Y SI UN CLIP FALLA, NO SE RE-PAGA: un clip cuesta 10 veces más que una
  imagen ($0.13-0.35 contra $0.04). En vez de regenerarlo, la escena **baja a
  su imagen fija animada**, que ya está verificada y no cuesta nada. Te queda
  el aviso explicando por qué.
- 🔁 CORRECCIÓN EN RONDAS (`fact_check_retries`, 2 por defecto): antes se
  corregía una sola vez y, si la segunda imagen seguía mal, se quedaba así.
  Cada ronda revisa **solo lo regenerado en la anterior**, así el gasto crece
  con los fallos reales y no con el tamaño del video. Con `1` vuelves al
  comportamiento anterior.
- 🔍 LA AUDITORÍA GRATUITA YA COMPRUEBA LA UBICACIÓN: además de la cantidad y
  el estado sin vida, ahora avisa si la narración sitúa una herida o marca en
  una parte concreta (cuello, pecho, lomo, pata…) y el prompt la pone en otra
  — o no la menciona. Con sinónimos en inglés, y sin falsos avisos cuando la
  palabra no es anatómica («la cabeza del imperio»).
- 🏺 EL TEXTO EN PANTALLA RESPETA LA LENGUA DE LA ESCENA: un papiro en arameo
  dentro de un documental en español debe leerse **en arameo**, no en
  español. El director indica esa lengua por escena (`image_text_lang`) y el
  prompt exige su grafía real, **sin traducir ni transliterar**. Si no la
  indica, manda el idioma del video, como hasta ahora. Y si no conoce la
  grafía exacta, se le pide describir el objeto con escritura ilegible en vez
  de inventar letras falsas.

Batería nueva (`tests/test_v0_53_0.py`, 26 comprobaciones, con clips reales de
ffmpeg y rondas de corrección simuladas).

## v0.52.0 — 2026-08-11
Preguntaste si la fidelidad factual estaba «al 100%». **No lo estaba**, y al
auditarla encontré un fallo que trabajaba EN CONTRA de ella.

- 🐛 EL SUAVIZADO DESHACÍA LA FIDELIDAD (el hallazgo grave): cuando un
  generador rechazaba una imagen por su contenido, el reintento sustituía
  «dead»→«ancient», «corpse»→«statue» y «wound»→«mark». Es decir, **borraba
  justo los hechos** que la dirección de arte acababa de fijar: un cabrito
  muerto se convertía en «un cabrito antiguo». Ahora el suavizado quita solo
  lo GRATUITO (sangre, vísceras, gore) y **conserva especie, estado sin vida,
  cantidad y ubicación**, pasando a registro clínico («lesion», no «mancha»).
- 🎞 EL ENCUADRE DOCUMENTAL YA VA DESDE EL PRIMER INTENTO (lo que pediste):
  el director marca cada escena delicada (animal sin vida, restos, herida,
  violencia histórica, anatomía, armas, desnudo artístico, sustancias) y el
  prompt sale con el registro que corresponde — clínico, sobrio, sin sangre,
  con el contexto real de documental divulgativo. Antes el primer intento
  salía en crudo, el filtro lo rechazaba y solo después se suavizaba: tiempo
  perdido, a veces dinero, y una imagen peor. Si el director no la marca, un
  detector automático (en español e inglés, con plurales) la marca igual.
  · **Nota técnica:** el encuadre describe la imagen que SÍ es admisible; no
    le declara al modelo que «esto no viola sus políticas». Esas fórmulas no
    funcionan —los filtros no leen declaraciones— y suelen empeorar el
    resultado. Pedir bien es lo que de verdad evita el rechazo.
- 🔍 AUDITORÍA DE FIDELIDAD GRATIS, ANTES DE PAGAR: al cerrar el storyboard se
  comprueba sin gastar un centavo que cada prompt refleja los hechos que su
  narración afirma — **la cantidad exacta** («tres orificios») y **el estado
  sin vida**. Si falta alguno, te lo dice con el número de escena para que lo
  corrijas donde es gratis. Hasta ahora eso solo lo cazaba el control con
  visión, es decir, con la imagen ya pagada.
- 📊 El log te dice cuántas escenas salieron encuadradas y cuáles necesitaron
  el segundo intento, por si quieres revisar su tono.

**Respuesta honesta a tu pregunta:** con esto la fidelidad tiene tres capas
(reglas al escribir el prompt → auditoría gratuita → control con visión) en
vez de una y media. Lo que sigue sin cubrirse: el control con visión revisa la
imagen fija de cada escena, no el movimiento de los clips de video IA, y
corrige una sola vez.

Batería nueva (`tests/test_v0_52_0.py`, 38 comprobaciones).

## v0.51.3 — 2026-08-11
**«⚠ hay cambios locales sin actualizar» te asustaba sin motivo.** Tenías la
última versión recién descargada y el aviso seguía ahí. No era tuyo el error:
era un descuido mío.

- 🗄 TU MATERIAL PROPIO YA NO CUENTA COMO «CAMBIO»: `assets/music/` estaba
  protegido, pero **`assets/elements/` (el banco) y `assets/sfx/` (efectos y
  ambientes) no lo estaban** — y son justo las carpetas donde el programa te
  pide poner tus archivos. Cada foto o sonido tuyo aparecía como una
  modificación del repositorio. Ya se ignoran; los README y las carpetas
  siguen viajando con el programa para que una instalación nueva funcione.
- 🏷 EL AVISO AHORA DICE QUÉ PASA: en vez de «hay cambios locales sin
  actualizar» (que sonaba a «estás desactualizado»), dice **«⚠ N archivo(s)
  del programa modificados»** y, al pasar el ratón, **los nombra** y explica
  que un `git pull` puede fallar mientras difieran.
- 🐛 De paso: el primer nombre de la lista salía sin su primera letra
  (`.gitignore` → `gitignore`) por limpiar los espacios de la salida de git.
- 📖 El manual estrena una tabla en §2.5 con los dos avisos de versión, qué
  significan y qué hacer con cada uno.

Batería nueva (`tests/test_v0_51_3.py`, 20 comprobaciones — le pregunta a git
de verdad si ignora tu material, y verifica que los README siguen versionados).

## v0.51.2 — 2026-08-10
Segunda tanda de tu reporte: con ffmpeg ya encontrado, pasaste de **34 fallos
a 3**. Los tres eran defectos de mis pruebas, no del programa.

- 🎨 DOS PRUEBAS VISUALES DEMASIADO ESTRICTAS (insertos de video y mapas):
  comprobaban que el fondo «plano» tuviera 2 colores o menos antes de que
  apareciera el inserto. En tu equipo la compresión de tu versión de ffmpeg
  deja **4 tonos casi idénticos** — y la prueba fallaba pese a que el inserto
  aparecía perfectamente (¡de 4 colores a 2 628!). Ahora se mide el **salto de
  variedad** del cuadro, no un número absoluto: funciona con cualquier ffmpeg.
- 🪟 LA PRUEBA DEL AVISO DE FFMPEG NO ERA VÁLIDA EN WINDOWS: para simular «no
  hay ffmpeg» yo vaciaba el PATH, pero en Windows el programa lo busca
  igualmente en `C:\ffmpeg` — que es exactamente lo que DEBE hacer. Es decir:
  la prueba fallaba porque el programa se comportaba bien. Ahora el aviso y el
  veredicto se comprueban sobre las funciones que los generan, así que el
  resultado es el mismo en Windows, Linux y Mac.

Sin cambios en el programa: solo en la suite de pruebas. 52 baterías en verde.

## v0.51.1 — 2026-08-10
**`probar.bat` fallaba 34 de 51 baterías con el programa perfectamente sano.**
Lo reportaste con capturas y tenías razón en sospechar: el error
«FileNotFoundError: [WinError 2] El sistema no puede encontrar el archivo
especificado» no venía de ytstudio, sino de mi suite de pruebas.

- 🔍 QUÉ PASABA: en Windows es normal tener ffmpeg en `C:\ffmpeg\bin` **sin**
  añadirlo al PATH del sistema. El programa se las arregla solo (lo busca ahí
  y lo añade al PATH de su proceso al empezar una generación) — por eso tus
  videos salían bien. Pero cada batería corre en su PROPIO proceso y **no
  pasaba por esa ayuda**: se quedaba sin ffmpeg y fallaban todas las de voz,
  audio y montaje.
- ✅ ARREGLADO: ahora el corredor de pruebas localiza ffmpeg UNA vez (con la
  misma búsqueda que usa el programa) y **hereda esa ruta a las 51 baterías**.
  En tu equipo deberían pasar todas.
- 🗣 Y SI DE VERDAD FALTA FFMPEG: en vez de 34 errores crípticos, sale **un
  solo aviso claro arriba** con dónde ponerlo (`C:\ffmpeg`, con el enlace de
  descarga) y qué implica.
- 🙅 HONESTIDAD DEL VEREDICTO: sin ffmpeg ya no dice «TODO EN VERDE — puedes
  generar con confianza» (sería mentir: no se probaron voz, audio ni montaje).
  Dice **VERDE PARCIAL** y te pide instalarlo antes de una generación
  importante.
- 📖 El manual estrena la sección **2.3 ffmpeg**, la única herramienta externa
  obligatoria, con instrucciones para Windows, Linux y Mac.

Batería nueva (`tests/test_v0_51_1.py`, 12 comprobaciones que corren el propio
corredor con y sin ffmpeg visible para verificar ambos caminos).

## v0.51.0 — 2026-08-10
**MANUAL DE USO dentro del programa.** Nuevo menú **📖 Manual de uso**, junto
al log de eventos: la guía completa para configurar y exprimir cada función,
escrita en claro y pensada para consultarse mientras trabajas.

- 📖 QUÉ TRAE, EN 12 SECCIONES: primeros pasos y claves de API · las
  decisiones ANTES de generar que ahorran dinero · las 11 fases explicadas ·
  el punto de control del storyboard · qué vigilar DURANTE · qué hacer
  DESPUÉS (y cómo corregir sin re-pagar) · la guía de ahorro con costos
  REALES · todo sobre tu narración · las funciones que quizá no conocías ·
  problemas frecuentes · qué SÍ y qué NO hacer · glosario.
- 🔎 CÓMODO DE USAR: índice lateral con salto directo a cada sección,
  buscador («costo», «rehacer», «banco»…) y tablas de consulta rápida.
- 🔄 NO PUEDE QUEDARSE ATRÁS: el manual declara qué versión documenta. Si el
  programa avanza y el manual no, **la interfaz te lo avisa** con un aviso
  visible y **`probar.bat` se pone en rojo** hasta que lo actualice. Además la
  batería comprueba que documenta las 11 fases, las 4 claves, las funciones
  principales y que **ningún ajuste que menciona es inventado** — si cambio un
  nombre de configuración y olvido el manual, la prueba lo caza.

Batería nueva (`tests/test_v0_51_0.py`, 24 comprobaciones).

### 🛟 Nota de mantenimiento
Durante esta sesión la rama de trabajo retrocedió sola a la v0.31.0 y se
perdieron de vista las versiones 0.32.0 a 0.50.0. Estaban intactas en el
historial y quedaron **restauradas por completo** (código, configuración,
changelog y las 50 baterías). Lo detectó justamente la batería del manual, al
comparar la versión declarada con la del programa.

## v0.50.0 — 2026-08-09
**Mapas localizadores animados** (Fase 4 de las 4 — el plan de calidad
audiovisual queda completo). Cuando la narración sitúa la historia («cruzó el
Sahara», «llegó a El Cairo», «el Imperio de Malí»), aparece un mapa con el
**pin cayendo sobre el punto exacto** y un anillo que se expande.

- 🗺 CARTOGRAFÍA REAL Y LIBRE: las coordenadas salen de Wikipedia y el mapa,
  de OpenStreetMap (vía Wikimedia Maps, licencia ODbL). El crédito
  «© colaboradores de OpenStreetMap» se añade solo a la descripción del
  video, igual que las fotos de Wikimedia.
- 🎨 NO PARECE UNA CAPTURA DE GOOGLE MAPS: el mapa se desatura, se oscurece y
  se tiñe con tu color de acento antes de componerlo, con el mismo marco de
  copia impresa que las fotos de archivo. El pie lleva el nombre del lugar y
  sus coordenadas.
- 🔍 ACERCAMIENTO CONFIGURABLE (`elements_map_zoom`): 3-4 vista continental ·
  5-6 país o región (por defecto) · 8-10 ciudad.
- 🛟 NUNCA FALLA: si no hay internet o el servicio no responde, sale una
  ficha de coordenadas generada en tu equipo, con el pin en su posición
  geográfica relativa correcta. Y si el lugar no tiene coordenadas, no se
  inventa nada: aviso honesto y esa escena queda sin inserto.
- 📁 Tu mapa propio manda: si pones un archivo con ese nombre en
  📚 Biblioteca → Banco → Mapas, se usa el tuyo y no se consulta la red.

Batería nueva (`tests/test_v0_50_0.py`, 30 comprobaciones: la proyección Web
Mercator contra puntos de referencia conocidos, unión de teselas con un
servidor simulado —incluidas teselas caídas—, la posición del pin medida en
píxeles y un render REAL de ffmpeg).

⚠ Honestidad sobre lo verificado: mi entorno no tiene acceso a internet, así
que la descarga de teselas está probada con un servidor SIMULADO (como las
fotos de Wikimedia en la v0.46.0). El respaldo local, la proyección, la
animación y el montaje están verificados de verdad. La primera descarga real
ocurrirá en tu máquina.

## v0.49.0 — 2026-08-09
**El banco de elementos, ahora desde la interfaz — y los insertos ya pueden
ser VIDEO** (Fase 3 de las 4).

- 🗄 BANCO GESTIONABLE EN 📚 BIBLIOTECA: nueva sección «Banco de elementos»
  con las 5 categorías (personajes, lugares, entidades, mapas, stickers).
  Arrastras archivos, los ves en miniatura (los clips se reproducen al pasar
  el ratón), y los quitas con un clic. Se acabó copiar carpetas a mano.
  Recuerda: **el nombre del archivo es la clave** — `elon-musk.jpg` encuentra
  la mención «Elon Musk», sin importar tildes ni mayúsculas.
- 🎬 INSERTOS EN VIDEO: el banco ya acepta clips (mp4, webm, mov), no solo
  imágenes. Un clip se compone enmarcado como una copia impresa —el mismo
  lenguaje visual que las fotos—, en bucle si es más corto que la ventana del
  inserto, y con sus fundidos. Ideal para material de archivo en movimiento.
- 🎨 ILUSTRACIÓN IA DE RESPALDO (opcional, `elements_ai`): cuando una entidad
  no tiene foto de licencia libre ni archivo tuyo, puede ilustrarse con IA en
  el estilo visual del video. **Viene APAGADA** porque cuesta como una imagen
  de B-roll (~$0.04 cada una) y no quiero sorpresas en tu factura; al
  encenderla hay un tope duro (`elements_ai_max`, 3 por defecto).
- 🐛 Un fallo de dinero cazado por la propia batería: los insertos se
  resuelven en 3 hilos a la vez y el tope de ilustraciones se comprobaba sin
  cerrojo — tres hilos podían pasar el mismo control y generar (y pagar) de
  más. La reserva de presupuesto ahora es atómica, y si la generación falla,
  el cupo se devuelve.
- El aviso de «sin foto libre» ahora te dice exactamente cómo cubrirlo: subir
  el archivo al banco desde la Biblioteca, o activar la ilustración IA.

Batería nueva (`tests/test_v0_49_0.py`, 27 comprobaciones: API del banco con
rutas encerradas, clips compuestos con un render REAL de ffmpeg, y el tope de
gasto verificado en tres corridas seguidas).

## v0.48.0 — 2026-08-09
**Diseño de sonido documental** (Fase 2 de las 4). La música ya dibujaba el
arco dramático, pero el fondo estaba VACÍO: un tramo que narra el desierto
sonaba exactamente igual que uno que narra un mercado.

- 🎧 UN DIRECTOR DE SONIDO EN EL EQUIPO: decide el AMBIENTE de cada acto
  (los mismos tramos que ya usa la música) según lo que se narra ahí —
  viento en el desierto, multitud en el mercado, sala en los tramos de
  archivo, lluvia, mar, fuego o un dron de tensión. Los ambientes se funden
  entre tramos, así que el lugar cambia con la historia y no de golpe.
  · **Una sola llamada por video** (~$0.02) con esfuerzo medio.
  · Puede elegir **'ninguno'**: el silencio también es diseño de sonido.
- 🔊 SIN COSTO DE MATERIAL: si tienes archivos propios en
  `assets/sfx/ambientes/` (`viento*.wav`, `multitud*.mp3`…), **mandan
  ellos**; si no, el programa los **sintetiza en tu equipo**, gratis. Hay un
  README en `assets/sfx/` con los nombres y dónde conseguir packs libres.
- 🎚 EN SU SITIO, NO ENCIMA: la cama va a −30 dB (ajustable con
  `ambience_db`), por debajo de la voz y la música, con fundido de entrada y
  muriendo exactamente con el video. Verificado midiendo una mezcla real:
  se oye, pero aporta menos de 1.5 dB al total — acompaña, no protagoniza.
- 🥁 DOS ACENTOS NUEVOS LIGADOS AL CONTENIDO, que el director coloca donde
  la narración lo pide: **'papel'** (un documento, un registro, una cifra de
  archivo) y **'latido'** (suspenso sostenido: peligro, espera, cuenta
  atrás). Se suman a whoosh/riser/boom y al 'pop' de los insertos.
- 🔌 Todo desactivable: `audio.ambience: false` deja el video con música y
  voz como hasta ahora. Y si el modelo falla o no hay escenas, la fase
  continúa con un aviso — el sonido de apoyo jamás detiene una generación.

Batería nueva (`tests/test_v0_48_0.py`, 24 comprobaciones que MIDEN el audio
real con ffmpeg: nivel de cada ambiente, prioridad de tu biblioteca, duración
y fundidos de la cama, y la aportación exacta a la mezcla final).

## v0.47.0 — 2026-08-09
**Los rótulos ya son diseño, no texto encima del video.** (Fase 1 de las 4
acordadas para la calidad audiovisual.) Tú mismo dijiste que se quedaban
cortos: tenías razón, eran `drawtext` pelado.

- 🎫 RÓTULO CON PLACA, FILETE Y JERARQUÍA: ahora se componen como imagen
  (igual que tus miniaturas), lo que permite tres cosas que antes eran
  imposibles:
  · **Placa de fondo** que garantiza el contraste sobre CUALQUIER B-roll —
    antes, sobre una imagen clara, el texto blanco se perdía.
  · **Filete de acento** que ancla el bloque: la marca de tu canal en cada
    rótulo.
  · **La palabra clave en color DENTRO de la línea** («Mansa **Musa**»,
    «**60.000** personas»). `drawtext` solo sabía pintar la línea entera de
    un color; por eso el énfasis nunca se notaba.
- 🎨 TRES VARIANTES, ELEGIBLES POR CANAL (⚙ Biblioteca → estilo → «Diseño del
  rótulo»):
  · **documental** — placa oscura sobria + filete dorado (por defecto),
  · **minimal** — sin placa, solo filete y tipografía con sombra,
  · **bold** — placa del color de acento con texto oscuro, máxima presencia.
  Los combos de branding de un clic ya traen la variante que les pega
  (Impacto viral → bold, Minimalista → minimal).
- 🔒 SIN RIESGOS: el gancho de apertura y la conclusión conservan su lenguaje
  propio; los proyectos antiguos (texto plano) reciben el diseño
  automáticamente; si algo fallara al componer, el rótulo sale como siempre.
  Con `overlay_plate: false` vuelves al estilo clásico cuando quieras.
- 💰 LA ESTIMACIÓN DECÍA «~7 LLAMADAS» y tu video de 84 escenas hace ~25: no
  contaba las TANDAS (diseño de escenas, dirección de arte, documentalista)
  ni el control de calidad con visión (una llamada por cada 6 imágenes). El
  tope de presupuesto se calculaba sobre esa base corta. Ahora se cuentan de
  verdad y el costo de inteligencia crece con el tamaño del video, como debe.

Batería nueva (`tests/test_v0_47_0.py`, 23 comprobaciones — mide los píxeles
de cada variante y verifica con un render REAL de ffmpeg que el rótulo
aparece cuando lo dices).

## v0.46.0 — 2026-08-09
**INSERTOS DOCUMENTALES (Fase 1 aprobada): el video deja de ser solo B-roll.**
Cuando la narración menciona a Elon Musk, El Cairo, la UNESCO, «60.000
personas» o «1324», un inserto de archivo aparece SOBRE el B-roll en el
instante exacto en que lo dices — como en un documental editado a mano.

- 🗄 UN NUEVO ESPECIALISTA EN EL EQUIPO: el **documentalista de archivo**.
  Tras la dirección de arte, recorre la narración y decide qué menciones
  merecen apoyo visual (personas, lugares, entidades, mapas, cifras, fechas).
  Es selectivo por diseño: máximo un inserto por escena y ~1 de cada 3-4 —
  acento documental, no papel tapiz. Corre en tandas con esfuerzo medio
  (~$0.30-0.60 por video largo) y si falla, el video sale igual (los insertos
  son un adorno: JAMÁS detienen una fase).
- 📎 TRES FUENTES, EN ORDEN DE PRIORIDAD:
  · **Tu banco local** (`assets/elements/personajes|lugares|entidades|mapas|
    stickers/`): pones `elon-musk.jpg` y esa se usa SIEMPRE primero (la
    búsqueda tolera tildes, guiones y mayúsculas). Hay un README en la
    carpeta con las reglas.
  · **Wikimedia/Wikipedia**: la foto canónica del artículo de la entidad,
    SOLO con licencia libre verificada (CC/dominio público) — y **el crédito
    se añade solo a la descripción del video** en Metadatos, a las 3
    opciones, para cumplir la licencia sin que hagas nada. Desactivable con
    `elements_web: false`.
  · **Generado en tu equipo, $0**: las cifras aparecen con CUENTA ASCENDENTE
    («60.000» sube hasta su valor real, conservando tu formato de miles) y
    las fechas en tarjeta — PIL local, ni un token.
- 🎯 EN EL INSTANTE EXACTO: el inserto se ancla a la PALABRA de la mención
  con los timestamps reales de Whisper (la misma maquinaria de los rótulos).
  Entra deslizándose arriba a la derecha (lejos de rótulos y subtítulos), se
  sostiene ~4s y se despide, con un **'pop' sutil** en la banda sonora (SFX
  local; también puedes poner tu propio `pop.wav` en assets/sfx/).
- 🎨 RESPETA LA IDENTIDAD: tarjeta de archivo sobria (marco blanco tipo
  copia impresa, pie con tu color de acento); en formatos cortos ni aparece
  (ahí mandan los stickers). Interruptor general: `video.elements`.
- 💰 COSTO REAL POR VIDEO LARGO: ~$0.30-0.60 de LLM + $0 de material
  (Wikimedia y tarjetas son gratis) + ~1-3 min de render. La mejora de
  calidad más barata del pipeline.

Batería nueva (`tests/test_v0_46_0.py`, 21 comprobaciones — incluye un render
REAL de ffmpeg midiendo píxeles para verificar que el inserto aparece cuando
debe, API de Wikimedia simulada sin internet).

## v0.45.1 — 2026-08-09
**El corrector de narración te borró 51.9 segundos de contenido legítimo.**
Lo encontré en tu log y es un fallo mío de diseño, no de tu grabación.

- 🔍 QUÉ PASÓ, EXACTAMENTE: los detectores razonan sobre la TRANSCRIPCIÓN
  (índices de palabra) pero el audio se corta por TIEMPO. Ese salto no tenía
  ninguna comprobación. Tu transcripción traía un tramo con tiempos
  disparatados al inicio: un corte que decía llevarse **22 palabras** («1 1 2
  3 4 5…», un conteo) se llevó **~48 SEGUNDOS de audio** — y ahí dentro
  estaban tu gancho de apertura y el párrafo de Forbes. El aviso solo mostraba
  las 22 palabras, así que era invisible.
- 🛡 LA VALLA NUEVA — ningún corte se aplica sin cuadrar con el audio real.
  Cinco comprobaciones, todas con el mismo principio (borrar contenido tuyo es
  mucho peor que dejar pasar un tropiezo):
  · **Coherencia texto↔tiempo**: si en el tramo de audio hay más palabras de
    las que el corte dice llevarse, se descarta (esto solo habría salvado tus
    48 segundos).
  · **Ritmo posible**: 22 palabras no ocupan 48 s. Si no cabe en un ritmo de
    habla real, los tiempos están mal.
  · **Tope por corte**: nada que dure más de 20 s es un «tropiezo».
  · **El empalme cae en silencio MEDIDO en la onda** (no en los tiempos de
    Whisper, que traen ±100 ms de error).
  · **Tope global**: si entre todas las correcciones se comen más del 8 % de
    tu grabación, no se toca NADA.
- 🎙 EL SEGUNDO CORTE («entre el 50 y el 60 por ciento»): ahí no había nada
  que corregir. El modelo creyó ver una reformulación en habla continua y el
  corte se comió desde el final de «producía». Ese caso lo bloquea ahora la
  cuarta valla: sin silencio en ninguno de los dos bordes, es cirugía en mitad
  de una frase fluida y se descarta. Además le dije al modelo explícitamente
  que el transcriptor a veces DUPLICA palabras que no están en el audio, y que
  un tramo sin pausas alrededor no se marca jamás.
- 👀 VISIBILIDAD: cada corrección aplicada dice ahora **cuántos segundos
  quita** (`[0.0s, −48.3s]`) — un «tropiezo» de 48 s salta a la vista. Y cada
  corrección descartada aparece con su motivo y la frase «Tu grabación queda
  INTACTA ahí».
- ✂ El corte deja de tragarse silencios largos que no le corresponden (como
  mucho 1 s tras la palabra): las pausas son cosa del compresor de pausas de
  la fase de Voz, con su tope `max_pause`.

Batería nueva (`tests/test_v0_45_1.py`, 16 comprobaciones que reproducen tus
dos cortes con audio real medido por ffmpeg).

## v0.45.0 — 2026-08-09
Aprobaste el cambio de proveedor de imágenes: **Replicate FLUX 1.1 Pro pasa a
ser el estándar** y gpt-image-1 queda solo para las escenas con texto legible.

- 💰 EL PORQUÉ, EN NÚMEROS: un video largo de 83 imágenes cuesta **$3.32-4.15
  con FLUX** contra $5.81-20.75 con gpt-image-1 — y FLUX no tiene el cuello
  de botella de 5 imágenes por minuto que te frenó la fase en «3-mansa-musa».
  Además su look fotorrealista cinematográfico es la referencia para el
  estilo documental.
- 🔁 MIGRACIÓN AUTOMÁTICA DE UNA SOLA VEZ: al primer arranque después de
  actualizar, tu `config.local.yaml` pasa de openai a replicate/FLUX solo. Es
  UNA vez y queda marcada: si algún día vuelves a elegir OpenAI en
  ⚙ Configuración, tu elección se respeta para siempre (la marca sobrevive
  incluso a guardados hechos con una página de Configuración abierta de
  antes).
- 🔤 TU PREGUNTA: **sí — el director elige gpt-image-1 automáticamente** en
  cada escena donde definió texto legible dentro de la imagen (`image_text`),
  sin que toques nada. Está así desde la v0.42.0 y esta versión lo deja como
  camino principal: verás en el log «🔤 N escena(s) con texto legible: el
  director las genera con gpt-image-1». Requiere tu OPENAI_API_KEY (la
  tienes); si faltara, avisa y esas escenas salen con FLUX con énfasis
  tipográfico. Suelen ser 1-5 escenas por video: esos centavos extra aparecen
  en el reporte de gasto como imágenes de OpenAI. Y si gpt-image-1 fallara en
  una escena, esa escena cae a FLUX — el ruteo nunca tumba la fase.

Batería nueva (`tests/test_v0_45_0.py`, 18 comprobaciones) y las 44
anteriores en verde.

## v0.44.0 — 2026-08-09
Blindaje ANTICIPADO para tu primera versión estable, con prioridad en los
videos largos. Esta vez no esperé a que un error apareciera en tu log: recorrí
el pipeline completo preguntando «¿qué es lo SIGUIENTE que va a fallar en una
corrida larga?» y cerré los seis agujeros con más papeletas — más una falsa
alarma que sí salió en tu última corrida.

- 🛡 EL PRÓXIMO 429, DESACTIVADO ANTES DE QUE TE PASE: el límite de OpenAI
  mató tu fase de imágenes (v0.43.1); el de **Anthropic** tiene el mismo
  agujero y un video largo hace ~25 llamadas grandes seguidas (tandas de
  escenas, dirección de arte, visión…). Ahora TODA llamada al modelo
  sobrevive a los errores transitorios del servidor (límite 429, sobrecarga
  529, caídas 5xx, cortes de conexión): espera lo que la API pida —o una
  rampa de 20s/40s/60s, tope 120s—, avisa en el log y reintenta hasta 4
  veces. Los errores REALES (clave inválida, petición mal hecha) suben
  intactos y sin esperas: reintentarlos sería pagar dos veces el mismo fallo.
- 💰 ECONOMÍA DE TOKENS POR PROPÓSITO: el modelo ahora razona A FONDO solo
  donde se nota en pantalla (concepto, guion, diseño de escenas, dirección de
  arte, metadatos) y con esfuerzo MEDIO en las tareas auxiliares (describir
  B-roll, elegir música, pulir la transcripción, control de calidad con
  visión). Menos tokens de razonamiento en ~8 tipos de llamada por video, sin
  tocar la calidad creativa. De paso cacé un fallo LATENTE de la propia
  mejora: el ajuste de esfuerzo podía PISAR el formato JSON estructurado en
  las llamadas que usan ambos (la revisión con visión) — viajan juntos desde
  el principio, así que nunca te ocurrirá.
- 🎙 NARRACIONES LARGAS SIN TECHO DE 25MB: Whisper rechaza archivos de más de
  25MB y una narración de ~25 minutos a 128kbps ya lo supera — justo el
  tamaño de video al que estás llegando. Por encima del umbral se transcribe
  una copia ligera MONO a 48kbps (misma duración → mismos tiempos por
  palabra; la copia se borra sola) — el techo real pasa a ~69 minutos. Si ni
  así cabe, el error te dice qué hacer (dividir la grabación) en vez del 413
  críptico de la API.
- 🎬 UNA TANDA FALLIDA YA NO TUMBA EL STORYBOARD: el diseño de escenas de un
  video largo va en tandas de 40; si UNA fallaba (un 429 agotado, un corte de
  red), moría la fase entera y reanudar re-pagaba las tandas buenas. Ahora
  las escenas de la tanda caída salen con un prompt básico desde su
  narración, queda un aviso con el rango exacto, y el pase de dirección de
  arte —que corre después— las reescribe con la biblia visual: en la práctica
  se recuperan solas.
- ⚡ CONTROL FACTUAL CON VISIÓN EN PARALELO: en un video de 84 escenas son
  ~14 tandas de revisión que en serie añadían 7-14 minutos a la fase de
  imágenes. Ahora corren 2 a la vez (mismo patrón que la generación): la
  espera se reduce a cerca de la mitad sin acercarse a los límites de la API.
- 🔇 LA FALSA ALARMA DE TU ÚLTIMO LOG: «deriva inesperada» en la voz con
  804.77s contra 811.21s. No había deriva: tu grabación tenía 109 pausas
  ajustadas y cada compresión se lleva ~60ms de ruido sub-umbral que el
  detector contaba como voz (109 × 60ms ≈ los 6.4s del aviso) — la
  comprobación DURA de duración total pasó con 2 centésimas. La tolerancia
  ahora escala con las pausas ajustadas (1.2s + 60ms por pausa); la señal
  dura de 0.15s sigue intacta, que es la que de verdad protege el video.

Batería nueva (`tests/test_v0_44_0.py`, 30 comprobaciones) y las 43
anteriores en verde: `probar.bat` las corre todas.

## v0.43.1 — 2026-08-09
Tu corrida de «3-mansa-musa» murió en Imágenes con un error 429 de OpenAI
tras 8 imágenes ya generadas. Tres causas, y una es de dinero:

- 🖼 EL ERROR QUE FRENÓ TODO: gpt-image-1 admite MUY pocas imágenes por
  minuto (5 en tu cuenta) y devolvió «Rate limit reached… Please try again
  in 12s». Ese 429 es **transitorio** —la propia API dice cuántos segundos
  faltan— pero el programa no lo manejaba: el camino de Replicate sí tenía
  reintentos y el de OpenAI no. Ahora espera EXACTAMENTE lo que la API pide
  (12s en tu caso, no un número inventado) y reintenta hasta 5 veces,
  avisándote en el log en vez de dejarte 13 minutos en silencio. Si el
  límite no cede, el mensaje te dice qué hacer y **las imágenes ya generadas
  se conservan**: reanudas con «Rehacer desde Imágenes» sin pagarlas otra
  vez.
- ⚡ LA CAUSA DE FONDO: el programa lanzaba 4 imágenes en paralelo. Contra un
  límite de 5 por minuto, el 429 era inevitable. Ahora con OpenAI baja a 2
  en paralelo (como ya hacía con Replicate) — el ritmo se acerca al límite y
  los reintentos absorben lo que sobre.
- 💰 LA ESTIMACIÓN TE MENTÍA (y con ella el tope de gasto): tu configuración
  tiene proveedor `openai` pero conservaba el `model` de FLUX de una prueba
  anterior. OpenAI ignora ese campo —siempre genera con gpt-image-1— pero la
  estimación sí lo leía, así que calculaba con el precio de FLUX ($0.04-0.05
  por imagen) lo que de verdad cuesta $0.07-0.25. En tu video: **estimó
  $3.32-$4.15 por 83 imágenes cuando el costo real era $5.81-$20.75**, y el
  tope de presupuesto se calculó sobre esa base equivocada. Ahora el precio,
  el tiempo y la etiqueta usan el modelo que se va a usar DE VERDAD
  (verás «gpt-image-1» en el panel, no «flux-1.1-pro»). Replicate sigue
  respetando el modelo que elijas.
- 🔤 Detalle: cuando OpenAI ya es tu proveedor de imágenes, las escenas con
  texto legible reutilizan esa misma conexión en vez de abrir una segunda
  contra el mismo límite.

## v0.43.0 — 2026-08-09
- 🧪 REVISIÓN DE SALUD DEL PROGRAMA, EN TUS MANOS: las 41 baterías de prueba
  que he ido escribiendo con cada versión vivían fuera del programa — en mi
  espacio de trabajo temporal, sin control de versiones, y solo yo las
  corría. Ahora están DENTRO del proyecto (`tests/`) y las puedes ejecutar
  tú: doble clic en **`probar.bat`** (o `./probar.sh` en Linux/Mac).
  · Te dice en claro **TODO EN VERDE** o qué falló, en qué batería y con qué
    valor medido — un resumen que puedes copiarme para diagnosticarlo.
  · **No cuesta un centavo**: sin claves de API ni internet (proveedores
    falsos, audio sintético, ffmpeg local). **No toca tus proyectos**: todo
    ocurre en carpetas temporales.
  · Tarda unos 6 minutos. Úsalo antes de una generación importante o después
    de actualizar — es la forma de saber que el programa está sano ANTES de
    gastar dinero en una corrida.
  · Filtro por si quieres ir rápido: `py tests\probar_todo.py 42` corre solo
    las baterías de la v0.42.x; `--lista` muestra todas sin ejecutarlas.
- 🩺 De paso, arreglé las 2 baterías que llevaban tiempo en rojo. Ninguna era
  un fallo del programa: **eran pruebas caducadas** que verificaban cosas que
  yo mismo cambié después.
  · Una probaba la «calibración de Whisper», una función que retiré a
    propósito en v0.24.0 porque medía ±380 ms de dispersión sobre la MISMA
    grabación; la sustituyó el lazo cerrado de subtítulos que ves funcionando
    en tus logs. Curiosamente, las comprobaciones que SÍ importaban —que los
    subtítulos caigan sobre la voz— pasaban: el test demostraba que quitarla
    fue correcto mientras marcaba rojo por buscar el mecanismo viejo.
  · La otra llamaba a funciones internas con la firma de v0.21 (hoy devuelven
    más datos) y pedía los subtítulos sin el mapa de tiempo que necesitan
    desde v0.25.1. Verifiqué a fondo que no escondían ninguna regresión real.
  · La suite queda **41 de 41 en verde**. Un test que se queda rojo deja de
    mirarse, y así es como un fallo de verdad se escondería.
- 🛡 Una batería creaba su proyecto de prueba en tu carpeta `projects/` real
  (y solo lo borraba si terminaba bien): ahora todas trabajan aisladas.

## v0.42.2 — 2026-08-09
Dos arreglos a partir de tu última corrida (proyecto 2-mansa-musa), uno de
ellos de DINERO:

- 🧠 LA FASE «CONCEPTO» QUE MURIÓ (tu error nuevo): el modelo piensa antes de
  responder, y ese razonamiento CUENTA dentro del mismo límite de tokens que
  la respuesta. Con un brief grande (análisis del video de referencia +
  transcripción de 20 min + imágenes), el razonamiento se comió los 16 000
  tokens del techo y el JSON llegó cortado. Tres capas de arreglo:
  · El techo por defecto sube de 16 000 a 64 000 tokens. **Esto no cuesta
    nada**: el techo es un LÍMITE, no una reserva — la API solo cobra lo que
    el modelo genera de verdad. Quedarse corto era pura pérdida.
  · Si aun así una respuesta se corta, ahora se REINTENTA UNA VEZ sola con
    el techo ampliado (hasta 128 000, el máximo del modelo) y la fase
    continúa, en vez de morir a mitad del proyecto.
  · Subí también los techos apretados de las fases que revisan tu narración
    (4 000 y 8 000 tokens): con un audio de 20 minutos eran igual de
    vulnerables al mismo corte.
- 💸 GASTO INVISIBLE — el que explica «sigo perdiendo tokens»: cuando una
  llamada se cortaba o el modelo la rechazaba, el programa lanzaba el error
  ANTES de anotar el gasto. Esos tokens ya estaban COBRADOS por la API (en
  tu corrida, una respuesta cortada de 16 000 tokens de salida de Opus ≈
  $0.55) y no aparecían en el reporte de la corrida. Ahora el gasto se anota
  SIEMPRE, pase lo que pase: primero se registra, después se decide qué
  hacer con el error. Lo mismo aplica al rechazo del pulido de transcripción
  que viste en la corrida anterior.
- Además, si una respuesta se corta te avisa en el log con el reintento
  («↻ La respuesta se cortó… se reintenta con N»), para que veas el motivo
  en vez de un error críptico.

## v0.42.1 — 2026-08-08
Arreglos a partir del log real de tus 2 últimas corridas (test-1-mansa-musa
y 2-mansa-musa) — cinco causas raíz encontradas y corregidas:

- ✂ ENUMERACIONES CORTADAS POR ERROR (lo más grave: 12.7 s quitados de tu
  narración de Mansa Musa): el detector de falsos arranques cortó «ni en
  América Latina,» y «ni en Europa,» de una enumeración («no en Estados
  Unidos, ni en América Latina, ni en Europa…»), «tuvo la visión, tuvo la
  generosidad,» de una anáfora, y «luego las rutas comerciales,» — porque
  le bastaba que el siguiente tramo repitiera 2 palabras del arranque («ni
  en», «tuvo la») tras una pausa. Regla nueva en AMBOS detectores de redos:
  la coincidencia debe cubrir el intento COMPLETO (todo lo que dijiste se
  vuelve a decir) — ese es el patrón de un redo real; la coincidencia
  parcial de arranque es el patrón de las enumeraciones y anáforas, y ya
  NUNCA corta. Además, un redo que corrige/extiende la frase exige ahora
  una pausa larga (≥1.2 s, como los 2 s de tu caso del «registro
  veterinario») para no tocar el eco retórico de extensión («Nadie lo
  sabía. Nadie lo sabía hasta hoy.»). Verificado con tus 4 casos del log:
  ninguno se corta ya; los redos reales sí.
- 📖 LA CORRIDA GRANDE QUE NO TERMINÓ («Unterminated string» en la fase de
  escenas): tu video de ~20 min genera tantas escenas que la respuesta del
  modelo YA NO CABE en una sola llamada — el JSON llegaba cortado por el
  límite de tokens y la fase moría con ese error críptico. Ahora el diseño
  de escenas y el pase de dirección de arte trabajan POR TANDAS de 40
  escenas cuando el video es largo (la biblia visual se define primero con
  el storyboard entero; cada tanda la recibe junto con el índice completo
  para no perder la visión de conjunto). Y si aun así una respuesta se
  cortara, el error ahora lo dice claro («la petición debe partirse en
  tandas») en vez del críptico «Unterminated string».
- 👁 EL 400 DEL CONTROL FACTUAL («image/jpeg… appears to be image/png»):
  algunos generadores devuelven PNG aunque se les pida .jpg, y la API de
  visión rechaza la imagen cuyo tipo declarado no coincide. El tipo se
  detecta ahora por los BYTES reales del archivo (PNG/JPEG/WebP/GIF), no
  por la extensión — afecta a todo el programa (control factual, revisión
  de tu B-roll, análisis de referencias).
- 🤥 AVISO ENGAÑOSO: tras fallar esa llamada, el programa decía «todas las
  imágenes respetan lo narrado» — sin veredictos no se puede afirmar nada.
  Ahora, si la revisión con visión falla, solo avisa del fallo y no
  presume de un control que no ocurrió.
- 🙅 PULIDO DE TRANSCRIPCIÓN RECHAZADO (stop_reason=refusal en
  2-mansa-musa): el prompt ahora deja claro que el texto es la
  transcripción Whisper de TU PROPIA grabación y que el creador pide
  revisar su calidad — el encuadre anterior podía leerse como una petición
  de transcribir contenido ajeno. (Si aún así el modelo se rehúsa, el
  programa sigue avisando y usa la transcripción tal cual: nada se rompe.)

## v0.42.0 — 2026-08-07
Debug general a partir de tu video «2-chupacabras» (59 escenas, ~15 min):
siete frentes, cada uno con su causa raíz encontrada en el log y verificado
con pruebas de código real.

- ✂ EL «GAGEO» EN «EL TEJIDO» (tu reporte de voz, causa raíz encontrada en
  el log): el corrector de v0.40.0 quitó «es decir,» de «…sección térmica;
  es decir, el tejido fue sellado…» tratándolo como "muletilla aislada" — y
  el empalme cayó justo sobre el arranque de «el», por eso suena a
  tartamudeo. Tres arreglos de fondo:
  · Los CONECTORES DISCURSIVOS («es decir», «o sea») salieron para siempre
    de la lista de muletillas: enlazan ideas y llevan pausa natural
    alrededor — nunca más se cortan por regla. Las palabras-relleno
    («bueno», «este») tampoco se cortan ya cuando vienen tras puntuación
    («Bueno, sigamos» abre frase legítimamente).
  · GUARDAS DE EMPALME en TODOS los cortes: el corte ya no termina en el
    inicio nominal de la palabra siguiente (Whisper trae ±100 ms de error y
    se comía su ataque — el gageo), sino dentro de la pausa, dejando margen
    de 100-350 ms antes de la palabra que se conserva.
  · La revisión IA ahora solo corta con seguridad ALTA y con el tropiezo y
    su reintento CONTIGUOS: el corte de [215.6s] («…monos masivos», una
    recapitulación a ~70 s de la frase original) ya no habría pasado.
- ✂ EL ERROR QUE SÍ SE QUEDÓ (tu reporte: «se repite la frase en la que el
  narrador se equivocó»): el detector de falsos arranques exigía que el
  intento quedara TRUNCADO — pero si Whisper le puso punto al intento («El
  registró veterinario.»), la protección anti-anáfora lo dejaba pasar
  entero. Detector nuevo de FRASE REINICIADA: si tras una pausa real
  repites el arranque de la frase anterior (≥4 palabras y el reintento la
  continúa, o la frase completa ≥3 palabras tras una pausa clara), se corta
  el primer intento y se queda tu reintento. Las anáforas retóricas y los
  ecos cortos de énfasis siguen protegidos (verificado en pruebas).
- 📝 SUBTÍTULOS «monos masivos» (dijiste «monos macacos rhesus»): doble
  arreglo. (1) Si aportas guion o texto, un extracto se pasa a Whisper como
  sesgo de vocabulario (transcribe los términos raros de TU material en vez
  del parecido frecuente). (2) PULIDO POR CONTEXTO tras transcribir: la IA
  detecta las malas transcripciones evidentes (fonéticamente similares y
  sin sentido en contexto) y corrige texto y subtítulos — solo con
  seguridad alta, avisándote de cada corrección, sin tocar jamás tu audio.
  Desactivable: audio.polish_transcript.
- 🖼 ESCENAS «VACÍAS» (7 y 23, rechazadas por el filtro del generador): la
  escalera de respaldo tiene dos peldaños nuevos antes del degradado. Si el
  prompt suavizado también es rechazado, se genera un PLANO ATMOSFÉRICO
  REAL del mismo mundo visual (sin los sujetos conflictivos — cuesta una
  imagen más, pero la escena queda con una imagen de verdad); y si hasta
  eso falla, se usa la escena VECINA desenfocada y oscurecida (sin costo)
  en vez del degradado plano que se veía «vacío». Avisos diferenciados
  para que sepas exactamente qué quedó en cada escena.
- 🔤 TEXTO ILEGIBLE Y EN INGLÉS EN LAS IMÁGENES (scene_010) — tu propuesta
  de ELECCIÓN DINÁMICA DE MODELO, implementada: el director marca por
  escena (image_text) cuándo un texto DEBE leerse (un titular, un letrero;
  máx. 2-3 por video) y ESAS imágenes se rutean a gpt-image-1 (la mejor
  tipografía) si tienes clave de OpenAI, con el texto EXACTO y EN EL IDIOMA
  DEL GUION — nunca más letras inventadas en inglés. Sin clave de OpenAI se
  usa el modelo estándar con énfasis tipográfico y se te avisa. En el resto
  de escenas la regla es la contraria y ahora explícita: prensa/documentos
  de atrezo se describen "out of focus, unreadable print".
- 👁 FIDELIDAD FACTUAL CON VISIÓN (ovejas vivas en 012/021, «3 orificios en
  triángulo en el cuello» convertidos en 4 en cuadrado en la 003): las
  reglas de prompt de v0.41.0 no bastan — el GENERADOR falla contando y con
  anatomías. Ahora hay CONTROL DE CALIDAD con visión: el director compara
  cada imagen generada con los hechos de su narración (estado, especie,
  cantidad, disposición, ubicación de heridas) y REGENERA UNA VEZ las que
  los contradicen, con el prompt corregido de forma redundante («exactly
  three, no more…»). Cost-aware: un solo reintento, firma de caché
  actualizada (reanudar no re-cobra), desactivable
  (providers.images.fact_check), y si tras regenerar sigue mal te lo dice
  honesto para que lo revises en el Storyboard. Además, regla nueva de
  CANTIDAD Y GEOMETRÍA EXACTAS en los prompts (el número repetido y la
  disposición descrita).
- 🎼 MÚSICA PLANA con 24 pistas en la biblioteca: el video entero usaba UNA
  pista en loop. Ahora, con biblioteca local y video de más de 3 minutos,
  la banda sonora se arma por ACTOS siguiendo el arco de intensidad que ya
  dibuja el director (calma/desarrollo/clímax): el supervisor musical elige
  una pista POR ACTO (con variedad, A-B-A permitido) y se funden con
  crossfade de 3 s. Verificado con ffmpeg real y análisis espectral: el
  clímax suena con otra pista. Desactivable: providers.music.multi_track.

## v0.41.0 — 2026-08-06
- 🎯 FIDELIDAD FACTUAL EN LOS PROMPTS DE B-ROLL (tu caso real del
  «Chupacabras»): detecté exactamente el problema en tus dos escenas —
  scene_002 mostraba animales VIVOS cuando la narración decía «hallados sin
  vida», y scene_003 tenía las heridas correctas pero en un cuerpo HUMANO
  (la narración hablaba de animales) y en el PECHO (la narración decía
  CUELLO). La instrucción anterior («que la imagen corresponda a lo que se
  dice») era demasiado genérica. Ahora hay una regla explícita — FIDELIDAD
  FACTUAL AL GUION — en las tres rutas que generan o reescriben tus
  broll_prompt (guion nuevo, narración propia, y el pase de dirección de
  arte que tiene la última palabra): el ESTADO (con/sin vida) debe quedar
  explícito en inglés ("dead", "lifeless", "carcass"), la ESPECIE del sujeto
  es obligatoria en cada mención de un cuerpo o herida cuando es un animal
  (para que el generador no dibuje anatomía humana por defecto), y la
  UBICACIÓN exacta que da la narración (cuello, pecho…) va tal cual, nunca
  una zona genérica. Ante la duda, manda la fidelidad sobre lo "artístico".
- 🎨 BRANDING DE RÓTULOS por canal/estilo (tu segundo pedido): cada estilo
  guardado en 📺 Canales y estilos puede fijar ahora su propia tipografía y
  colores de rótulo — 4 familias (Moderna/sans, Editorial/serif,
  Impacto/display, Mono/datos) más color de acento y de texto libres, con 4
  presets de un clic (Documental clásico, Impacto viral, Tech/datos,
  Minimalista) para no tener que ajustar hex a mano. Se aplica a TODOS los
  rótulos — dato, lista, conclusión y el gancho de apertura de los cortos.
  Sin estilo, o con un estilo que no personalice esto, el video sale
  IDÉNTICO a como salía antes (incluida tu propia personalización global de
  color, que un estilo sin colores propios nunca pisa). Verificado con
  render ffmpeg real: el color medido por píxeles cambia con el branding y
  vuelve al de siempre sin él.

## v0.40.0 — 2026-08-05
- ✂ CORRECTOR DE TROPIEZOS EN TU NARRACIÓN (lo que pediste, con tu caso
  real): hasta ahora tu grabación era verdad absoluta — si arrancabas mal y
  volvías a empezar, ese falso arranque terminaba en el video Y en los
  subtítulos. Ahora el programa detecta los errores EVIDENTES, **corta el
  audio de verdad** (no solo el texto: si no, la voz seguiría diciéndolo),
  reajusta todos los tiempos y te avisa de CADA corrección con lo que quitó
  y por qué. Detecta:
  · FALSOS ARRANQUES — tu caso exacto: «El registró veterinario» …2s…
    «El registro veterinario oficial es la evidencia…» → se queda solo con
    el reintento. Exige tres evidencias a la vez: que el reintento repita el
    arranque, que haya una pausa real y que el intento quedara truncado.
  · PALABRAS REPETIDAS sin intención («el el registro»).
  · MULETILLAS AISLADAS entre pausas («eh», «o sea», «este»).
  · CORRECCIONES QUE ANUNCIAS («voy de nuevo», «corrijo», «otra vez»,
    «perdón»): se borra el aviso Y el intento anterior.
  · Y una REVISIÓN CON IA opcional que caza los tropiezos reformulados con
    otras palabras, que ninguna regla puede ver (unos centavos por video;
    desactivable con audio.fix_narration_ai).
- REGLA DE ORO: ante la duda NO se corta. Borrar contenido legítimo tuyo es
  mucho peor que dejar pasar un tropiezo, así que cada detector exige varias
  señales convergentes. Verificado con pruebas que confirman que NO se tocan:
  anáforas retóricas («El registro dice esto… El registro dice aquello»),
  muletillas dentro de una frase fluida («compré este libro»), enumeraciones,
  pausas dramáticas y coincidencias casuales de palabras cortas.
- Todo desactivable con `audio.fix_narration: false` si prefieres tu
  grabación intacta. Si algo falla, la narración se usa tal cual la grabaste.

## v0.39.0 — 2026-08-05
- 🖥 REDISEÑO DE LA EXPERIENCIA para redes sociales (etapa final del plan):
  · «¿PARA DÓNDE ES ESTE VIDEO?» es ahora la PRIMERA decisión al crear:
    tarjetas con ícono por plataforma (YouTube largo, Short, Reel, TikTok,
    Ads 1:1 y 4:5) en vez de un desplegable escondido.
  · PREVIEW CON EL ASPECTO REAL en todas partes: las miniaturas del
    Storyboard y el Editor se muestran en la proporción verdadera del
    proyecto (un Reel se ve vertical, un Ad cuadrado — ya no todo como
    16:9), y el VIDEO FINAL vertical se reproduce en un marco de teléfono
    centrado. El aspecto sale del config real del proyecto, servido por la
    API (proyectos antiguos siguen mostrándose 16:9 sin tocar nada).
  · El encabezado del proyecto muestra la PLATAFORMA y la PLANTILLA
    elegidas como insignias — de un vistazo sabes qué estás produciendo.
  · PIPELINE COMPACTO para cortos: las fases casi instantáneas (análisis,
    concepto, música, subtítulos, publicación) se atenúan en chips mini y
    el foco visual queda en Guion → Escenas → Voz → Imágenes → Montaje —
    las que de verdad pesan en un corto (se re-iluminan si corren o fallan).

## v0.38.0 — 2026-08-05
- 🎬 PLANTILLAS DE FORMATO COMPLETO para cortos (la cuarta etapa del plan):
  al crear un Short/Reel/TikTok/Ad eliges la receta del video en UN clic y
  toda la cadena se alinea — estructura del guion, rótulos, stickers,
  pantalla dividida, efectos de sonido y arco musical:
  · 🏆 TOP 3 / RANKING: cuenta regresiva de ítems con el mejor al final,
    rótulos «TOP 3→1», música que sube hasta el clímax, encuesta al cierre.
  · 🎭 HISTORIA CON GIRO: in media res, giro al 70% con boom y pausa
    dramática antes, remate de una línea.
  · 🔁 ANTES/DESPUÉS: transformación con la comparación clave en PANTALLA
    DIVIDIDA (mismo encuadre en ambas mitades para que el contraste cante).
  · ❌✅ MITO VS REALIDAD: el mito como gancho, hechos que lo desmontan,
    rótulos «MITO»/«REALIDAD».
  · ⚡ TUTORIAL EN PASOS: resultado prometido + pasos imperativos con
    rótulos «PASO 1…N» y cierre «guárdalo».
  · 🤯 DATO IMPACTANTE: la cifra primero, contexto y remate.
  · ✨ LIBRE (por defecto): el director decide, como hasta ahora.
  La plantilla guía al guionista (junto con los 970 hooks), al storyboard y
  al pase de dirección de arte. Si traes TU guion, la plantilla solo lo
  ordena, no lo reescribe. Los videos largos 16:9 no cambian en nada.

## v0.37.0 — 2026-08-05
- 📊 STICKERS DE ASPECTO NATIVO para formatos cortos (imitaciones visuales,
  como acordamos — un MP4 no puede ser clicable; la interactividad real la
  añade la app al publicar, y aquí la respuesta se dirige a comentarios):
  · ENCUESTA: tarjeta blanca con la pregunta y dos opciones en pastilla con
    los acentos de Instagram — cuando la narración plantea una disyuntiva.
  · PREGUNTA: tarjeta con campo de respuesta y pista «Responde en
    comentarios…» — cuando se pide opinión abierta.
  · CUENTA REGRESIVA: tarjeta oscura con un número que CUENTA DE VERDAD
    (segundos reales hacia la revelación) — para crear anticipación.
  El director decide cuál y cuándo (máximo UNO por video: más de un sticker
  deja de parecer nativo), entra deslizándose con fundido tras el gancho y
  se despide antes del corte; no lo zoomean las rupturas de patrón (los
  stickers de la app viven por encima del contenido). Visible en el
  storyboard para revisarlo en el punto de control. Solo formatos cortos;
  dibujado con PIL + ffmpeg en local: costo $0.

## v0.36.0 — 2026-08-05
- 🎭 VIDEOS DE REACCIÓN (nueva categoría de archivo «Tu video de reacción»):
  grábate reaccionando al contenido y súbelo — el programa te compone SOBRE
  el video todo el tiempo, con cada escena tomando exactamente SU tramo de
  tu grabación (sincronizado con la línea de tiempo). Si te grabaste sobre
  PANTALLA VERDE, se detecta sola (muestreo del fotograma) y se recorta con
  chroma key + limpieza de reborde, compuesto en la franja inferior; si no
  hay pantalla verde, apareces en una BURBUJA CIRCULAR estilo TikTok en la
  esquina. Sin configurar nada.
- 🫧 PERSONAJE EN BURBUJA (segunda fuente de reacción, como pediste): nueva
  opción al crear el proyecto — en vez de ocupar la pantalla completa, el
  personaje IA con lipsync aparece en una burbuja circular sobre el B-roll
  de sus escenas (estilo reacción). La escena conserva su imagen de fondo;
  si el lipsync falla, sale solo el B-roll con un aviso (nunca se rompe).
- ◫ PANTALLA DIVIDIDA para comparaciones (antes/después, esto vs aquello):
  el director puede marcar escenas de formato corto como «dividida» con un
  SEGUNDO prompt — se generan las dos imágenes y el montaje las compone a la
  vez (arriba/abajo en vertical, izquierda/derecha en horizontal) con
  Ken Burns propio por mitad y línea divisoria. Máximo 1-2 por video, solo
  cuando la narración de verdad compara. Visible en el storyboard.
- Toda la composición es ffmpeg local (costo $0); lo único que paga es la
  segunda imagen de las escenas divididas (una imagen IA más) y el lipsync
  del personaje que ya pagabas. Verificado con renders reales medidos por
  píxeles: el chroma elimina el verde y conserva a la persona, la burbuja
  es circular, las mitades muestran cada una su imagen y el tramo de
  reacción coincide con el tiempo real de cada escena.

## v0.35.0 — 2026-08-05
- ✨ MOTOR DE TEXTO Y HOOKS VISUALES para formatos cortos (lo que elegiste
  construir primero — todo ffmpeg local, costo $0 por uso):
  · GANCHO VISUAL DE APERTURA: la escena 1 de todo Short/Reel/TikTok/Ad abre
    con el gancho en TEXTO GRANDE estilo TikTok — bloque centrado de líneas
    cortas, entrada inmediata con golpe de escala (nada de fundidos lentos:
    el espectador decide en 2 segundos), la palabra clave en el color de
    acento, y salida rápida cuando la narración avanza. El director lo
    redacta (≤8 palabras con gancho real); si no, un respaldo automático
    condensa el arranque de la narración — un corto JAMÁS abre sin texto.
  · RUPTURAS DE PATRÓN en los cortes: golpe de zoom que asienta (1.10x →
    1.0 en 0.25 s) en cortes secos alternados y destello blanco en los
    golpes dramáticos (sfx boom) — el lenguaje de edición nativo de TikTok/
    Reels, dosificado para no cansar (nunca en la escena 1 ni en fundidos).
    Solo en formatos cortos: los documentales 16:9 no cambian en nada.
  · RÓTULOS MÁS FRECUENTES en cortos (hasta 1 de cada 2 escenas): mucha
    gente ve sin sonido; el texto sostiene la historia.
- 🟦 FORMATOS META ADS: nuevos formatos de proyecto «cuadrado 1:1 (feed)» y
  «retrato 4:5 (feed IG)» además del 9:16 — con subtítulos quemados y ritmo
  corto. Y un arreglo de fondo: el generador de imágenes ahora recibe la
  relación de aspecto REAL del proyecto (antes un proyecto 1:1 pedía
  imágenes 16:9 y todo salía del recorte); el video IA pide la más cercana
  que su modelo soporte (Kling no genera 4:5 → pide 1:1 y el montaje ajusta).

## v0.34.0 — 2026-08-05
- 🪝 BIBLIOTECA DE 970 GANCHOS VIRALES (primer paso del giro a redes
  sociales): tu documento «1000 HOOKS VIRALES» quedó convertido en una
  biblioteca estructurada del programa (assets/hooks/hooks_virales.json,
  970 plantillas con su ejemplo, verificadas una a una en el parseo). Al
  escribir el guion de un video VERTICAL (Short/Reel/TikTok), el guionista
  ya no recibe la orden abstracta de «gancho demoledor»: recibe ~20
  plantillas PROBADAS seleccionadas por afinidad con el tema (un video de
  finanzas recibe ganchos de dinero) más variedad aleatoria reproducible
  por proyecto, y abre el video adaptando la que mejor encaje. Los videos
  largos (16:9) no cambian en nada; con narración propia grabada tampoco
  (tu voz manda). Si la biblioteca faltara, el guion funciona como siempre.

## v0.33.0 — 2026-08-04
- 🛡 TOPE DE GASTO DINÁMICO (adiós al número fijo que estorbaba): un tope de
  $8 no puede servir a la vez para una prueba de 3 escenas y para un
  documental de 15 minutos — es enorme para la primera y demasiado pequeño
  para el segundo, que legítimamente cuesta ~$40 y quedaba interrumpido sin
  motivo. Ahora el tope se calcula solo, a partir de la estimación que el
  programa ya hacía: **tope = costo ALTO estimado de lo que FALTA por
  generar × un margen (1.4 por defecto)**, con un piso mínimo. Resultado con
  tus propios casos: la prueba corta que te costó $11.85 queda con un tope de
  **~$4.34** (el sangrado se habría cortado al PRIMER cobro fallido en vez de
  al quinto), y el documental de 15 min con personaje al 30% queda con
  **~$73** — muy por encima de su costo real, así que no te interrumpe nada.
- El tope se RECALCULA antes de cada fase: al arrancar solo se conoce el
  pronóstico de la configuración, pero después de «Escenas» ya se sabe el
  número EXACTO de escenas, cuáles son video y cuántos segundos de personaje
  hay — justo lo que se va a pagar en la fase siguiente. Y se calcula sobre
  lo PENDIENTE, así que reanudar un proyecto a medias no infla el tope con lo
  que ya está generado (y que no se vuelve a cobrar).
- `budget.max_usd` pasa a ser un techo ABSOLUTO opcional (por defecto 0 = sin
  techo manual). Si lo pones, manda solo cuando sea MÁS restrictivo que el
  automático: es un candado extra, nunca un permiso para gastar más.
- 📋 PUNTO DE CONTROL AL TERMINAR EL STORYBOARD: al completarse la fase de
  «Escenas» el registro muestra un bloque destacado con el nº de escenas y
  duración, dónde revisarlo (04_scenes/storyboard.md: biblia visual, prompt
  de cada escena, riesgo de movimiento, reparto de personaje), el desglose
  de lo que falta por PAGAR partida por partida y el tope activo. Es el
  último momento en que corregir es gratis: de las 11 fases, 10 cuestan
  centavos o son locales, y solo la de Imágenes concentra casi todo el gasto.

## v0.32.0 — 2026-08-04
- 💰 CERO PÉRDIDA DE SALDO: LIBRO DE PREDICCIONES PAGADAS. Encontré la causa
  exacta de tus ~$14 perdidos. En Replicate el dinero se cobra cuando la
  generación TERMINA BIEN EN SU SERVIDOR, no cuando el archivo llega a tu
  disco; entre esos dos momentos hay una descarga que puede fallar — y falló.
  Tu panel lo confirma: 5 predicciones de omni-human **exitosas y cobradas a
  $2.37 cada una ($11.85)** de las que no recibiste ni un archivo. El
  programa descartaba el resultado sin guardar el id ni la URL, así que ese
  dinero era **irrecuperable**, y como el gasto se anotaba DESPUÉS de
  descargar, tampoco aparecía en el reporte: **invisible**. Ahora cada
  generación queda anotada en un libro en disco en el instante en que el
  dinero entra en riesgo (creada → terminada con su URL → descargada), y
  antes de encargar NADA el programa mira ese libro:
  · si ya pagaste un resultado y no se descargó, lo **re-descarga sin volver
    a cobrar**;
  · si una generación sigue corriendo en el servidor, **se reengancha** en
    vez de duplicarla;
  · si la conexión se cortó justo al lanzarla y el servidor sí la aceptó,
    **adopta esa predicción huérfana** en vez de pagar otra igual.
- 💸 EL GASTO YA NUNCA ES INVISIBLE: se registra en el momento en que la
  predicción termina bien, aunque después falle la descarga. Al terminar
  cada generación, si quedó algo pagado y no entregado, verás un aviso con
  el importe y el detalle, y bastará pulsar «Generar video» **dentro de la
  hora siguiente** para recuperarlo sin coste (pasado ese plazo Replicate
  borra el resultado y ya no hay nada que rescatar).
- 🛑 TOPE DE PRESUPUESTO POR GENERACIÓN (⚙ Configuración → budget.max_usd,
  por defecto **$8**): antes de cada llamada que cuesta dinero se comprueba
  que no se pase del tope; si se pasaría, la generación se DETIENE con un
  aviso que dice cuánto llevas gastado, cuánto costaba el siguiente paso y
  cuál es el límite — en vez de seguir vaciando el saldo. Lo ya generado se
  reanuda después sin volver a cobrarse. Súbelo o ponlo en 0 (sin tope)
  cuando quieras una tirada larga.
- Nota sobre tu caso: los $11.85 de esas 5 predicciones ya no se pueden
  recuperar (sus URLs caducaron hace días), pero SÍ puedes reclamarlos a
  soporte de Replicate mostrando que se cobraron sin entrega. De aquí en
  adelante, un fallo de red como el tuyo cuesta $0: se re-descarga lo pagado.

## v0.31.0 — 2026-07-29
- 🎨 PASE DE DIRECCIÓN DE ARTE GLOBAL (lo que pediste: coherencia a nivel de
  TODO el guion, no solo por escena): tras diseñar el storyboard, un segundo
  pase lee el video COMPLETO y crea la «biblia visual» de la producción —
  época y lugar, paleta, luz, lenguaje de cámara, textura/acabado y 2-4
  motivos visuales recurrentes que unen el video. Con esa biblia REESCRIBE
  cada prompt de B-roll con nivel de detalle profesional (sujeto y acción +
  encuadre + luz y atmósfera + textura) y coherencia total entre escenas:
  los personajes, lugares y objetos que se repiten se describen IGUAL en
  todas sus apariciones. La biblia queda visible al inicio del storyboard.
- 🎛 RÓTULOS, TRANSICIONES, SFX, CORTES Y MÚSICA COMO SISTEMA: el mismo pase
  revisa el conjunto — un solo clímax musical con arco gradual, rótulos con
  estilo unificado y sin datos repetidos, fundidos solo en fronteras de
  sección o momentos dramáticos, efectos de sonido sin fatiga y variedad de
  ritmo — y ajusta los campos de cada escena en consecuencia.
- 🎥 AUDITORÍA DE MOVIMIENTO EN VIDEO IA (tu segundo tema): los modelos de
  video fallan con movimientos complejos (personas caminando, manos, caras
  hablando, multitudes, acción rápida). El pase clasifica el riesgo de cada
  escena (baja/media/alta, visible en el storyboard) y en las escenas de
  VIDEO con riesgo alto reescribe el prompt para que el movimiento lo pongan
  la CÁMARA (dolly lento, paneo, parallax) y la ATMÓSFERA (polvo, humo,
  lluvia, telas al viento, cambios de luz) con los sujetos casi estáticos en
  pose potente — cinematográfico y sin artefactos. De tus dos opciones
  (auditar los clips generados con visión IA vs. reforzar los prompts) se
  implementó la segunda: previene el defecto ANTES de pagar el clip; la
  auditoría visual posterior puede añadirse encima si hiciera falta.
- El pase es UNA llamada extra al modelo por generación (se reporta en el
  gasto como «direction»). Si falla, el video no se detiene: se conservan
  las decisiones escena a escena del primer pase y queda un aviso. En modo
  preview (sin clave) se omite.

## v0.30.0 — 2026-07-25
- POR QUÉ TARDÓ TANTO Y POR QUÉ EL PERSONAJE SALIÓ COMO FOTO GIGANTE (debug
  completo de tu corrida test-2-hetty): el lipsync volvió a caer con el corte
  de red (WinError 10054) — la conexión de tu equipo hacia Replicate se corta
  sobre todo en las operaciones LARGAS (el 25-07 falló el lipsync 3 de 3
  veces y Kling e imágenes de forma intermitente; el 18/19-07 todo pasaba,
  así que apunta a tu red/VPN/antivirus de ese día, no al programa). Al
  fallar, el programa usó su reserva DISEÑADA: la escena del personaje pasa a
  su foto fija — por eso viste tu imagen de referencia en pantalla; no es que
  el director la eligiera como B-roll.
- ARREGLADO EL RE-COBRO Y LA ESPERA ETERNA EN LOS REINTENTOS: cuando el
  corte llegaba a MITAD de la espera del resultado, el reintento RE-CREABA
  la predicción — o sea, volvía a pagar el modelo completo y a esperar sus
  minutos (así se fueron ~12 min de lipsync). Ahora la reconexión RETOMA la
  misma predicción (la generación sigue en el servidor y no se cobra de
  nuevo), y si la red no vuelve, el error final lo dice claro. Además el
  lipsync y los clips de video, que tienen reserva por escena, caen rápido
  (3 intentos) en vez de retener la fase; las imágenes —que sí detienen la
  fase— insisten más (6). Revisa tu consumo en replicate.com/account: los
  reintentos de omni-human de esa corrida pudieron cobrarse varias veces.
- ARREGLADO un bug de la v0.29.3: al reintentar una llamada con ARCHIVOS
  (foto del personaje, audio, fotograma inicial de Kling), el reintento los
  subía VACÍOS (ya se habían leído en el intento anterior) — de ahí el error
  críptico «'NoneType' object has no attribute 'read'» de tus 2 clips Kling.
  Ahora los archivos se rebobinan antes de cada intento.
- AVISOS DE REINTENTO VISIBLES: los mensajes «reintentando en Xs…» de la
  generación en paralelo se quedaban en la consola y no llegaban al registro
  de la interfaz — la fase parecía colgada sin explicación. Ahora se ven.
- 🖼 ENCUADRE INTELIGENTE DEL PERSONAJE (lo que pediste): si el lipsync cae a
  la foto fija y tu foto tiene una relación de aspecto muy distinta a la del
  video (retrato o cuadrada sobre 16:9), el director ya no recorta a ciegas
  (te cortaba la cara): 1º intenta REGENERARLA con el modelo de identidad
  usando tu foto como referencia, ya en el formato del video; si no puede
  (sin clave, modelo caído, red), la compone ENTERA sobre su propio fondo
  ampliado y desenfocado (estándar televisivo) — la cara completa siempre
  visible. Esto aplica también a cualquier imagen fija con aspecto muy
  distinto (p. ej. B-roll tuyo en vertical); con desajustes leves (4:3) se
  mantiene el recorte cinematográfico de siempre. Verificado con render real:
  un sujeto en el tercio superior de un retrato 9:16 —que antes quedaba fuera
  de cuadro— ahora aparece entero, sin deformar y con fondo desenfocado.

## v0.29.3 — 2026-07-25
- REINTENTO ANTE CORTES DE RED PASAJEROS (antes detenían la fase entera):
  en tu segunda prueba, la fase de Imágenes falló por completo con
  «[WinError 10054] Se ha forzado la interrupción de una conexión existente
  por el host remoto» — un corte de conexión de Windows, casi siempre
  transitorio (Wi-Fi/VPN inestable un instante). `replicate_call()` solo
  reintentaba ante el límite de velocidad (429); cualquier otro error,
  incluido este corte pasajero, se propagaba de inmediato y detenía TODA la
  fase, exigiendo pulsar «Generar video» de nuevo a mano. Además, la
  descarga del resultado ya generado (`urlretrieve`, usada por imágenes,
  video IA, lipsync y música) no tenía ningún reintento — un corte justo ahí
  tiraba trabajo ya pagado y completado. Ahora ambos puntos reintentan con
  espera creciente (hasta 5 veces) ante cortes de red reconocidos
  (`ConnectionError`/`TimeoutError`, WinError 10054/10053/10060, «connection
  reset», «forcibly closed», etc.) antes de rendirse — y si el corte
  persiste, el aviso final es claro y accionable en vez de un traceback. Los
  errores REALES (token inválido, modelo no encontrado, sin saldo, contenido
  sensible) se detectan y detienen la fase igual que antes, sin reintentar
  algo que no se va a resolver solo. Verificado con un servidor HTTP local
  real que corta la conexión a medio camino y con un cliente Replicate falso
  que lanza las excepciones reales de red, ambos ejercitando el código de
  reintento tal cual corre en producción.

## v0.29.2 — 2026-07-25
- ARREGLADO EL ESTIRAMIENTO DE IMÁGENES EN ESCENAS CON KEN BURNS (caras y
  fotos deformadas horizontalmente): si subías la foto de referencia de un
  personaje o un B-roll con una relación de aspecto DISTINTA a 16:9 (por
  ejemplo cuadrada o vertical), el efecto Ken Burns las escalaba conservando
  su aspecto ORIGINAL y luego las ajustaba al tamaño de salida — como el
  recorte no coincidía en proporción, el ajuste final ESTIRABA la imagen de
  forma no uniforme. El camino de video (B-roll en video) ya recortaba
  primero para cubrir el encuadre de salida y luego animaba; al camino de
  imagen fija (Ken Burns) le faltaba ese mismo recorte de cobertura. Ahora
  toda imagen se recorta primero para llenar exactamente el encuadre de
  salida (sin deformar) y DESPUÉS se aplica el zoom/paneo — confirmado con
  una prueba geométrica real (círculo de referencia que debe seguir siendo
  círculo, no elipse, tras el filtro) sobre fuente cuadrada, vertical y ya
  16:9, en las 5 animaciones.
- MODELO DE LIPSYNC POR DEFECTO MÁS FIABLE: el modelo económico por
  defecto («zsxkib/sonic») dejó de encontrarse en Replicate («no
  encontrado»/404) — es un modelo de un autor independiente que puede
  cambiar de nombre o retirarse sin aviso. El nuevo económico por defecto es
  «cjwbw/sadtalker» (evidencia sólida de que sigue activo). Sonic queda en
  el catálogo como alternativa con aviso explícito de que puede fallar así,
  y para qué modelo probar en ese caso. AVISO IMPORTANTE: no tengo acceso de
  red desde este entorno para verificar en vivo la disponibilidad actual de
  modelos en Replicate (el proxy de salida bloquea api.replicate.com por
  política) — este cambio reduce el riesgo con la mejor evidencia
  disponible, pero no es una garantía. Si «cjwbw/sadtalker» también fallara,
  prueba «bytedance/omni-human» (confirmado, aunque más caro) o revisa
  replicate.com/collections/lipsync para ver qué modelos siguen activos hoy.

## v0.29.1 — 2026-07-23
- ARREGLADO EL FALLO EN LA FASE DE METADATOS («For 'array' type, 'minItems'
  values other than 0 or 1 are not supported»): en v0.27.0, al añadir las 3
  opciones de título/descripción/miniatura, exigí «exactamente 3» dentro del
  esquema técnico con «minItems: 3». La API de Anthropic no admite ese
  valor y rechazaba la petición entera — justo en la ÚLTIMA fase, después de
  haber pagado ya todo lo anterior. Ahora el «exactamente 3» se pide en el
  prompt y lo garantiza el código (si el modelo devuelve 5 se recortan, si
  devuelve 1 se completan), sin esquema inválido. Las 3 opciones de todo
  siguen igual.
- POR QUÉ NO LO DETECTARON LAS PRUEBAS (y por qué no volverá a pasar): las
  pruebas locales usan un modelo simulado que aceptaba cualquier esquema, así
  que el error solo aparecía con la API real. Ahora hay un VALIDADOR de
  esquemas que corre tanto en la API real (falla claro ANTES de gastar la
  llamada, indicando la ruta exacta del problema) como en el modelo simulado
  — así cualquier esquema incompatible salta en las pruebas locales, sin
  necesidad de clave. Se validaron los 19 esquemas del programa: todos
  correctos.

## v0.29.0 — 2026-07-20
- 👥 ELENCO CON CONSISTENCIA VISUAL (personajes coherentes en TODO el
  video): en 📎 Archivos hay ahora un bloque «Elenco» donde creas los
  personajes del video — nombre, descripción y UNA O VARIAS FOTOS de
  referencia cada uno (varios personajes por video). El director lee el
  guion y ETIQUETA en qué escenas aparece cada personaje (se ve con
  insignias 👥 en el Storyboard), y esas imágenes se generan con un modelo
  de IDENTIDAD guiado por sus fotos: la misma cara y el mismo aspecto en
  todas sus escenas, no una persona distinta cada vez.
- MODELO DE IDENTIDAD configurable (⚙ Configuración → Imágenes): Nano
  Banana de Google por defecto (~$0.04/img, acepta VARIAS fotos de
  referencia a la vez) · Seedream 4 (multi-referencia, gran fidelidad) ·
  FLUX Kontext Pro (look FLUX, una referencia). Solo las escenas CON
  personajes usan este modelo; el resto sigue con tu modelo de siempre
  (mismo orden de costo, sin sorpresa en el presupuesto).
- PERSONAJE SIN FOTOS: se le genera UNA referencia (retrato coherente con
  el estilo del video, usando su descripción) y se reutiliza en todas sus
  escenas — consistencia también para personajes 100% IA.
- INTEGRADO CON EL NARRADOR (v0.28): el personaje marcado como «narrador»
  es el que habla en cámara con lipsync, usando su foto del elenco. Los
  prompts del director describen a los personajes por su ROL y acción — la
  cara la ponen las referencias, no la imaginación del modelo.
- La caché por escena ahora incluye su elenco: si cambias qué personaje
  aparece en una escena, solo ESA escena se regenera. Tras cambiar el
  elenco, rehaz desde «Escenas» para que el director lo use.

## v0.28.0 — 2026-07-20
- 🧑 PERSONAJE NARRADOR CON LIPSYNC (nuevo tipo de video): sube tu voz + la
  IMAGEN del personaje (nueva categoría «🧑 Personaje narrador» al crear el
  proyecto) y el personaje narra EN CÁMARA con lipsync sobre tu audio real,
  intercalado con B-roll (tuyo o generado). Tú eliges el % DE PRESENCIA
  (15/30/45/60% al crear, 30% recomendado) y el DIRECTOR decide en qué
  momentos aparece con criterio narrativo: el gancho y el cierre piden la
  cara del narrador (primera persona), los picos dramáticos también, y el
  resto ilustra con B-roll. Puedes forzar personaje/B-roll escena a escena
  desde el ✂ Editor (regenera solo esas escenas).
- CÓMO FUNCIONA POR DENTRO (y por qué no rompe la sincronía): cada escena
  de personaje se genera con el tramo EXACTO de audio de esa escena
  (cortado de la pista única de voz) y entra al montaje como video MUDO —
  la voz la pone la misma pista continua de siempre, así que los labios
  quedan sincronizados sin tocar el motor de tiempos que estabilizamos.
- MODELOS con pros/contras en ⚙ Configuración → Personaje narrador:
  Sonic (~$0.02-0.05/seg, económico, por defecto) · OmniHuman de ByteDance
  (~$0.10-0.16/seg, calidad cine: gestos y emoción) · SadTalker (casi
  gratis, básico). ⚠ El lipsync se cobra POR SEGUNDO de personaje en
  pantalla: la estimación previa lo refleja según tu % de presencia y el
  modelo (ej. 2 min al 30%: ~$1-2 con Sonic, ~$4-6 con OmniHuman).
  Estrategia: itera con Sonic y genera la final con OmniHuman.
- DEGRADACIÓN LIMPIA: sin clave de Replicate (o si un clip falla), esas
  escenas usan la imagen fija del personaje con movimiento Ken Burns y se
  avisa — el video siempre se termina.

## v0.27.0 — 2026-07-20
- MINIATURAS PROFESIONALES, 3 DISEÑOS POR VIDEO: nueva fase de diseño real
  (no la banda oscura con texto de antes). Cada video recibe 3 miniaturas
  con diseños distintos aplicando las reglas de las miniaturas ganadoras:
  texto de 2-4 palabras GIGANTE legible en móvil, palabra de acento en el
  color de marca del canal (la misma identidad que los rótulos), kicker de
  contexto, alto contraste (gradientes/viñetas medidos, nunca texto
  flotando), imagen realzada y punto focal despejado. Los diseños:
  🎬 Cine (letterbox + gradiente + subrayado), 💥 Impacto (texto centrado
  enorme con trazo grueso + píldora) y ◧ Panel (panel lateral con filo de
  acento — máxima legibilidad en pequeño). El fondo de cada una es la
  escena más icónica (la elige la IA entre tus imágenes reales; sin
  repetir). En formatos verticales salen 1080x1920.
- 3 TÍTULOS Y 3 DESCRIPCIONES CON ESTRATEGIA: cada título llega con un
  ángulo de CTR distinto (curiosidad/bucle abierto · dato/beneficio ·
  contradicción/autoridad, máx. 70 caracteres, keyword al frente) y cada
  descripción con un enfoque distinto (SEO · narrativa · directa), todas
  con capítulos reales y hashtags. En la pestaña ▶ Video eliges con un
  clic la miniatura, el título y la descripción (la elección se guarda y
  es la que se usa al publicar).
- SIN IMPACTO EN LOS TIEMPOS: sigue siendo UNA sola llamada de IA (la
  misma de antes, con algo más de texto de salida — un par de segundos) y
  las miniaturas se dibujan en tu PC en milisegundos, sin generar imágenes
  nuevas ni costo extra.

## v0.26.0 — 2026-07-20
- MÁS MODELOS Y MÁS BARATOS, CON PROS Y CONTRAS A LA VISTA: cada modelo del
  catálogo (⚙ Configuración) muestra ahora su costo aproximado y sus
  ventajas ✚ / desventajas ✖. Nuevos modelos económicos: FLUX schnell
  (~$0.003/imagen, 10x más barato), SDXL Lightning (~$0.0015, casi gratis,
  para borradores), Imagen 4 Fast (bueno con texto en imagen), Seedance 1
  Lite (~$0.06-0.15/clip de video) y LTX Video (el más rápido y barato).
  La ESTIMACIÓN de costo/tiempo ahora es POR MODELO: al elegir uno
  económico, el presupuesto previo baja de verdad (antes estimaba igual
  con cualquier modelo del proveedor). Sobre la colección «try for free»
  de Replicate: son corridas de PRUEBA gratuitas limitadas (al agotarlas
  pide crédito) — sirve para probar un modelo antes de pagarlo, no como
  vía gratuita permanente. Los ahorros reales están en: modelos económicos
  para iterar + el final con el premium, Edge TTS (gratis), biblioteca de
  música local y Ken Burns en vez de video IA.
- 10 IDIOMAS CON NOMBRE COMPLETO: Español, Inglés, Chino mandarín, Hindi,
  Francés, Árabe, Bengalí, Portugués, Ruso y Alemán — seleccionables en
  ⚙ Configuración con su nombre completo (ya no la sigla). El idioma guía
  TODO: guion, escenas, rótulos, metadatos, transcripción y el idioma del
  stream de subtítulos del mp4. Edge TTS incluye ahora voces gratuitas
  para los 10 idiomas (elige una voz DEL idioma: la voz no traduce).
- FORMATOS CORTOS VERTICALES: al crear un proyecto eliges el formato —
  🎬 YouTube largo (16:9) · 📱 YouTube Short (≤60s) · 📱 Reel de Instagram
  (≤90s) · 📱 TikTok (~60s). Los verticales generan 9:16 (1080x1920) con
  guion corto de gancho inmediato, escenas rápidas (~3s), imágenes y video
  IA en 9:16 y subtítulos grandes quemados — listos para subir. El formato
  es POR PROYECTO (no toca tu configuración global).
- ✂ EDITOR DE ESCENAS (nueva pestaña): ajusta por escena el movimiento de
  cámara (Ken Burns), la transición, el efecto de sonido, la intensidad
  musical, y el rótulo (texto/encabezado/tipo — se re-ancla solo al momento
  exacto en que se pronuncia); con voz TTS también la DURACIÓN de cada
  escena. «Aplicar» + remontar: solo se rehace el montaje (rápido y sin
  costo de IA). Nota honesta: no es un CapCut — la edición cuadro a cuadro
  con línea de tiempo arrastrable no cabe con seguridad en esta
  arquitectura; este editor cubre los ajustes que de verdad cambian el
  resultado sin regenerar nada caro. El orden y la narración se editan
  desde el Guion (eso sí regenera fases).

## v0.25.3 — 2026-07-20
- ¡EL RECORTE, ENCONTRADO Y ELIMINADO DE RAÍZ! Con el audio final que
  subiste lo medí de verdad: la voz estaba INTACTA en la pista intermedia,
  pero el video final tenía SILENCIO ABSOLUTO justo en «Su padre, Filipo
  II… una provincia» (segundos 15-19). Aislé el culpable filtro por filtro:
  el `loudnorm` de UNA SOLA PASADA de la mezcla final. Ese normalizador es
  DINÁMICO: cuando el volumen baja —una pausa dramática de la voz, o el
  «silencio estratégico» de la música en esa escena— sube la ganancia y
  luego la frena en seco, hundiendo la mezcla ENTERA (tu voz incluida) a
  casi-silencio (−90 dB) en ese punto. Por eso el «recorte» caía SIEMPRE en
  la misma escena (la del cambio de música) y no se veía en la pista de voz.
  ARREGLO: se quita ese loudnorm dinámico. La voz ya viene normalizada, así
  que la mezcla final ahora lleva una ganancia fija + un limitador de picos
  (alimiter): loudness estable ~−14 LUFS (apta para YouTube), sin tocar la
  dinámica de la voz. Reproducido y verificado con medidas: con loudnorm la
  voz se hundía; sin él, queda intacta. Ajustable: audio.final_gain_db.
- Gracias por insistir con que tu grabación es profesional y por subir el
  audio final: sin eso habría seguido buscando en el lado equivocado.

## v0.25.2 — 2026-07-20
- PROBADO CON TU AUDIO REAL: pasé tu grabación profesional por el
  constructor de la línea de tiempo de voz y NO se pierde ni un segundo de
  habla — los 8 recortes caen TODOS en silencio real (64.36 s de voz entran,
  64.36 s salen). O sea, el motor de voz NO está borrando ninguna frase; el
  «recorte» que oyes viene de otra parte de la cadena (lo estamos acotando).
- ARREGLO de un falso positivo que tu audio destapó: la salvaguarda de «voz
  baja» marcaba PAUSAS REALES (25 s, 32 s, 47 s, 62 s) como habla baja solo
  porque una palabra de Whisper se desviaba ±0.3 s hacia esa pausa — y el
  realce de v0.25.1 habría amplificado el ruido de fondo de esas pausas.
  Ahora se exige que las palabras LLENEN el hueco (>55 %) y sean ≥2 para
  marcarlo como voz baja, y el realce nunca toca nada por debajo de −55 dB
  (silencio de verdad). En tu audio profesional ya no se marca ni realza
  nada indebido.

## v0.25.1 — 2026-07-20
- EL «RECORTE LARGO» NO ERA UN RECORTE: EL LOG LO PROBÓ. En tu última prueba
  las compresiones sumaban ~2.3 s en total (imposible que borren una frase
  entera) y la pista de voz tenía la longitud completa esperada — o sea, NO
  se borraba nada. Lo que oías como «recorte» era una frase CONSERVADA
  (gracias a la salvaguarda de v0.25.0) pero dicha tan baja que no se oía:
  solo la sílaba fuerte («ca» de «periférica») pasaba. Ahora, además de
  conservarla, el programa REALZA esos tramos de habla baja hasta un nivel
  audible (solo esos tramos; ni el silencio ni el resto se tocan) — la voz
  que ya estaba ahí por fin se escucha. El aviso «🔊 Detecté habla muy baja»
  sigue apareciendo para que, si quieres, regrabes esa parte con mejor
  volumen; pero ya no se pierde ni se apaga.
- SUBTÍTULOS SIN PALABRAS HUÉRFANAS NI TRIPLE LÍNEA: se troceaban POR ESCENA,
  así que una frase que cruzaba la frontera de una escena quedaba partida y
  dejaba una palabra sola («El» al empezar una escena, «Cuando» colgada al
  final de otra y desapareciendo en un instante). Ahora los subtítulos se
  trocean de forma GLOBAL sobre toda la narración: las frases fluyen a
  través de las escenas y ninguna palabra queda huérfana. Además, ningún
  subtítulo se solapa con el siguiente (ese solape era el que hacía aparecer
  una tercera línea fugaz con la primera palabra del subtítulo siguiente).

## v0.25.0 — 2026-07-20
- LA CAUSA REAL DEL RECORTE, POR FIN: no era un arranque suave — era una
  FRASE ENTERA borrada («Su padre, Filipo II, había pasado años convirtiendo
  una provincia vulnerable y periféri…», de la que solo sobrevivía la sílaba
  «ca»). El motivo: esa frase está dicha MÁS BAJO que el resto (te alejas
  del micro, un pasaje suave), y cae por debajo del umbral de silencio
  (-45 dB). silencedetect solo mira la ENERGÍA, así que la marcaba como
  «silencio»… y el compresor de pausas la quitaba como si fuera aire muerto.
  Encajaba con todo: el mismo punto siempre (esa frase siempre suena igual
  de baja), «solo se oye ca» (esa sílaba sí pasaba el umbral), y ni la
  autocomprobación saltaba (contaba la frase como silencio en ambos lados).
  ARREGLO DE RAÍZ: Whisper SÍ transcribió esa frase, así que ahora, antes de
  tocar cualquier hueco, se comprueba si hay PALABRAS cronometradas dentro.
  Si las hay, NO es silencio: es voz baja y se conserva intacta, jamás se
  recorta ni se rellena. Además el programa te AVISA («🔊 Detecté habla muy
  baja en …»): esa parte se oirá floja, conviene regrabarla más cerca del
  micro o subirle el volumen. Este fue el «recorte» que llevábamos días
  persiguiendo.
- SUBTÍTULOS ESTILO CINE (frases cortas): los subtítulos eran párrafos de
  dos líneas llenas, poco profesionales. Ahora cada subtítulo es una frase
  o cláusula BREVE, acorde a lo que se dice en ese instante: se corta al
  terminar cada oración (. ! ? …) y en las comas/pausas fuertes, con líneas
  más cortas (max_chars_per_line 32, antes 42). El texto en pantalla cambia
  al ritmo de la voz, no en bloques largos. Ajustable en config.
- Nota sobre los rótulos desfasados: al borrar una frase entera, TODO lo que
  venía después se corría — de ahí el desfase de subtítulos y rótulos que
  también viste. Al dejar de borrar esas frases, la línea de tiempo vuelve a
  cuadrar; revisa los rótulos en una generación limpia y, si aún notaras
  alguno movido, dímelo con el segundo exacto.

## v0.24.5 — 2026-07-20
- EL RECORTE DE VOZ, ATACADO POR EL LADO CORRECTO (y corrigiendo una
  regresión que YO metí en v0.24.4). En v0.24.4 el recorte se hacía en el
  trozo de silencio profundo MÁS GRANDE; cuando una respiración a mitad de
  pausa partía ese silencio y el trozo mayor quedaba pegado a la palabra
  siguiente, el recorte se MOVÍA hacia ella y se comía su arranque — por
  eso en tu última prueba el «pedazo» recortado fue el más largo de todos.
  La lección clave: los dos bordes de una pausa NO son igual de fiables.
  La COLA de la palabra anterior decae rápido de fuerte a nada, así que su
  borde de silencio es de fiar (basta una guarda corta). Pero el ARRANQUE
  de la siguiente, si es una fricativa suave (la «s» de «Su padre») o
  aireado, se mantiene por debajo de CUALQUIER umbral 100-250 ms: su borde
  medido SIEMPRE llega tarde, ya dentro de la palabra. Por eso ahora el
  recorte se hace SIEMPRE por el FRENTE de la pausa (justo tras la palabra
  anterior) y deja una guarda GRANDE antes del arranque de la siguiente
  (onset_guard, 0.45 s por defecto). El arranque se estima por lo más
  temprano —y seguro— entre el silencio medido y el tiempo de Whisper.
  Resultado: pase lo que pase con respiraciones, ritmo o umbrales, el
  recorte nunca se acerca al arranque de la palabra siguiente. Ajustable en
  config: audio.onset_guard (súbelo a 0.55-0.6 si aún oyeras algún recorte)
  y audio.cut_guard (guarda tras la palabra anterior).
- Si el recorte de v0.24.3/0.24.4 te dejó algún proyecto con la voz movida,
  basta «Rehacer desde Voz» con esta versión para reconstruir la pista.

## v0.24.4 — 2026-07-20
- EL ÚLTIMO RECORTE DE VOZ («Su padre, Filipo II», segundo 14): la guarda
  de v0.24.3 se medía desde donde la energía cruza el umbral de pausas
  (-45 dB). Pero una consonante suave como esa «s» inicial suena a ~-48 dB
  — MÁS silenciosa que el umbral — así que el detector la contaba como
  parte del silencio y la guarda se medía desde la vocal siguiente: si la
  «s» duraba más de 0.25 s, su cola seguía cayendo en el tramo saltado
  (por eso el recorte se hizo más pequeño pero no desapareció). Ahora hay
  una SEGUNDA medición más estricta (-55 dB, configurable en
  audio.deep_silence_db) donde una respiración o una «s» suave SÍ cuentan
  como voz, y todo corte vive únicamente en ese interior profundo con la
  guarda a cada lado. En el caso de prueba que reproduce tu frase, el
  recorte de v0.24.3 reanudaba 0.1 s DENTRO de la «s»; ahora termina 0.6 s
  ANTES de que arranque.
- VALLA ADICIONAL CON LA TRANSCRIPCIÓN: el recorte tampoco puede pasar del
  arranque de la palabra siguiente según Whisper (ni empezar antes del
  final de la anterior). Si Whisper deriva hacia dentro de la pausa, solo
  restringe más — nunca abre la puerta a cortar voz.
- LAS PAUSAS DEL DIRECTOR TAMPOCO PARTEN RESPIRACIONES: al AMPLIAR una
  pausa, el silencio se insertaba en el punto medio del hueco — que podía
  caer justo en mitad de una respiración suave, partiéndola en dos (un
  microcorte audible). El punto de inserción ahora se reubica al interior
  profundo del silencio. (En tu última prueba hubo «1 ampliada» justo en
  esa transición — este era el otro sospechoso.)
- Si algún ajuste no encuentra interior profundo (ruido de fondo alto), se
  usa la guarda ancha de antes y el log lo AVISA con «⚠ N ajuste(s) sin
  interior profundo medible» — si ves ese aviso, compártelo.

## v0.24.3 — 2026-07-20
- EL «PEDAZO DE VOZ» RECORTADO EN LA TRANSICIÓN, RESUELTO DE RAÍZ: al
  comprimir una pausa larga, el programa saltaba parte del silencio y
  reanudaba la voz a solo 0.1 s del final del silencio MEDIDO. Pero
  silencedetect marca el fin del silencio donde la energía cruza el umbral,
  y un arranque de palabra suave o aireado ya suena 100-200 ms ANTES de ese
  cruce: con solo 0.1 s de margen, ese arranque caía dentro del tramo
  saltado y se recortaba — siempre en el mismo punto (la detección es
  determinista), y el subtítulo sí mostraba la palabra porque la
  transcripción sí la tenía. Ahora el recorte deja un margen de guarda
  (cut_guard, 0.25 s por defecto) a AMBOS lados: nunca se acerca a la voz,
  pase lo que pase con la precisión del umbral. En el mismo caso de prueba,
  el margen final pasó de 0.1 s a 0.95 s. Ajustable en config
  (audio.cut_guard); súbelo a 0.3-0.35 si aún oyeras algún recorte.
- PUNTUACIÓN COMPLETA EN LOS SUBTÍTULOS QUEMADOS: los subtítulos se anclan
  a los tiempos por palabra de Whisper (que vienen SIN signos), y la
  puntuación se reponía emparejando posición a posición con el texto del
  segmento. Si el conteo no cuadraba por un solo token (un número que
  Whisper parte, unos puntos suspensivos sueltos), se abandonaba y el
  bloque ENTERO perdía comas y puntos. Ahora se alinea por el núcleo de
  cada palabra: cada palabra toma su token puntuado aunque el conteo no
  cuadre, sin perder ni duplicar palabras.
- SUBTÍTULOS Y RÓTULOS AÚN MÁS AJUSTADOS: el lazo de sincronía corregía el
  desfase solo si superaba 120 ms, así que un desfase de ~111 ms (que sí se
  nota) se colaba sin corregir. Como la medición se hace sobre la mediana
  de ~15 arranques (muy estable), se bajó el tope a 50 ms: ahora se corrige
  hasta dejarlo prácticamente en cero cada vez.

## v0.24.2 — 2026-07-19
- EL % Y EL TIEMPO RESTANTE AHORA SE ACOTAN A LO QUE PEDISTE GENERAR: si
  solo pediste generar «hasta Análisis» (o cualquier fase previa a
  publicar el video completo), la barra ya no mostraba el estimado del
  VIDEO COMPLETO (ej. «~22 min restantes» con apenas el 1% hecho, cuando en
  segundos reales el análisis dura muy poco). Ahora estimate.py reparte el
  tiempo estimado entre las fases del pipeline (ingesta, concepto, guion,
  escenas, voz, B-roll, música, subtítulos, montaje, metadatos) y el
  servidor solo suma las fases que de verdad van a correr en esa ejecución
  — saltando además las que ya estén completadas al reanudar un proyecto a
  mitad de camino, igual que hace el generador real.
- AVISO CLARO CUANDO TERMINA CADA ETAPA: antes solo se sabía que el
  programa seguía trabajando mirando el 🧾 Log de eventos con detalle; ahora
  aparece un aviso emergente («✔ <fase> completada») cada vez que una etapa
  termina, además de la actualización silenciosa de los indicadores.

## v0.24.1 — 2026-07-19
- Al DUPLICAR un proyecto, ahora se pregunta el nombre ANTES de crear la
  copia — ese nombre pasa a ser el identificador interno del proyecto
  (antes solo cambiaba el nombre visible, pero por debajo se seguía
  registrando como «…-copia-copia-copia» en cada duplicado sucesivo, y ese
  nombre técnico era el que aparecía en el 🧾 Log de eventos). Si el nombre
  ya existe, se numera con un sufijo limpio (-2, -3…), no más cadenas de
  «copia».
- El Log de eventos ahora muestra el NOMBRE VISIBLE actual de cada
  proyecto (el que le pusiste), no el identificador técnico — aunque hayas
  renombrado o duplicado el proyecto después de que ese evento se registró.

## v0.24.0 — 2026-07-19
- ADIÓS AL EXCESO DE SILENCIOS: conservar íntegras todas las pausas de la
  grabación (v0.23.0) le metía el aire muerto de los ensayos al video (tu
  narración pasó de 70 a 87s). Ahora el director AJUSTA CADA PAUSA MEDIDA a
  su ritmo: las largas se comprimen (saltando SOLO silencio medido — la voz
  sigue siendo intocable), las cortas se respetan, y el «pace» por escena
  las escala (ligado acorta, amplio da aire). Configurable:
  audio.max_pause (1.2s por defecto). La escena 1 de 18 segundos era una
  pausa larga tuya dentro de la escena: se corrige sola.
- LA PAUSA DE DIRECTOR SOLO TRAS FIN DE ORACIÓN: si la frontera de escena
  cae en una vacilación a mitad de frase, ya no se inserta la pausa
  dramática ahí (ese silencio largo en mitad de una frase era lo que
  sonaba a «se cortó la voz» en el primer cambio de escena).
- LAZO CERRADO DE SINCRONÍA (sustituye a la calibración de Whisper, que
  resultó frágil: midió −158ms y +226ms en corridas de la MISMA
  grabación): ahora se mide el desfase de los subtítulos contra la pista
  de voz REAL ya montada y se corrigen todos por esa medición — y se
  re-mide para confirmar (queda en el log: «🔁 Lazo de sincronía»). Los
  rótulos usan la misma corrección.
- CIERRE MUSICAL: el fundido final ahora es largo (mínimo 2.5s) y muere
  EXACTAMENTE con la imagen — la música ya no termina antes ni de golpe.

## v0.23.0 — 2026-07-19
- EL PEDAZO DE VOZ CORTADO, encontrado por fin (con la pista clave del
  reporte: «el subtítulo SÍ muestra lo que la voz no dice»): la LIMPIEZA de
  la grabación recortaba los silencios internos, y con voz suave o aireada
  el filtro confundía sílabas con silencio y SE COMÍA pedazos de palabra.
  Era determinista (siempre el mismo punto — descartada la caché), ocurría
  ANTES de transcribir (Whisper subtitulaba el audio ya mordido: por eso el
  subtítulo muestra el texto que el audio perdió), y las fronteras de
  escena caen en las pausas — por eso sonaba «en la transición».
- ARREGLO DE RAÍZ: la limpieza ya SOLO recorta el silencio de los bordes
  (inicio y fin, dejando 0.25s de aire) y normaliza el volumen. Los
  silencios internos se conservan SIEMPRE — el director los gestiona con su
  motor de pausas. Ya no existe NINGUNA operación destructiva sobre tu voz
  en todo el pipeline.
- Refuerzo: los respiros solo se insertan en silencios medidos a -45 dB
  (umbral estricto) — la voz aireada o susurrada ya no se confunde con
  silencio.
- B-ROLL EN EL ORDEN QUE TÚ INDICAS: si el archivo trae un número que
  coincide con una escena (scene_003.mp4, 05_castillo.jpg, «escena 7».mp4),
  va DIRECTO a esa escena — determinista, sin criterio del director y sin
  gastar tokens. Ideal para reutilizar material exportado de un proyecto
  anterior (ya viene numerado). Los archivos sin número siguen el reparto
  semántico (que ahora también ve el NOMBRE del archivo, no solo la
  descripción visual).
- Requiere «Rehacer desde Análisis» una vez para re-limpiar y re-transcribir
  tu narración (unos centavos de Whisper) — de ahí en adelante la fuente
  queda íntegra.

## v0.22.0 — 2026-07-19
- LA PIEZA QUE FALTABA (encontrada gracias al diagnóstico del log v0.21.1,
  que salió PERFECTO a nivel de archivo y aun así el desfase se veía): los
  TIEMPOS DE WHISPER derivan de forma sistemática (±0.3–0.8s es normal en
  whisper-1) respecto a dónde suena de verdad cada palabra en tu grabación.
  Los subtítulos y rótulos se anclaban a esos tiempos corridos — toda la
  matemática interna era exacta, pero sobre coordenadas desplazadas. Los
  cortes de escena (anclados a silencios MEDIDOS en la onda) sí estaban
  bien: por eso el desfase se notaba justo en las transiciones.
- CALIBRACIÓN AUTOMÁTICA: al transcribir, cada arranque de habla según
  Whisper se compara con los arranques REALES medidos en la onda
  (silencedetect); la mediana de las diferencias corrige TODOS los tiempos
  de segmentos y palabras. El log registra cuántos milisegundos venían
  corridos («🎯 Calibración de transcripción: +XXX ms»).
- MEDICIÓN DE CONTENIDO en cada montaje: se compara dónde SUENA tu voz
  (arranques de habla reales de la pista) contra dónde CAEN los subtítulos,
  y la mediana firmada queda siempre en el 🧾 Log de eventos («Contenido
  voz↔subtítulos: +XX ms»). El «se siente desfasado» ahora es un número
  con signo — y si supera 400 ms aparece un aviso con la solución.
- Verificado con deriva simulada de +400 ms: la calibración la mide, la
  corrige, y la medición de contenido confirma subtítulos a +0 ms de la
  voz real.

## v0.21.1 — 2026-07-19
- Gracias al Log de eventos compartido, la autocomprobación de v0.21.0
  atrapó una deriva real: el video final reportaba 94s cuando el cuerpo
  medía 79s. La causa más probable (verificada en laboratorio): un
  subtítulo cuyo fin quedaba más allá del final del video ESTIRA la pista
  de subtítulos del mp4 — el contenedor «dura» más y el reproductor
  muestra cola vacía y tiempos corridos.
- TRIPLE DEFENSA:
  · Ningún subtítulo puede terminar después del final del video (se
    recortan al montar los cues).
  · La mezcla final lleva un tope duro de duración (-t): ningún stream
    puede exceder el cuerpo, pase lo que pase.
  · El diagnóstico de sincronía ahora se registra SIEMPRE en el 🧾 Log de
    eventos con la duración medida de CADA stream (video, audio,
    subtítulos) + la pista de voz; si algo deriva, se registran además las
    duraciones de cada escena — el log identifica el stream exacto, no una
    cifra global ambigua.
- Afinado el aviso de la autocomprobación de voz: el umbral de «segundos
  hablados» era demasiado estricto (saltaba por ruido de medición aunque
  la duración estuviera perfecta, como en tu log: 79.20s vs 79.21s). La
  señal dura (duración total) mantiene su tolerancia estricta.

## v0.21.0 — 2026-07-19
- UNA SOLA LÍNEA DE TIEMPO (cambio de arquitectura — la causa raíz del
  desfase en las transiciones, MEDIDA y demostrada): cada escena se
  renderizaba como un mp4 con su PROPIA pista de audio, y al concatenarlas
  el contenedor corría los cuadros +23 ms (exactamente un cuadro de audio
  AAC) en cada transición — los cortes de escena y los rótulos llegaban
  tarde respecto a la voz y los subtítulos, que sí iban sobre la línea de
  tiempo teórica. Por eso el desfase se sentía «a través de la transición
  de cada escena» sin importar cuánto se afinara el resto.
- El arreglo (verificado: 0.00 ms de error en las fronteras): las escenas
  ahora son SOLO VIDEO — el audio del video completo es UNA pista continua
  (voz + música + efectos) que se mezcla al final sobre el cuerpo entero.
  La voz, los subtítulos, los rótulos y los efectos fluyen como un todo;
  las escenas son solo lo visual que se pinta encima.
- La voz TTS (guion escrito) usa ahora la MISMA arquitectura que la
  narración propia: los clips se colocan en el inicio exacto de cada
  escena dentro de una única pista continua (antes iban incrustados en el
  audio de cada escena — la fuente del desfase).
- EL PIPELINE SE VERIFICA A SÍ MISMO de punta a punta: al concatenar
  comprueba que el cuerpo dura EXACTAMENTE la suma de escenas (±1 cuadro)
  y al terminar comprueba el video final contra lo esperado. Si algo
  deriva, aviso visible y registro en el 🧾 Log de eventos; si todo cuadra,
  verás «✅ Sincronía verificada» en el progreso.
- Los proyectos existentes re-renderizan sus escenas una única vez al
  reanudar el montaje (formato nuevo sin audio); los proyectos de versiones
  muy anteriores sin pista continua piden «Rehacer desde Voz» con un
  mensaje claro.

## v0.20.1 — 2026-07-19
- La REVISIÓN del B-roll subido por el director ahora es CONFIGURABLE: un
  interruptor en el Storyboard permite desactivarla para ahorrar tokens.
  Desactivada, tu material se usa tal cual y no se gasta NADA de visión IA
  (ni una llamada). El interruptor de «reemplazar lo que no encaje» queda
  deshabilitado cuando la revisión está apagada (sin revisión no hay
  veredicto que aplicar).

## v0.20.0 — 2026-07-19
- B-ROLL MANUAL POR ESCENA (pestaña Storyboard): tras «Generar hasta el
  guion gráfico», ahora puedes subir tu propia imagen o video a las escenas
  que quieras — ideal para reutilizar B-roll de pruebas anteriores y
  ahorrar tiempo y créditos. Lo que no subas, se genera con IA (opcional
  por escena). Cada escena acepta el tipo que decidió el director: una
  escena de video acepta video (o una imagen, que se usa con movimiento
  Ken Burns, avisando); una de imagen solo acepta imagen (un video se
  rechaza con un mensaje claro).
- EL DIRECTOR REVISA LO QUE SUBES: con visión IA juzga si tu B-roll de
  verdad ilustra lo que se narra en esa escena, y te muestra su veredicto
  (✓ aprobado / ⚠ no encaja + motivo) en el propio Storyboard. Si activas
  «el director reemplaza lo que no encaje», los que no encajan se generan
  con IA (se te notifica el motivo); si no, se respeta SIEMPRE tu elección
  y solo se avisa. Solo se revisa lo que cambió (no gasta tokens de más).
- Nada de esto afecta la voz, los subtítulos ni los tiempos: cambiar el
  B-roll de una escena solo rehace esa escena en el montaje (las duraciones
  vienen de la voz, son independientes del material visual). Subir o quitar
  material reanuda solo desde el B-roll, no desde el guion.

## v0.19.0 — 2026-07-19
- ARREGLO: renombrar un proyecto no se veía reflejado en el panel principal
  (el título de arriba seguía mostrando el nombre viejo aunque la lista de
  la izquierda sí se actualizara). Ahora ambos se refrescan al renombrar.
- VERSIONADO SEMÁNTICO: el número de versión pasa de un contador
  consecutivo (v1, v2, v3…) a SemVer real (Mayor.Menor.Revisión). Se
  rehicieron los números de TODO el historial anterior (v1→v0.1.0,
  v26→v0.18.0…) conservando el contenido de cada entrada tal cual — nada
  se perdió, solo se renumeró con criterio (función nueva = Menor, arreglo
  = Revisión).
- REPORTE DE GASTO REAL: al terminar de generar (o en cualquier momento
  después), el proyecto muestra el gasto REAL por proveedor — no una
  predicción — con lo que de verdad se generó (tokens exactos de Claude,
  imágenes/clips/voz/transcripción realmente producidos) y el tiempo REAL
  que tardó la última ejecución y el total acumulado del proyecto. Se
  acumula entre sesiones: reanudar un proyecto suma al total, no lo
  reemplaza.
- PROGRESO EN VIVO: barra con % completado y tiempo restante estimado
  mientras se genera el video, calculada con la misma base de tiempo que
  ya se mostraba antes de empezar (ningún número nuevo que la contradiga).
- PANEL DE ESTIMACIÓN MÁS PEQUEÑO Y ÚTIL: antes de generar, ahora muestra
  un solo número aproximado («~$X.XX») en vez de un rango ancho que no
  decía mucho — el desglose por fase sigue disponible con un clic. Además
  el rango interno de la estimación de Claude se angostó (antes variaba
  hasta 2.25× entre el mínimo y el máximo mostrados; ahora como mucho 1.3×).

## v0.18.0 — 2026-07-19
- CAUSA DE RAÍZ encontrada: «subo mi voz y el programa genera una propia».
  Una nota de voz grabada en un contenedor de VIDEO (.webm o .mp4 — lo
  normal si la grabaste con el micrófono del navegador o ciertos
  celulares) se descartaba EN SILENCIO al analizarla: el programa seguía
  sin ningún error y generaba guion y voz sintética por su cuenta, sin
  avisar. Ahora se detecta y se le extrae el audio igual que a cualquier
  narración. Además, se añadieron avisos explícitos para que esto NUNCA
  vuelva a pasar en silencio: si un archivo de voz no se puede aprovechar,
  si no se detecta voz en la grabación, o si falta configurar un
  transcriptor real (STT) y se usaría texto de muestra — todo queda dicho
  en el registro de avisos y en el 🧾 Log de eventos.
- GESTIÓN DE PROYECTOS: la lista de la izquierda ahora se ordena del más
  reciente al más antiguo (antes salía alfabética por nombre interno).
  Nuevo: 🔎 buscador, filtro (todos · en curso · completos · con errores)
  y, pasando el cursor sobre cada proyecto, tres acciones rápidas:
  ⧉ duplicar (copia completa, incluidas las fases ya generadas — para
  variar un video sin pagar de nuevo lo ya hecho), ✎ renombrar (el nombre
  visible; los archivos internos no se mueven, así que no hay riesgo de
  romper nada) y 🗑 borrar.

## v0.17.1 — 2026-07-19
- ARREGLO de la regresión de v24 (desfase/corte en la transición de la
  escena 1 a la 2, y desfase acumulado después):
  · La pausa entre escenas exigía solo un hueco entre palabras según
    Whisper — hasta un microhueco de 50ms A MITAD DE FRASE valía, y ahí se
    metía la pausa (ese era el corte que se oía en la transición). Ahora
    toda pausa exige DOBLE verificación: hueco entre palabras Y silencio
    real MEDIDO en la onda (≥0.15s). Si la frontera cae a mitad de frase,
    no se inserta nada: la voz fluye a través del corte visual.
  · Las escenas con clip de video podían salir con UN CUADRO DE MÁS (por el
    redondeo de la duración a milésimas): cada escena de video sumaba hasta
    42ms y los subtítulos quemados se iban corriendo respecto a la voz —
    desfase progresivo. Ahora cada escena se renderiza con el número EXACTO
    de cuadros del mapa de tiempos.
- AVISO CLARO DE REINICIO: tras actualizar.bat, si la ventana de
  iniciar.bat sigue abierta con la versión anterior, la interfaz mostraba
  la versión nueva pero el programa seguía siendo el viejo (por eso el log
  de eventos decía «No encontrado»). Ahora la interfaz compara la versión
  del programa EN EJECUCIÓN con la del disco y muestra un aviso rojo:
  «cierra la ventana de iniciar.bat y ábrela de nuevo».
- El log de eventos registra también el arranque del programa (útil para
  confirmar que el reinicio aplicó la actualización).
- Afinado el filtro de palabras duplicadas de v23: ya solo descarta
  duplicados exactos (mismo texto y mismo instante) — un solape de
  milisegundos entre palabras legítimas de Whisper ya no borra palabras
  del subtítulo.

## v0.17.0 — 2026-07-19
- SOLUCIÓN DE RAÍZ del corte de voz en las transiciones (el «se cortó al
  segundo 11»). Causa: las fronteras de escena se colocaban por TIEMPO y
  podían caer a mitad de una palabra; al insertar ahí el respiro, la palabra
  se partía. Ahora TODO silencio se inserta en el hueco ENTRE dos palabras
  reconocidas (en su punto de menor energía, medido en la onda). Es
  imposible partir una palabra, sin importar la imprecisión de Whisper.
- EL RITMO LO DECIDE EL DIRECTOR, no un rango de tiempos fijo:
  · Entre escenas/bloques: respiro base + la pausa dramática que el director
    marcó para esa escena (pause_after).
  · Dentro de la escena: un respiro breve al final de cada frase, según el
    RITMO que el director elige por escena — nuevo campo «pace»: ligado
    (frases encadenadas, tensión/acción), normal, o amplio (contemplativo,
    solemne). Así las frases dejan de sonar pegadas, con criterio, y sin
    cortar la voz. (Cuesta ~0 tokens: es un campo más del análisis que ya se
    hacía.)
  · Donde el narrador encadenó dos palabras sin ningún hueco, no se inserta
    nada — no hay dónde sin cortar; la voz fluye, muy documental.
- MAPA DE TIEMPO GLOBAL: subtítulos y rótulos ahora se anclan al instante
  REAL en que suena cada palabra en el video (una sola fuente de verdad para
  voz, subtítulos y rótulos). Esto corrige el desfase acumulado entre voz,
  subtítulos, rótulos y escenas — todo se mueve junto.
- Autocomprobación reforzada: verifica que la voz conserva todos sus
  segundos y que la pista dura exactamente la suma de escenas.
- LOG DE EVENTOS (🧾 en el menú): cada novedad, aviso, error y el TIEMPO de
  cada fase quedan registrados y se pueden descargar para compartir. Filtra
  por avisos/errores y actualiza en vivo.

## v0.16.2 — 2026-07-19
- ARREGLO de las palabras repetidas en subtítulos («historia historia»): la
  transcripción asignaba las palabras a los segmentos de Whisper por ventana
  de tiempo, y dos segmentos vecinos pueden solaparse un poco — la misma
  palabra caía en AMBOS y quedaba duplicada. Ahora cada palabra se asigna a
  un único segmento (misma técnica que ya arregló la duplicación entre
  escenas en v21).
- RECUPERADA LA PUNTUACIÓN en subtítulos con sincronía por palabra: la API
  de Whisper devuelve el tiempo de cada palabra SIN comas ni puntos (aunque
  el texto completo del segmento sí los trae) — al reconstruir el subtítulo
  palabra por palabra se perdía toda la puntuación. Ahora se recupera del
  texto del segmento, conservando el tiempo real de cada palabra.
- Margen de seguridad más generoso al anclar los respiros en silencios
  reales (0.06s → 0.08s por lado, silencio mínimo detectable 0.15s → 0.18s):
  refuerzo adicional contra cortes al filo de una palabra.
- COLA DE CIERRE MÁS CORTA: outro (3.5s → 2s) y fundido final (3s → 1.5s).
  Antes casi todo el cierre se iba en el fundido y se sentía como un hueco
  vacío tras la última palabra; ahora respira lo justo y el fundido sigue
  sin tocar nunca la voz.
- Red de seguridad adicional: si un proyecto ya guardado tiene palabras
  duplicadas (del bug anterior), se filtran automáticamente al usarlas — no
  hace falta volver a transcribir para beneficiarte del arreglo.

## v0.16.1 — 2026-07-18
- AUDITORÍA TOTAL DE SINCRONIZACIÓN (voz, subtítulos, rótulos y escenas).
  Causa raíz de la «voz cortada en varios tramos»: los respiros se cortaban
  en las fronteras de segmento de Whisper, que traen un sesgo de ±0.2–0.4s —
  cuando Whisper marcaba el inicio tarde, el corte caía A MITAD DE PALABRA.
  Ahora los silencios se MIDEN en la onda real de tu grabación (ffmpeg
  silencedetect) y cada respiro se ancla DENTRO de un silencio medido, con
  margen de seguridad a cada lado. Donde no hay silencio real cerca (aunque
  Whisper diga que sí), no se corta nada: la voz fluye a través del corte
  visual. Es matemáticamente imposible partir una palabra.
- AUTOCOMPROBACIÓN de la pista de voz: al montarla se verifica que dura
  exactamente la suma de las escenas y que conserva TODOS los segundos
  hablados de tu grabación — cualquier deriva dispara un aviso visible en
  vez de entregar un video desincronizado en silencio.
- CACHÉ HONESTA del B-roll: cada escena firma su material (hash del prompt
  IA o archivo propio asignado). Si rehaces desde Análisis/Guion y el
  contenido de una escena cambia, su imagen/clip viejo se descarta y se
  rehace (con aviso) — antes se quedaba pegado material de la versión
  anterior y el video salía «desfasado» respecto a la narración. Los
  proyectos previos adoptan la firma sin regenerar nada (cero costo
  sorpresa).
- El montaje re-renderiza una escena cuando su imagen/clip se regeneró con
  el MISMO nombre (la firma ahora incluye tamaño y fecha del archivo).
- B-roll propio: si re-subes un archivo con el mismo nombre, la copia de la
  escena se refresca (antes quedaba la vieja).
- Batería de pruebas nueva: fronteras de Whisper deliberadamente sesgadas,
  huecos inventados a mitad de voz continua, invariante palabra↔video
  (±1.5 cuadros), subtítulos y las tres rutas de caché del B-roll.

## v0.16.0 — 2026-07-18
- SINCRONÍA REAL de los subtítulos con narración propia: antes se repartían
  por proporción de caracteres dentro de cada escena, así que el cambio de
  texto se sentía ligado al corte de escena y no a tus pausas reales. Ahora
  se piden a Whisper los tiempos de CADA PALABRA y los subtítulos se anclan a
  ellos: si haces una pausa a mitad de una frase, el subtítulo la refleja en
  vez de ignorarla.
- Los rótulos en pantalla usan la misma fuente de verdad (ya no interpolan
  dentro del segmento: usan la palabra real).
- Arreglado de paso un caso límite que encontré verificando esto: una palabra
  que cae justo en la frontera entre dos escenas podía duplicarse en los
  subtítulos de ambas. Ahora cada palabra se asigna a una única escena.
- Compatibilidad total: si un proyecto (o tu STT) no trae tiempos por
  palabra, se usa automáticamente el método anterior — nada se rompe.

## v0.15.0 — 2026-07-18
- ARREGLO del crash por "NSFW content detected": un solo prompt marcado como
  sensible ya NO tumba todo el proyecto. Se sube la tolerancia de FLUX a 6
  (evita falsos positivos en contenido histórico/bélico) y, si aun así se
  rechaza una imagen, se reintenta con el prompt suavizado y, en último caso,
  se usa un fondo cinematográfico neutro solo para esa escena — el video se
  completa y un aviso te dice qué escena y qué hacer. Los errores de
  infraestructura (clave/red) sí detienen la fase, como debe ser.
- Sincronía EXACTA de los rótulos con la narración propia: antes se estimaba
  por posición del texto (impreciso, se notaba con B-rolls en video); ahora
  se usa el timestamp REAL de Whisper e incluso se interpola la posición de
  la palabra dentro de su frase — el highlight aparece justo cuando lo dices,
  sin importar si la escena usa imagen IA, tu imagen o tu video.

## v0.14.0 — 2026-07-18
- RESPIRACIÓN ESTILO DOCUMENTAL en narración propia: los espacios en blanco
  se insertan SOLO dentro de las pausas naturales de tu grabación (donde hay
  silencio real) — la voz jamás se corta a destiempo. Entre escenas hay un
  respiro (audio.scene_breath, 0.3s) y las pausas dramáticas del director
  creativo (pause_after) vuelven a aplicarse, siempre en pausas reales.
  Donde el corte visual cae a mitad de frase, la voz fluye a través del
  corte (muy documental) sin insertar nada.
- AIRE DE ENTRADA (audio.intro_seconds, 0.8s): el video abre, entra la
  música y luego la primera palabra.
- COLA DE CIERRE (audio.outro_seconds, 3.5s): tras la última palabra, la
  imagen y la música respiran — el fundido final NUNCA toca la voz (adiós al
  desvanecimiento al filo del cierre). Aplica también con voz IA (TTS).
- La pista de voz se compila como WAV sin pérdidas (narration_timeline.wav):
  cortes solo en silencios reales, sin el padding del codificador mp3.

## v0.13.2 — 2026-07-18
- SOLUCIÓN DEFINITIVA de los saltos de voz en narración propia. La causa
  real: los tiempos de Whisper traen huecos entre segmentos (pausas,
  respiraciones) y esos huecos se DESCARTABAN de la línea de tiempo — el
  video quedaba más corto que la voz, se desincronizaba progresivamente y el
  final se truncaba. Ahora las fronteras de escena son puntos de corte sobre
  una línea de tiempo CONTINUA (la primera escena arranca en 0 y la última
  termina en el final real del audio): no se pierde ni un milisegundo.
- Cada corte de escena cae en un cuadro de video exacto (sin deriva
  acumulada): sincronía precisa de escenas y subtítulos con la voz.
- Los clips de voz cacheados de versiones anteriores se regeneran solos si
  sus fronteras cambiaron (reanudar un proyecto viejo queda bien).
- Limpieza de silencios más suave (detección RMS, umbral -42 dB): ya no se
  come respiraciones ni sílabas suaves al preparar tu grabación (aplica a
  proyectos nuevos o al rehacer desde Análisis).
- El registro muestra «🎙 Narración propia: línea de tiempo continua…» y
  «🎙 Voz: usando tu narración CONTINUA…» para confirmar que el modo correcto
  está activo.

## v0.13.1 — 2026-07-17
- ARREGLO GRAVE del audio en narración propia: tu voz grabada ya NO se pica
  con silencios entre escenas. Antes se insertaba relleno (0.35s) y pausas
  entre cada trozo — muy notorio con ritmos rápidos. Ahora el montaje usa tu
  grabación CONTINUA como pista única de voz: suena exactamente como la
  grabaste, sin cortes ni huecos. Las duraciones de escena son exactas, así
  que los subtítulos quedan perfectamente alineados.
- ARREGLO de las transiciones que no variaban: «Guardar configuración»
  congelaba TODOS los ajustes (incl. el viejo «transition: fade») en tu
  archivo local y tapaba los nuevos valores por defecto. Ahora solo se guarda
  lo que la interfaz controla, y al arrancar se limpian los defaults
  congelados de versiones antiguas. Efecto inmediato: las transiciones vuelven
  a variar (auto) y otros ajustes nuevos (paralelismo, etc.) dejan de quedar
  tapados. No pierdes tus preferencias reales (idioma, resolución, ritmo,
  proveedores, etc.).

## v0.13.0 — 2026-07-16
- CANALES Y ESTILOS (📺 en el menú): guarda el estilo de un proyecto que te
  gustó (botón «💾 Guardar estilo» en la pestaña Concepto) o crea estilos
  desde cero; agrúpalos por canal de YouTube y elígelos al crear un proyecto
  nuevo. El video sale con esa dirección visual, tono, música, ritmo y
  fórmula EXACTOS — sin re-analizar referencias: ahorro directo de tiempo y
  tokens en cada proyecto del mismo canal.
- GENERACIÓN EN PARALELO (misma calidad, mismos tokens, mucho menos tiempo):
  imágenes IA de 4 en 4, clips de video de 2 en 2 (corren en el servidor de
  Kling — esperarlos uno a uno era puro desperdicio), voces de 4 en 4 y
  montaje de escenas de 2 en 2. Configurable en config.yaml → performance.
- Ken Burns optimizado (sobreescala 2560 en vez de 3840): montaje ~2× más
  rápido sin pérdida de calidad (las imágenes fuente son de 1536 px).
- La estimación de tiempo ahora refleja el paralelismo.

## v0.12.0 — 2026-07-16
- Transiciones entre escenas variadas: ya no todas hacen el mismo fundido.
  El video abre y cierra con fundido; entre escenas alterna corte seco (sin
  transición) y fundido breve según la historia (cambios de sección, saltos
  de tiempo/lugar y momentos dramáticos). Configurable: video.transition =
  auto (por defecto) · fade (todas) · none (todas corte). No altera la
  duración: los subtítulos siguen alineados.
- Reajustar las transiciones (o los rótulos) ahora SÍ se ve al reanudar el
  montaje: las escenas se re-renderizan cuando cambia algo visual.
- Arreglado el "congelamiento" en la Ingesta con enlaces de referencia: ahora
  muestra el progreso paso a paso (consultando, descargando, transcribiendo,
  midiendo ritmo) y la descarga tiene límite de tiempo — si YouTube se atasca,
  falla y degrada a los metadatos en vez de quedarse colgado.

## v0.11.0 — 2026-07-15
- Estimación de costo y tiempo ANTES de generar: panel en cada proyecto con
  el desglose por fase (IA, voz, imágenes, video, música, montaje), rangos en
  USD y minutos según tu configuración de proveedores e inputs.
- Versionado consecutivo del programa (v1, v2, v3…) con este registro de
  cambios visible desde la interfaz (clic en la versión).

## v0.10.0 — 2026-07-15
- Análisis PROFUNDO de videos de referencia por enlace (YouTube, Vimeo,
  Wistia…): guion/transcripción completa, ritmo de cortes medido (se aplica
  al ritmo visual del proyecto), capítulos y fotogramas para visión.
- Requiere yt-dlp (actualizar.bat lo instala). Sin él, se usan los metadatos
  públicos del enlace.

## v0.9.0 — 2026-07-15
- B-roll propio colocado por CONTEXTO: cada imagen/video se describe con
  visión IA y se asigna a la escena cuya narración ilustra. Lo que no encaja
  no se fuerza; lo que falta se genera.
- Música elegida con criterio de supervisor musical (títulos ID3 vs concepto
  del video); si ninguna pista encaja y hay Replicate, se genera a medida.
- Referencias nuevas: documentos (PDF, docx…) y enlaces web al crear proyecto.

## v0.8.1 — 2026-07-15
- Arreglado: la fase Música se colgaba indefinidamente con mp3 que traen
  carátula incrustada (Suno, iTunes…). Además, tiempo límite de seguridad.
- La tarjeta de error de un intento anterior se oculta mientras se genera.

## v0.8.0 — 2026-07-15
- Rótulos sincronizados con la narración (aparecen cuando el narrador dice
  la frase, con margen de entrada).
- Conclusiones como declaración tipográfica (líneas apiladas, mezcla de
  pesos, entrada escalonada).
- Clips de video en cámara lenta para cubrir la escena (nunca en bucle) y
  clips de 10 s cuando la escena es larga.
- Corte de voz preciso (no se come el inicio de la primera palabra).
- Fundido de cierre del audio al final del video.

## v0.7.0 — 2026-07-14
- Rótulos cinematográficos tipados (personaje, lugar, fecha, dato, lista,
  conclusión) con kicker dorado, animados y SOLO en momentos clave.
- Arco dramático musical: la intensidad de la música sube y baja con la
  historia; respiros con silencio donde la música respira.
- Efectos de sonido incidentales (whoosh, riser, boom) en cortes señalados.

## v0.6.0 — 2026-07-14
- Número exacto de escenas con video generativo (configurable) repartidas
  uniformemente — ya no queda al criterio del modelo.
- Kling por polling (sin timeouts de lectura) y reintentos automáticos ante
  el límite de velocidad de Replicate (429), visibles en el progreso.

## v0.5.1 — 2026-07-13
- Tamaños válidos automáticos para gpt-image-1; versiones de modelos de
  Replicate resueltas dinámicamente (adiós 404 por hashes caducados).
- El video generativo y la música degradan con aviso en vez de detener todo.

## v0.5.0 — 2026-07-13
- Presets de estilo (documental cinematográfico, cine épico, misterio…).
- Ritmo visual configurable (cada cuántos segundos cambia la imagen).
- La configuración de la interfaz se guarda en config.local.yaml (git pull
  ya no choca con tus ajustes).

## v0.4.0 — 2026-07-12
- Modo narración propia: tu voz grabada se usa TAL CUAL — limpieza de
  silencios, transcripción con tiempos y escenas alineadas a tu audio.

## v0.3.0 — 2026-07-12
- Subida de varios archivos por categorías (guion, voz, B-roll, referencia)
  con eliminación individual; se aceptan PDF, Word, PowerPoint, Excel, etc.
- Configuración de claves de API desde la interfaz.

## v0.2.1 — 2026-07-11
- Compatibilidad completa con Windows: fuentes, UTF-8, autodetección de
  ffmpeg, rutas en filtros. Lanzadores iniciar.bat / actualizar.bat.

## v0.2.0 — 2026-07-11
- Interfaz web local: crear proyectos, ver progreso por fases, storyboard,
  reanudar desde cualquier paso, video final y metadatos.

## v0.1.0 — 2026-07-10
- Sistema base: pipeline de 11 fases (análisis, concepto, guion, escenas,
  voz, B-roll, música, subtítulos, montaje, metadatos, publicación) con
  proveedores intercambiables (Claude, OpenAI, ElevenLabs, Replicate…).
