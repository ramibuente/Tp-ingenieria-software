# Matriz de requisitos

Esta matriz vincula los requisitos del SRS/PGP con la implementacion actual. Cuando un indicador depende de datos historicos y no de fixtures futuros, se implementa como comparacion previa entre dos equipos.

## Requisitos funcionales

| ID | Requisito | Estado | Implementacion |
|---|---|---|---|
| RF01 | Carga de archivos CSV con datos deportivos | Implementado | `scripts/download_data.py`, carga lateral en `app/streamlit_app.py` |
| RF02 | Informar errores cuando un archivo no pueda procesarse | Implementado | Mensajes `st.error`, `validate_raw.py`, `quality_report.py` |
| RF03 | Identificar nulos, duplicados e inconsistencias | Implementado | `src/sports_analytics/etl/quality.py`, `scripts/quality_report.py` |
| RF04 | Limpiar y normalizar datos antes de KPIs | Implementado | `src/sports_analytics/etl/normalize.py`, `services/repository.py`, `csv_to_parquet.py` |
| RF05 | Relacionar clubes, partidos, jugadores, apariciones y eventos por IDs | Implementado | `data_catalog.py`, metricas de equipos/jugadores/arbitros |
| RF06 | Calcular indicadores estadisticos basicos | Implementado | `metrics/teams.py`, `metrics/players.py`, `metrics/referees.py` |
| RF07 | Calcular indicadores compuestos para equipos, jugadores y arbitros | Implementado base | Win Rate, BTTS, Over 2.5, por 90, sesgo local/visitante, competitividad, impacto de roja |
| RF08 | Consultar dashboard de equipos | Implementado | Pestaña `Estadisticas de partidos proximos` |
| RF09 | Dashboard de equipos con Win Rate, Over/Under 2.5, BTTS, racha, rendimiento mensual, roja, Head-to-Head, competitividad | Implementado | `metrics/teams.py` y primera pestaña |
| RF10 | Consultar dashboard de jugadores | Implementado | Pestaña `Estadisticas de jugadores especificos` |
| RF11 | Dashboard de jugadores con por 90, rival, titularidad/suplencia, formacion, cambios y disciplina | Implementado base | `metrics/players.py`; cambios se mide con eventos de sustitucion disponibles |
| RF12 | Consultar dashboard de arbitros | Implementado | Pestaña `Estadisticas de arbitros` |
| RF13 | Dashboard de arbitros con amarillas, rojas, sesgo local/visitante, historial arbitro-equipo y penales | Implementado base | `metrics/referees.py`; penales se infieren desde descripciones de eventos |
| RF14 | Filtros por equipo, jugador, arbitro, competicion, temporada o partido | Implementado base | Selectores en las tres pestañas |
| RF15 | Resultados con graficos, tablas y tarjetas resumen | Implementado | `st.metric`, `st.dataframe`, Plotly |
| RF16 | Comparar dos equipos antes de un partido | Implementado | Comparador de equipos |
| RF17 | Visualizar historial entre dos equipos | Implementado | Head-to-Head |
| RF18 | Actualizar datos con nuevos archivos | Implementado base | Carga lateral de CSV y regeneracion de Parquet |
| RF19 | Mensajes de error claros para usuarios no tecnicos | Implementado base | Mensajes en castellano en app y scripts |
| RF20 | Ingerir fixtures futuros desde API-Football | Implementado base | `scripts/sync_api_football_fixtures.py`, `services/api_football.py`, DAG Airflow |
| RF21 | Minimizar requests a API externa | Implementado base | Consulta por liga/temporada, cache Parquet, log de requests |
| RF22 | Orquestar el pipeline ETL | Implementado base | `dags/football_analytics_pipeline.py` |
| RF23 | Cargar datos procesados a un DWH | Implementado base | `db/init_dwh.sql`, `postgres-dwh`, tablas staging y marts |
| RF24 | Respaldar artefactos en storage externo | Implementado base | `storage/external.py`, `scripts/upload_pipeline_artifacts.py` |

## Requisitos no funcionales

| ID | Requisito | Estado | Implementacion |
|---|---|---|---|
| RNF01 | Facil de usar para usuarios no tecnicos | Implementado base | Tres pestañas, selectores y tarjetas resumen |
| RNF02 | Interfaz clara y ordenada | Implementado base | Layout por pestañas, filtros arriba, resultados debajo |
| RNF03 | Carga en tiempo razonable | Implementado base | Cache de Streamlit, Parquet y lectura por columnas/chunks |
| RNF04 | Ejecutable en navegadores modernos | Documentado | Streamlit corre en Chrome, Edge, Firefox y Safari modernos |
| RNF05 | Permitir nuevos KPIs sin rehacer la app | Implementado | KPIs separados en modulos `metrics/` |
| RNF06 | Manejar errores sin interrumpir todo | Implementado | `safe_render` por pestaña y errores claros en carga |
| RNF07 | Conservar trazabilidad entre datos e indicadores | Implementado base | Catalogo de tablas, columnas `_source_*` en Parquet, documentacion |
| RNF08 | Mostrar estadisticas historicas | Implementado | Filtros por temporada, mes, historial y tablas |
| RNF09 | Adaptable a nuevas fuentes, ligas o temporadas | Implementado base | Catalogo de tablas, validacion y carga de nuevos CSV |
| RNF10 | Mantenible | Implementado base | Separacion `etl`, `services`, `metrics`, `app`, `docs`, `tests` |
| RNF11 | Credenciales fuera del codigo | Implementado base | Variables de entorno y Airflow Variables |
| RNF12 | Pipeline observable | Implementado base | Logs de Airflow, reportes de calidad, `etl_request_log` |
| RNF13 | Reejecucion controlada | Implementado base | UPSERT por `fixture_id` y marts reconstruibles |
