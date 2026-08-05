# Novedades de ytstudio

Versionado semántico (SemVer): **Mayor.Menor.Revisión**.
- **Mayor**: cambios que rompen compatibilidad (aún en 0.x — programa de
  un solo usuario en desarrollo activo, puede cambiar sin previo aviso).
- **Menor**: funciones nuevas.
- **Revisión**: arreglos que no añaden función nueva.

La versión activa se muestra arriba a la izquierda en la interfaz (junto a la
fecha de actualización) — clic para ver este historial completo.

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
