# Panorama de modelos que aún no tenemos

Inventario de lo que usa ytstudio hoy frente a lo que existe en el mercado —
agosto 2026. Para decidir qué añadir, qué cambiar y qué hay que arreglar ya.

> **Estado: aplicado en la v0.58.0.** Las nueve acciones de la sección 8 están
> implementadas. Este documento se conserva como el razonamiento que llevó a
> esas decisiones y como base para la próxima revisión del mercado. Lo único
> que quedó fuera está anotado al final, en «Lo que no se implementó».

---

## 0. URGENTE — dos modelos que usamos se apagan

Esto no es una oportunidad, es una avería programada. Ambos están en el código
y en el catálogo de la interfaz.

| Modelo | Dónde está | Se apaga | Consecuencia |
|---|---|---|---|
| **Imagen 4 Fast** (`google/imagen-4-fast`) | `catalog.py` (opción de la UI), `pricing.py` | **17 ago 2026** *(en 3 días)* | Todo proyecto configurado con él deja de generar |
| **gpt-image-1** | `images.py` → `OpenAIImages.MODEL`, **codificado a fuego** | **23 oct 2026** | Muere el proveedor OpenAI de imágenes **y con él las escenas con TEXTO LEGIBLE** (`_shows_text` en `broll.py:1596`), que hoy dependen exclusivamente de él |

El segundo es el grave: la ruta de texto legible no tiene alternativa. Hoy
`broll.py` abre un segundo cliente `OpenAIImages(cfg)` sólo para carteles,
periódicos y lápidas. El 23 de octubre esa función desaparece sin sustituto.

**Reemplazos directos:**

- `imagen-4-fast` → `google/nano-banana` (que ya usamos como `ref_model`) o
  FLUX schnell si lo que se buscaba era el precio.
- `gpt-image-1` → **GPT Image 2** ($0.005–$0.21/img según tamaño y calidad;
  ~$0.03–$0.06 en el rango que usaríamos). Mejor renderizado de texto que su
  antecesor, sin el tinte amarillento, y salida 2K nativa. Migración barata:
  cambiar la constante `MODEL` y revisar tamaños admitidos.
- Alternativa sin OpenAI para texto legible: **Nano Banana Pro**
  (`gemini-3-pro-image`, ~$0.134/img a 1-2K), hoy el mejor en tipografía dentro
  de imagen junto a GPT Image 2.

---

## 1. Imágenes

### Lo que ya tenemos

FLUX 1.1 Pro · FLUX dev · FLUX schnell · SDXL Lightning · Imagen 4 Fast †
· Recraft v3 · SD 3.5 Large · gpt-image-1 † · nano-banana, seedream-4,
flux-kontext-pro (identidad). † *se apagan, ver arriba.*

### Lo que falta

| Modelo | Precio/img | ✚ Pros | ✖ Contras | ¿Vale la pena? |
|---|---|---|---|---|
| **FLUX 2 Pro** | ~$0.055 (1MP; **cobra por megapíxel** — 4MP cuesta 4×) | Sucesor directo de nuestro caballo de batalla; mejor coherencia y detalle | Más caro que 1.1 Pro; el cobro por MP puede dispararse sin querer | **Sí** — probar contra 1.1 Pro |
| **FLUX 2 Flash** | por debajo de Pro | Rápido y barato dentro de la familia FLUX | Menos detalle fino | Sí, como nuevo "modo prueba" |
| **GPT Image 2** | $0.005–$0.21 | El mejor texto dentro de imagen; ultrapanorámicas 3:1; 2K nativo | Caro en calidad alta | **Sí, obligatorio** (sustituto de gpt-image-1) |
| **Nano Banana Pro** (`gemini-3-pro-image`) | $0.134 (1-2K) · $0.24 (4K) | Identidad de **hasta 5 sujetos** a la vez; supera a flux-kontext en consistencia de personaje; excelente texto | 3× nuestro costo actual por imagen | **Sí, pero solo como `ref_model`** para escenas de elenco |
| **Seedream v4** | ~$0.03 | Barato, multi-referencia, buena fidelidad | — | Ya está como `ref_model`; **falta como modelo general** |
| **Qwen Image Max** | ~$0.075 | Estética alternativa, fuerte en texto asiático | Caro para lo que aporta | No |
| **Recraft V4.1** | ~$0.03–0.04 | Sucesor de Recraft v3 (que sí tenemos) | Sigue sin buscar fotorrealismo | Actualizar la versión, nada más |
| **Ideogram Turbo** | ~$0.03 | Muy bueno en tipografía, barato | Menos "cine" | Alternativa económica para texto legible |

**Lectura:** el mercado se ha estabilizado en **$0.03–$0.04 por imagen de 1MP**
— justo donde ya estamos con FLUX 1.1 Pro. **No hay ahorro estructural
disponible en imágenes**: lo que hay es un cambio de guardia (FLUX 2, GPT Image
2) y una mejora real en consistencia de personaje (Nano Banana Pro).

---

## 2. Video generativo

### Lo que ya tenemos
Kling v2.1 · Kling v1.6 standard · Wan 2.2 i2v · Hailuo 02 · Seedance 1 Lite
· LTX Video. *(hoy apagado: `videogen.name: none`)*

### Lo que falta

| Modelo | Precio | ✚ Pros | ✖ Contras |
|---|---|---|---|
| **Veo 3.1 Fast** | $0.15/s (~$0.75 por 5 s) | **Audio nativo en el clip** — único del mercado; el resto exige pista aparte | 3-5× nuestro Kling actual |
| **Veo 3.1 Standard** | $0.40/s (~$2/clip) | 4K nativo, el mejor lipsync del mercado, audio incluido | Carísimo para 100 escenas |
| **Veo 3.1 Lite** 1080p | $0.05/s (~$0.25/clip) | **Compite en precio con Kling** con marca Google | Sin audio nativo en este tramo |
| **Kling 3.0** | $0.09–$0.14/s | Mejor seguimiento de sujeto y consistencia de movimiento que la v2 | Precio por segundo, no por clip |
| **Seedance 2.0** | ~$0.09/s | La mejor calidad por dólar en volumen | **Sin API oficial** — ByteDance la retrasó; solo por terceros |
| **Wan 2.6** | open source (coste de cómputo) | Gratis en peso, dominante en volumen alto | Requiere hospedarlo o un proveedor |
| **Sora 2** | ~$0.10/s | Calidad consistente, bien documentado | ⚠ **La API se apaga el 24 sep 2026** |
| **Runway Gen-4** | variable | Control de cámara fino | Caro, orientado a suite propia |

**Hallazgo clave — Veo 3.1 con audio nativo.** Es la única novedad que cambia
*qué puede hacer* el programa, no solo cuánto cuesta. Hoy cada escena de video
sale muda y el sonido lo arma `utils/sfx.py` + `utils/ambience.py` en local. Un
clip Veo trae su propio ambiente sincronizado con la imagen. Para 3-5 escenas
clave por documental serían **$2.25–$3.75** extra — asumible, y con un salto de
producción visible.

**⚠ Corrección al informe de Higgsfield (`higgsfield-mcp-evaluacion.md`).** Ahí
recomendé reconsiderar Higgsfield "si quieres Sora 2, Veo 3.1 o Soul". **Sora 2
deja de existir el 24 de septiembre**, así que ese argumento se cae solo. Y Veo
3.1 está disponible por API directa sin pasar por créditos de suscripción. El
caso a favor de Higgsfield queda reducido a Soul y a Seedance 2.0 — que
justamente no tiene API oficial y es el único hueco real que una plataforma
agregadora puede taparte hoy.

---

## 3. Voz (TTS)

### Lo que ya tenemos
ElevenLabs `eleven_multilingual_v2` · OpenAI `gpt-4o-mini-tts` · Edge TTS
(gratis) · mock.

### Lo que falta

| Proveedor | Precio/millón car. | ✚ Pros | ✖ Contras |
|---|---|---|---|
| **ElevenLabs v3** | ~$120 | 70+ idiomas, la mejor expresividad; **actualización directa** de lo que ya usamos | Caro; nuestro código fija `eleven_multilingual_v2` a mano |
| **ElevenLabs Flash/Turbo** | ~$60 | Mitad de precio dentro del mismo proveedor | Menos matiz emocional |
| **Cartesia Sonic 4** | ~$11 | **Hasta 27× más barato que ElevenLabs**; latencia ~40 ms | Menos catálogo de voces en español |
| **Deepgram Aura-2** | ~$30 | Opción on-premise, precio predecible | Solo 7 idiomas |
| **Hume Octave 2** | variable | Líder en fidelidad emocional — interesante para documental | Ecosistema pequeño |
| **Inworld TTS** | variable | Señalado como el más realista en matiz sutil | Menos maduro |
| **MiniMax Speech** | bajo | 300+ voces, 30+ idiomas | Fuerte en chino, español correcto sin destacar |

**Lectura:** aquí **sí hay ahorro grande**. Un documental de 10 min son ~9 000
caracteres de narración. Con ElevenLabs son ~$1.08; con **Cartesia, ~$0.10**.
No mueve la aguja en un video suelto, pero a 50 videos/mes son $54 contra $5.
Y el detalle importante: ElevenLabs cobra por plan de suscripción, no por
llamada — por eso `tts.py` registra los caracteres con **coste $0.00** y el
gasto real queda fuera del presupuesto. Cartesia, al ser pago por uso, lo
devolvería a la contabilidad honesta.

---

## 4. Transcripción (STT)

### Lo que tenemos
OpenAI `whisper-1` ($0.006/min). Se usa para analizar videos de referencia y
para alinear la narración propia.

### Lo que falta

| Proveedor | Precio/min | ✚ Pros | ✖ Contras |
|---|---|---|---|
| **AssemblyAI (batch)** | **$0.0025** | 2.4× más barato que Whisper; marcas de tiempo por palabra excelentes | Sin streaming en ese precio (no lo necesitamos) |
| **Deepgram Nova-3** | $0.0043 | Más rápido, muy preciso, streaming disponible | Algo más caro que AssemblyAI |
| **Whisper large-v3 turbo** | gratis (local) | 5.4× más rápido que large-v3; **coste cero** si corre en tu máquina | Necesita GPU decente; sin GPU es más lento que la API |
| **Gemini / GPT-4o audio** | variable | Entiende contexto, corrige términos mientras transcribe | Más caro; parte del trabajo ya lo hace `polish_transcript` |

**Lectura:** el gasto en STT es marginal (12 min de referencia = $0.07). La
mejora real no es el precio sino la **calidad de las marcas de tiempo por
palabra**, que es de lo que vive `utils/align.py` y todo el sistema de
respiraciones y recorte de pausas. AssemblyAI es mejor ahí y encima más barato.
Y **Whisper turbo en local** eliminaría el coste y la dependencia de red por
completo.

---

## 5. Música

### Lo que tenemos
Biblioteca local (`assets/music`, gratis, con montaje por actos) · MusicGen por
Replicate ($0.05–$0.15/pista) · mock.

### Lo que falta

| Opción | Precio | ✚ Pros | ✖ Contras |
|---|---|---|---|
| **ElevenLabs Music** | por créditos del plan | **Licencia comercial limpia**, cerrada antes del lanzamiento; API oficial | Calidad a veces un paso por detrás de Suno |
| **Stable Audio** | comercial de Stability | Términos comerciales claros | Menos pegadizo |
| **Suno v4.5 / v5** | $10–$30/mes | La mejor calidad del mercado | **Sin API pública** y **licencia en disputa judicial** (demandas por datos de entrenamiento, abiertas a abril 2026) |
| **Udio** | suscripción | Calidad preferida por músicos | Sin API pública; misma incertidumbre legal |
| **Google Lyria** | variable | Respaldo de Google | Acceso limitado |

**Lectura:** para un canal de YouTube que monetiza, **la licencia importa más
que la calidad**. Suno y Udio están fuera por dos motivos independientes: no
tienen API y su situación legal no está resuelta. **ElevenLabs Music es el
único candidato serio** para sustituir a MusicGen — y si ya se paga ElevenLabs
para voz, comparte saldo.

---

## 6. Personaje narrador (lipsync)

### Lo que tenemos
SadTalker ($0.005–$0.02/s) · Sonic ($0.02–$0.05/s) · OmniHuman ($0.10–$0.16/s).

### Lo que falta

| Modelo | Precio/s | ✚ Pros | ✖ Contras |
|---|---|---|---|
| **OmniHuman 1.5** | $0.16 | Control de cámara por prompt (paneo, movimiento) | Lento: ~118 s por clip |
| **Kling AI Avatar Pro** | $1 los primeros 5 s, luego $0.20/s | Calidad alta, hasta 600 s | El más caro |
| **Hedra** | ~50 % menos que sus rivales | Buen equilibrio precio/calidad | Menos control fino |
| **HeyGen** | ~$0.14 | Gana en precio dentro de la gama alta; 40+ idiomas | Orientado a avatares de catálogo |
| **VEED Fabric 1.0** | variable | Gana en velocidad y realismo en pruebas comparadas (63 s vs 118 s de OmniHuman) | Proveedor más pequeño |
| **InfiniteTalk** | variable | **Multi-personaje**: dos audios → dos personajes hablando | Nicho |
| **Veo 3.1 Standard** | $0.40/s | Señalado como el mejor lipsync del mercado, con audio | Precio de otra liga |

**Lectura:** nuestra escalera (SadTalker barato → Sonic → OmniHuman caro) sigue
siendo razonable. La única incorporación con argumento es **Hedra**, que se
mete entre Sonic y OmniHuman por la mitad de precio de este último.

---

## 7. Lo que no tenemos como *categoría*

Aquí están las oportunidades que no son "cambiar de modelo" sino "hacer algo
que hoy no hacemos".

| Categoría | Modelos | Qué aportaría | Encaje |
|---|---|---|---|
| **Escalado (upscaling)** | Real-ESRGAN (Replicate, centavos) · Topaz Starlight/Proteus ($299/año o ~$0.01/s por API) | Generar el B-roll a 1MP (barato) y **subirlo a 1080p/4K al final**. Bajaría el coste por imagen manteniendo la entrega en HD | Fase nueva entre B-roll y montaje. **La palanca de ahorro más limpia que encontré** |
| **Interpolación de fotogramas** | FILM · RIFE (Replicate, centavos) | Clips de video IA generados a 12-16 fps y llevados a 24 fps; Ken Burns más suave | Encaja en `assembly.py` |
| **Audio nativo en video** | Veo 3.1 | Ambiente sincronizado con la imagen sin sintetizarlo | Sustituiría parcialmente `utils/ambience.py` en escenas clave |
| **Restauración de material de archivo** | Topaz, GFPGAN | Las fotos reales de Wikimedia que usa `utils/elements.py` suelen venir en baja resolución | Mejora directa de los insertos documentales |

**El escalado merece un párrafo propio.** Hoy pagamos FLUX 1.1 Pro ($0.04) por
100 imágenes = $4-5. Si generáramos con **FLUX schnell** ($0.003) y escaláramos
con Real-ESRGAN (~$0.002/img), las mismas 100 imágenes costarían **~$0.50**: un
ahorro del 90 %. La contrapartida es real —el escalado recupera resolución, no
inventa la microtextura y el detalle de iluminación que hacen "cine" a FLUX
Pro— así que no sirve para todas las escenas. Pero como ruta híbrida (escenas
de relleno en schnell+upscale, escenas clave en Pro) es la idea con mejor
relación beneficio/riesgo de todo este documento.

---

## 8. Qué haría yo, en orden

| # | Acción | Esfuerzo | Beneficio |
|---|---|---|---|
| 1 | **Migrar `gpt-image-1` → GPT Image 2** y retirar `imagen-4-fast` | 2-3 h | **Evita dos averías con fecha.** Sin esto, el 23 de octubre se cae la generación de texto legible |
| 2 | **Prueba híbrida schnell + Real-ESRGAN** contra FLUX Pro | 1 día | Hasta −90 % en la partida más cara. Decidir con las imágenes delante, no con la tabla |
| 3 | **Cartesia como opción de TTS** | 3-4 h | −90 % en voz y devuelve el gasto de voz al presupuesto |
| 4 | **AssemblyAI o Whisper turbo local para STT** | 3-4 h | Mejores marcas de tiempo por palabra → mejor respiración y recorte de pausas |
| 5 | **Veo 3.1 Fast en `videogen`** para 3-5 escenas clave | 4-6 h | Audio nativo: capacidad nueva, no solo precio |
| 6 | **Nano Banana Pro como `ref_model`** | 2 h | Identidad de hasta 5 personajes; el salto de calidad más visible en escenas de elenco |
| 7 | **FLUX 2 Pro / Flash al catálogo** | 1-2 h | Mantenerse al día; medir contra 1.1 Pro |
| 8 | **ElevenLabs Music** en lugar de MusicGen | 3-4 h | Licencia comercial limpia para un canal que monetiza |
| 9 | **Hedra** en la escalera de lipsync | 2 h | Cubre el hueco entre Sonic y OmniHuman |

Los puntos 1, 7 y 9 son casi solo entradas nuevas en `catalog.py` y `pricing.py`
—la abstracción de proveedores aguanta sin tocarse—. Los puntos 2 y 5 son los
que de verdad cambian el producto: uno el coste, el otro lo que el video puede
llegar a ser.

---

## 9. Lo que no se implementó (y por qué)

La v0.58.0 aplicó las nueve acciones. Dos matices honestos sobre el alcance:

- **El audio nativo de Veo se guarda, pero todavía no se mezcla solo.** El
  proveedor pide el clip, detecta que trae sonido y lo extrae a un archivo
  junto al vídeo (`scene_XXX_amb.m4a`). Lo que aún no ocurre es que esa pista
  entre automáticamente en la mezcla final: la cama de ambiente se construye
  como un único WAV para todo el vídeo desde la fase de música, y empalmar ahí
  el sonido de una escena concreta exige el mapa de tiempos exacto del montaje.
  Es un cambio en el mezclador de audio, que es la pieza más delicada del
  programa, y no era verificable sin generar clips reales. Se dejó para una
  revisión propia, con el material delante.
- **Whisper large-v3 turbo en local** (coste cero) se descartó frente a
  AssemblyAI: exige GPU y añadiría peso de instalación a un programa que hoy
  arranca con `pip install` y poco más. AssemblyAI da la mejora de tiempos por
  palabra sin tocar los requisitos.

Fuera de eso, **Topaz** quedó descartado por su modelo de suscripción ($299 al
año frente a los centavos de Real-ESRGAN por proyecto), y **Seedance 2.0** por
no tener API oficial — es, junto a Soul, lo único que hoy justificaría mirar a
una plataforma agregadora.

---

### Fuentes

**Imágenes** · [AI Image Model Pricing normalizado (invideo)](https://invideo.io/blog/ai-image-model-pricing/) · [Price Per Token — imagen](https://pricepertoken.com/image) · [buildmvpfast — costes de imagen](https://www.buildmvpfast.com/api-costs/ai-image) · [GPT Image 2 explicado](https://invideo.io/blog/gpt-image-ai-image-generator/) · [GPT Image 1 vs 1.5 vs 2: migración](https://unifically.com/blogs/gpt-image-1-vs-1.5-vs-2) · [Nano Banana Pro — API y precios](https://pricepertoken.com/pricing-page/model/google-gemini-3-pro-image-preview)

**Apagados** · [Imagen 4: cierre 17 ago 2026](https://kingy.ai/ai-launch-tracker/google-will-shut-down-three-imagen-4-api-models-august-17/) · [Guía de migración de Imagen (Firebase)](https://firebase.google.com/docs/ai-logic/imagen-models-migration) · [Deprecaciones de OpenAI](https://developers.openai.com/api/docs/deprecations) · [Qué saber sobre la discontinuación de Sora](https://help.openai.com/en/articles/20001152-what-to-know-about-the-sora-discontinuation)

**Video** · [Veo 3.1 vs Kling 3.0 vs Sora 2 — costes de API](https://modelslab.com/blog/api/veo-3-1-vs-kling-3-sora-2-ai-video-api-cost-2026) · [AI Video API Pricing 2026 (CometAPI)](https://www.cometapi.com/ai-video-api-pricing/) · [Seedance vs Sora vs Kling vs Veo](https://devtk.ai/en/blog/ai-video-generation-pricing-2026/) · [APIs de video más baratas](https://www.atlascloud.ai/blog/tips/cheapest-ai-video-generation-api-2026)

**Voz y transcripción** · [Mejores APIs de TTS 2026 (futureagi)](https://futureagi.com/blog/best-text-to-speech-providers-2026/) · [Deepgram — mejores APIs de TTS](https://deepgram.com/learn/best-text-to-speech-apis-2026) · [APIs de STT 2026 comparadas](https://futureagi.com/blog/speech-to-text-apis-in-2026-benchmarks-pricing-developer-s-decision-guide/) · [buildmvpfast — transcripción](https://www.buildmvpfast.com/api-costs/transcription)

**Música** · [Suno, Udio, ElevenLabs comparados](https://www.digitalapplied.com/blog/ai-music-generation-platforms-suno-udio-elevenlabs-2026) · [Mejor API de música 2026](https://musicapi.ai/blog/best-ai-music-api-2026)

**Lipsync y realce** · [Mejor API de lipsync 2026 (VEED)](https://www.veed.io/learn/best-lipsync-api) · [Modelos de avatar y lipsync (WaveSpeed)](https://wavespeed.ai/collections/avatar-lipsync) · [Replicate — mejora de video](https://replicate.com/collections/ai-enhance-videos) · [Topaz Video AI 2026](https://unifab.ai/resource/topaz-video-ai-review)

*Nota: los precios provienen de comparativas de terceros y de la documentación
pública de cada proveedor; cambian con frecuencia. Confirma la tarifa vigente
antes de fijar cualquiera en `pricing.py`. Las fechas de apagado de Imagen 4 y
gpt-image-1 sí están confirmadas en documentación oficial de Google y OpenAI.*
