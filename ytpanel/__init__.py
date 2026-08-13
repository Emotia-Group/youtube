"""ytpanel — Torre de Control: panel multicanal de YouTube (Fase 1).

Módulo hermano de ytstudio dentro del mismo repositorio. Conecta tus canales
por OAuth (un token por canal, da igual a qué cuenta de Google pertenezca),
sincroniza métricas de la Analytics API y la Data API a una base local, y las
muestra en una interfaz web con tarjetas por canal.

    python -m ytpanel ui        # abre http://localhost:8766
    python -m ytpanel sync      # sincroniza desde la terminal (cron/Programador)
"""
