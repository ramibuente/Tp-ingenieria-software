# Resumen SRS + PGP

## Producto

Aplicacion web de analisis estadistico deportivo para transformar datos historicos de futbol en dashboards comprensibles. El sistema ayuda a tomar decisiones basadas en estadisticas, pero no permite apostar ni garantiza resultados.

## Usuarios

- Analista o tomador de decisiones: consulta dashboards, filtros y comparaciones.
- Administrador: carga y actualiza CSV.
- Equipo de desarrollo: mantiene pipeline, KPIs e interfaz.

## Modulos

- Carga de datos.
- Validacion de estructura.
- Control de calidad y limpieza.
- Relacion de tablas.
- KPIs de equipos.
- KPIs de jugadores.
- KPIs de arbitros.
- Visualizacion en dashboards.

## Requisitos funcionales prioritarios

- Cargar CSV.
- Detectar errores de estructura, nulos, duplicados e inconsistencias.
- Relacionar clubes, partidos, jugadores, apariciones y eventos por IDs.
- Calcular KPIs basicos y compuestos.
- Comparar dos equipos.
- Visualizar historial Head-to-Head.
- Filtrar por equipo, jugador, arbitro, competicion, temporada o partido.

## Riesgos principales

- Datos incompletos o inconsistentes.
- Datos desactualizados.
- Falta de disponibilidad del equipo.
- Cambios en requerimientos.
- Interpretacion incorrecta de probabilidades.
- Restricciones legales vinculadas con apuestas.

