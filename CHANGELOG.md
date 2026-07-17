# Novedades de ytstudio

Cada ajuste publicado incrementa la versión. La versión activa se muestra
arriba a la izquierda en la interfaz (junto a la fecha de actualización).

## v16 — 2026-07-16
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

## v15 — 2026-07-16
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

## v14 — 2026-07-15
- Estimación de costo y tiempo ANTES de generar: panel en cada proyecto con
  el desglose por fase (IA, voz, imágenes, video, música, montaje), rangos en
  USD y minutos según tu configuración de proveedores e inputs.
- Versionado consecutivo del programa (v1, v2, v3…) con este registro de
  cambios visible desde la interfaz (clic en la versión).

## v13 — 2026-07-15
- Análisis PROFUNDO de videos de referencia por enlace (YouTube, Vimeo,
  Wistia…): guion/transcripción completa, ritmo de cortes medido (se aplica
  al ritmo visual del proyecto), capítulos y fotogramas para visión.
- Requiere yt-dlp (actualizar.bat lo instala). Sin él, se usan los metadatos
  públicos del enlace.

## v12 — 2026-07-15
- B-roll propio colocado por CONTEXTO: cada imagen/video se describe con
  visión IA y se asigna a la escena cuya narración ilustra. Lo que no encaja
  no se fuerza; lo que falta se genera.
- Música elegida con criterio de supervisor musical (títulos ID3 vs concepto
  del video); si ninguna pista encaja y hay Replicate, se genera a medida.
- Referencias nuevas: documentos (PDF, docx…) y enlaces web al crear proyecto.

## v11 — 2026-07-15
- Arreglado: la fase Música se colgaba indefinidamente con mp3 que traen
  carátula incrustada (Suno, iTunes…). Además, tiempo límite de seguridad.
- La tarjeta de error de un intento anterior se oculta mientras se genera.

## v10 — 2026-07-15
- Rótulos sincronizados con la narración (aparecen cuando el narrador dice
  la frase, con margen de entrada).
- Conclusiones como declaración tipográfica (líneas apiladas, mezcla de
  pesos, entrada escalonada).
- Clips de video en cámara lenta para cubrir la escena (nunca en bucle) y
  clips de 10 s cuando la escena es larga.
- Corte de voz preciso (no se come el inicio de la primera palabra).
- Fundido de cierre del audio al final del video.

## v9 — 2026-07-14
- Rótulos cinematográficos tipados (personaje, lugar, fecha, dato, lista,
  conclusión) con kicker dorado, animados y SOLO en momentos clave.
- Arco dramático musical: la intensidad de la música sube y baja con la
  historia; respiros con silencio donde la música respira.
- Efectos de sonido incidentales (whoosh, riser, boom) en cortes señalados.

## v8 — 2026-07-14
- Número exacto de escenas con video generativo (configurable) repartidas
  uniformemente — ya no queda al criterio del modelo.
- Kling por polling (sin timeouts de lectura) y reintentos automáticos ante
  el límite de velocidad de Replicate (429), visibles en el progreso.

## v7 — 2026-07-13
- Tamaños válidos automáticos para gpt-image-1; versiones de modelos de
  Replicate resueltas dinámicamente (adiós 404 por hashes caducados).
- El video generativo y la música degradan con aviso en vez de detener todo.

## v6 — 2026-07-13
- Presets de estilo (documental cinematográfico, cine épico, misterio…).
- Ritmo visual configurable (cada cuántos segundos cambia la imagen).
- La configuración de la interfaz se guarda en config.local.yaml (git pull
  ya no choca con tus ajustes).

## v5 — 2026-07-12
- Modo narración propia: tu voz grabada se usa TAL CUAL — limpieza de
  silencios, transcripción con tiempos y escenas alineadas a tu audio.

## v4 — 2026-07-12
- Subida de varios archivos por categorías (guion, voz, B-roll, referencia)
  con eliminación individual; se aceptan PDF, Word, PowerPoint, Excel, etc.
- Configuración de claves de API desde la interfaz.

## v3 — 2026-07-11
- Compatibilidad completa con Windows: fuentes, UTF-8, autodetección de
  ffmpeg, rutas en filtros. Lanzadores iniciar.bat / actualizar.bat.

## v2 — 2026-07-11
- Interfaz web local: crear proyectos, ver progreso por fases, storyboard,
  reanudar desde cualquier paso, video final y metadatos.

## v1 — 2026-07-10
- Sistema base: pipeline de 11 fases (análisis, concepto, guion, escenas,
  voz, B-roll, música, subtítulos, montaje, metadatos, publicación) con
  proveedores intercambiables (Claude, OpenAI, ElevenLabs, Replicate…).
