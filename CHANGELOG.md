# Novedades de ytstudio

Versionado semántico (SemVer): **Mayor.Menor.Revisión**.
- **Mayor**: cambios que rompen compatibilidad (aún en 0.x — programa de
  un solo usuario en desarrollo activo, puede cambiar sin previo aviso).
- **Menor**: funciones nuevas.
- **Revisión**: arreglos que no añaden función nueva.

La versión activa se muestra arriba a la izquierda en la interfaz (junto a la
fecha de actualización) — clic para ver este historial completo.

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
