# Plantillas de encuadre

## PLANTILLA_ZonaSegura_1080x1920.png

Guía de la **zona segura** del video vertical (Shorts, Reels, TikTok): un PNG
transparente de 1080×1920 que marca en verde el rectángulo donde puedes poner
texto sin que la interfaz de la app lo tape, y en rosa las franjas que NO son
tuyas — arriba el título, a la derecha la columna de botones y abajo el nombre
del canal y el **enlace al video largo**.

**El programa ya coloca los subtítulos dentro de la zona segura solo.** Esta
plantilla es para cuando edites algo A MANO en otro programa (Premiere,
DaVinci, CapCut): arrástrala a una pista por encima del video, coloca tu texto
dentro del rectángulo verde y **apaga esa pista antes de exportar**.

Para comprobarlo sobre un video ya hecho, pegándole las guías encima (necesita
ffmpeg):

```
ffmpeg -i "MI_VIDEO.mp4" -i "assets/plantillas/PLANTILLA_ZonaSegura_1080x1920.png" -filter_complex "overlay=0:0" -c:a copy "PRUEBA_zonasegura.mp4"
```

Mira el resultado **en un teléfono de verdad**, no en el ordenador: la
interfaz cambia entre iPhone y Android.
