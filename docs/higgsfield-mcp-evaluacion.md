# ¿Conectar ytstudio con Higgsfield vía MCP?

Evaluación técnica y económica — agosto 2026.
Pregunta del creador: *¿es posible, es más barato o más caro, cuánto cuesta
incorporarlo y sería más rápido o más lento que lo que hacemos hoy?*

> **Nota posterior (v0.58.0).** Al revisar el resto del mercado apareció un
> dato que debilita todavía más el caso de Higgsfield: **la API de Sora 2 se
> apaga el 24 de septiembre de 2026**, así que «acceso a Sora 2» dejó de ser
> un argumento a su favor. Y **Veo 3.1** —la otra razón que se apuntaba abajo—
> ya está integrado por API directa desde la v0.58.0, sin pasar por créditos
> de suscripción. Ver `panorama-modelos-2026.md`.

**Respuesta corta:** es posible, pero **no por MCP**. MCP es un protocolo para
que un *agente conversacional* llame herramientas; nuestro pipeline no es un
agente, es un programa Python que genera ~100 imágenes en paralelo con
contabilidad de gasto al centavo. Encajar MCP ahí es meter un intérprete
humano en una cadena de montaje. Y en dinero, con el catálogo actual,
Higgsfield sale **más caro por imagen** y, sobre todo, **te pone un techo
mensual de videos** que hoy no tienes.

Recomendación: **no integrar ahora**. Si algún día se integra, que sea por
HTTP directo contra su API, no por MCP, y solo por los modelos que Replicate
no tenga (Sora 2, Veo 3.x, Soul).

---

## 1. Qué hacemos hoy

El pipeline resuelve las imágenes y el video en `ytstudio/providers/`, con una
interfaz mínima por proveedor:

| Categoría | Fábrica | Contrato |
|---|---|---|
| Imágenes | `get_images(cfg)` | `generate(prompt, out) -> Path` |
| Video IA | `get_videogen(cfg)` | `generate(prompt, out, image, seconds) -> Path` |
| Lipsync | `get_lipsync(cfg)` | clip de personaje |

Cada proveedor concreto (`ReplicateImages`, `OpenAIImages`, `ReplicateVideo`)
hace tres cosas antes de devolver el archivo:

1. Consulta la tarifa en `ytstudio/pricing.py` (USD por imagen / por clip).
2. Pide permiso al tope de gasto (`usage.check_budget`).
3. Anota el gasto real (`usage.record` + `usage.add_spend`).

Ese triángulo —tarifa conocida, tope dinámico, gasto anotado— es lo que
sostiene el presupuesto automático del `config.yaml` (`budget.margin`,
`min_usd`, `max_usd`) y la estimación previa de `estimate.py`.

Y la fase de B-roll (`ytstudio/phases/broll.py`) llama a `generate()` desde un
pool de hilos: `performance.parallel_images: 4`, `parallel_video: 2`.

### Costo real de un documental de 10 minutos

Con `scene_seconds: 6` → ~100 escenas → ~100 imágenes IA:

| Concepto | Modelo actual | Costo |
|---|---|---|
| 100 imágenes B-roll | FLUX 1.1 Pro (Replicate) | **$4.00 – $5.00** |
| Correcciones del control factual | ~10-15 % regeneradas | +$0.40 – $0.75 |
| Clips de video IA | apagado (`videogen.name: none`) | $0 |
| *(si se encendieran 10 clips)* | Kling v1.6 std | +$1.30 – $3.50 |

Tiempo: 8-25 s por imagen ÷ 4 en paralelo ≈ **3-10 minutos** de reloj para el
B-roll completo.

---

## 2. Qué ofrece Higgsfield

Higgsfield es una **plataforma por suscripción con créditos**, no un proveedor
de infraestructura con precio por llamada. Expone tres puertas:

- **MCP alojado** en `https://mcp.higgsfield.ai/mcp` — herramientas de
  generación de imagen y video, entrenamiento de personajes (Soul), historial.
  Autenticación contra tu cuenta Higgsfield; consume los créditos de tu plan.
- **CLI** (`higgsfield.ai/cli`), pensada igualmente para agentes.
- Acceso tipo API expuesto por reventas/agregadores.

El catálogo sí es su punto fuerte: Sora 2, Veo, Kling 3.0, Seedance 2.0,
GPT Image 2, Nano Banana Pro, Flux 2, Soul. Es un supermercado de modelos
frontera bajo un solo saldo.

### Planes y precio del crédito

| Plan | Precio/mes | Créditos | USD/crédito |
|---|---|---|---|
| Starter | $15 | 200 | ~$0.075 |
| Plus | $39 | 1 000 | ~$0.039 |
| Ultra | $99 | 3 000 (hasta 9 000 según paquete) | ~$0.033 |

**Los créditos no se acumulan de un mes al otro.** Lo que no gastas, se pierde.

---

## 3. ¿Más barato o más caro?

Tomando el mejor caso (Ultra, $0.033/crédito):

### Imágenes — **más caro**

| Vía | Por imagen | 100 imágenes |
|---|---|---|
| FLUX 1.1 Pro (hoy) | $0.040 – $0.050 | **$4.00 – $5.00** |
| FLUX schnell (ya soportado) | $0.003 – $0.004 | $0.30 – $0.40 |
| Higgsfield · Nano Banana Pro (~2 cr) | ~$0.066 | **~$6.60** |

Entre **30 % y 65 % más caro** por imagen que nuestro FLUX actual, y eso
midiéndolo en el plan más caro. En Starter el crédito vale más del doble y la
imagen se va a ~$0.15.

### Video — **empatado**

| Vía | Clip 5 s | 
|---|---|
| Kling v1.6 std (Replicate, hoy) | $0.13 – $0.35 |
| Higgsfield · Kling 3.0 720p (~6 cr) | ~$0.20 |
| Higgsfield · Sora 2 / Veo 3.1 (40-70 cr) | **$1.30 – $2.30** |

Kling por Higgsfield está dentro de nuestro rango actual. Sora 2 y Veo cuestan
5-10× nuestro clip, pero eso **no es un sobreprecio de Higgsfield**: es lo que
valen esos modelos en cualquier lado. Ahí Higgsfield aporta acceso, no ahorro.

### El problema real no es el precio unitario: es el techo

Un documental de 10 min consume ~200 créditos solo en B-roll. Eso significa:

| Plan | Videos/mes que soporta |
|---|---|
| Starter ($15) | **1** |
| Plus ($39) | ~5 |
| Ultra ($99) | ~15 |

Hoy, con Replicate, no hay techo: pagas $4-5 por video y produces 3 o 50 sin
pedirle permiso a nadie. Cambiar a créditos convierte un costo variable en una
cuota fija con muro al final del mes — justo lo contrario de lo que necesita un
sistema de producción en volumen. Y si un mes produces poco, pagaste igual.

---

## 4. ¿Más rápido o más lento?

**Igual de rápido en el modelo, más lento en el pipeline.** Los modelos son los
mismos (Kling es Kling, Flux es Flux); el tiempo de cómputo no cambia. Lo que
cambia es todo lo que rodea a la llamada:

| Factor | Hoy (SDK directo) | Vía MCP |
|---|---|---|
| Paralelismo | 4 imágenes simultáneas, hilos Python | El protocolo es conversacional: una herramienta por turno. Recuperar las 4 vías exige un cliente MCP propio con sesiones concurrentes |
| Espera del resultado | `replicate.run()` bloquea y descarga | Trabajo asíncrono → sondeo del estado + descarga aparte |
| Sobrecarga por llamada | ninguna | handshake JSON-RPC, sesión, reintentos |

Si se integrara MCP con el paralelismo intacto, el B-roll tardaría
prácticamente lo mismo (±10 %). Si se integrara de la forma natural —una
herramienta cada vez, como lo usa un agente— los mismos 3-10 minutos se
convertirían en **20-40 minutos**. Higgsfield no acelera nada; en el mejor de
los casos no estorba.

---

## 5. ¿Cuánto cuesta incorporarlo?

Depende radicalmente de por dónde se entre.

### Opción A — HTTP directo contra su API · **~1 día**

Es la que encaja con la casa. La abstracción de proveedores ya está hecha para
esto:

- `ytstudio/providers/images.py` → nueva clase `HiggsfieldImages` con
  `generate(prompt, out)` (~120-150 líneas, calcada de `ReplicateImages`).
- `ytstudio/providers/videogen.py` → `HiggsfieldVideo` (~60 líneas).
- `ytstudio/providers/__init__.py` → registrar `"higgsfield"` en las fábricas y
  añadir `HIGGSFIELD_API_KEY` a `_REQUIRED_KEYS` (degradación a mock incluida).
- `ytstudio/pricing.py` → tarifas de sus modelos.
- `config.yaml` + `MANUAL.md` → documentar la opción.

Sin cambios en `broll.py`, `assembly.py` ni en el resto del pipeline. El
paralelismo, el tope de gasto y los reintentos siguen funcionando tal cual.

**El punto pegajoso: la contabilidad.** `pricing.py` habla en USD por unidad y
`budget.py` corta cuando el gasto estimado se pasa. Higgsfield cobra en
créditos de una bolsa mensual. Hay que traducir crédito→USD con el precio del
plan del creador (un campo nuevo en el config, `providers.images.usd_per_credit`)
y aceptar que el tope de gasto pasa a ser una aproximación. Es resoluble, pero
es trabajo de verdad y degrada una garantía que hoy es exacta.

### Opción B — vía MCP · **~4-6 días, y no lo recomiendo**

Además de todo lo anterior:

- No tenemos cliente MCP: hay que añadir dependencia y ciclo de vida de sesión
  a un programa que hoy solo habla SDKs REST.
- La autenticación del MCP alojado va contra la cuenta Higgsfield, con flujo de
  navegador — incompatible con `iniciar.bat` / ejecución desatendida / cron del
  panel.
- Las herramientas MCP devuelven texto y referencias pensadas para que las lea
  un modelo, no rutas de archivo. Hay que interpretar respuestas semiestructuradas
  y descargar aparte, con lo que eso trae de fragilidad.
- Los reintentos por límite de peticiones que hoy salvan un proyecto a medias
  (ver `_rate_limit_wait` en `images.py`, escrito tras perder 8 imágenes ya
  pagadas) habría que reconstruirlos sobre otra semántica de error.

MCP resuelve un problema que no tenemos. Nuestro programa ya sabe *qué* imagen
quiere: el director de arte escribió el prompt tres fases antes. No necesita un
protocolo para que un agente descubra herramientas en tiempo de ejecución;
necesita una función que reciba un prompt y devuelva un PNG.

---

## 6. Veredicto

**No integrar por ahora.** Razones, en orden:

1. **Es más caro por imagen** (~+30-65 %) que FLUX 1.1 Pro, que es exactamente
   donde está el 90 % de nuestro gasto de generación.
2. **Introduce un techo mensual de producción** donde hoy hay costo variable sin
   límite. Es un cambio de modelo de negocio, no de proveedor.
3. **No aporta velocidad.** Mismos modelos, más capas.
4. **MCP es el protocolo equivocado** para un pipeline por lotes con
   paralelismo y contabilidad al centavo.

**Cuándo sí reconsiderarlo:** si el creador quiere Sora 2, Veo 3.1 o los
personajes Soul para escenas clave —cosas que Replicate no ofrece o no con esa
calidad—. En ese caso la vía es la **Opción A**, y solo para `videogen`, dejando
las ~100 imágenes de B-roll en FLUX. Un puñado de clips premium por video
($1.30-$2.30 cada uno) sobre una base barata es una mezcla sensata; mover todo
el catálogo a créditos no lo es.

**Alternativa de mayor rendimiento inmediato:** si el objetivo era abaratar, la
palanca ya está en casa y no cuesta ni una línea de código —
`providers.images.model: black-forest-labs/flux-schnell` baja las 100 imágenes
de $4-5 a **$0.30-0.40**, aunque con pérdida de fotorrealismo. Y para calidad
sin cambiar de plataforma, `google/imagen-4-fast` ($0.02-0.03) o
`bytedance/seedream-4` ya están tarifados en `pricing.py`.

---

### Fuentes

- [Higgsfield MCP (sitio oficial)](https://higgsfield.ai/mcp) ·
  [Higgsfield CLI](https://higgsfield.ai/cli)
- [Higgsfield MCP: Agentic Image and Video Generation — MCP.Directory](https://mcp.directory/blog/higgsfield-mcp-guide)
- [Higgsfield MCP: Sora, Veo, Kling from Claude Code — claudefa.st](https://claudefa.st/blog/tools/mcp-extensions/higgsfield-mcp)
- [Higgsfield Pricing 2026 — Scopeful](https://www.scopeful.org/tools/higgsfield)
- [Higgsfield AI Pricing in 2026 — imagine.art](https://www.imagine.art/blogs/higgsfield-ai-pricing)
- [Higgsfield AI Review 2026: Pricing, Credits & Alternatives — gstory.ai](https://www.gstory.ai/blog/higgsfield-ai/)
- [Higgsfield AI Pricing 2026 — layer3labs](https://www.layer3labs.io/guides/higgsfield-ai-pricing)

*Los precios en créditos provienen de fuentes de terceros: el sitio oficial de
Higgsfield está bloqueado por el proxy de red de este entorno, así que las
tarifas por modelo no pudieron verificarse contra la documentación primaria.
Conviene confirmarlas en su panel antes de tomar la decisión final.*
