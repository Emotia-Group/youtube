# Efectos de sonido y ambientes

## Efectos incidentales (`assets/sfx/`)
Archivos cuyo nombre EMPIEZA por el tipo se usan en lugar del sintetizado:
`whoosh*.wav`, `riser*.mp3`, `boom*.wav`, `pop*.wav`, `papel*.wav`,
`latido*.wav`. El director elige cuál va en cada corte según la narración;
el `pop` acompaña a los insertos documentales.

## Ambientes (`assets/sfx/ambientes/`)
Camas de fondo por tramo. El nombre debe EMPEZAR por el tipo:
`viento*.wav`, `multitud*.mp3`, `sala*.wav`, `lluvia*.wav`, `mar*.wav`,
`fuego*.wav`, `tension*.wav`.

Si no pones ninguno, el programa los **sintetiza en local** (gratis): suenan
sobrios y funcionan al volumen al que van (muy por debajo de la voz), pero
una grabación de campo real siempre suena mejor. Packs gratuitos: Freesound
(filtra por CC0), Mixkit, Pixabay Sounds.

Duración recomendada: 30-60 s por archivo — se repiten en bucle sin corte
audible hasta cubrir el tramo.
