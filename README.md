# Sports Analytics Pipeline

Proyecto academico de Ingenieria de Software: pipeline ETL y aplicacion de analisis estadistico deportivo para apoyar decisiones con datos historicos de futbol y fixtures futuros desde API-Football.

## Stack recomendado

- Python + pandas para procesamiento.
- Parquet + pyarrow para guardar datos procesados.
- Streamlit + Plotly para la primera version del dashboard.
- Apache Airflow para orquestacion del pipeline.
- PostgreSQL como Data Warehouse local.
- Metabase como capa BI opcional.
- Dropbox o espejo local como storage externo opcional para artefactos.

## Estructura

```text
app/                         App Streamlit
dags/                        DAGs de Airflow
db/                          SQL de inicializacion del DWH
data/raw/                    CSV originales
data/interim/                Datos temporales
data/processed/parquet/      Datos convertidos a Parquet
data/marts/                  Tablas finales para dashboards
docs/                        Documentacion del proyecto
notebooks/                   Exploracion puntual
scripts/                     Comandos de descarga y preparacion
src/sports_analytics/        Codigo reutilizable
tests/                       Pruebas automatizadas
```

## Arquitectura objetivo

```text
CSV historicos + API-Football
        ↓
Airflow DAG football_analytics_pipeline
        ↓
Raw JSON / CSV versionados
        ↓
Validacion de esquema y calidad
        ↓
Normalizacion + Parquet
        ↓
PostgreSQL DWH
        ↓
Marts agregados
        ↓
Streamlit / Metabase
```

## Primeros pasos

### Opcion A: app local con CSV historicos

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_data.py
PYTHONPATH=src python scripts/prepare_data.py --table games
PYTHONPATH=src streamlit run app/streamlit_app.py
```

### Opcion B: ingesta API-Football manual

La estrategia recomendada es consultar por liga y temporada para reducir requests.

```bash
export APIFOOTBALL_API_KEY="tu_api_key"
PYTHONPATH=src python scripts/sync_api_football_fixtures.py --league 128 --season 2024 --next 20
```

Para varias ligas:

```bash
PYTHONPATH=src python scripts/sync_api_football_fixtures.py --league 128,39,140 --season 2024
```

Esto genera:

- JSON crudo en `data/raw/api_football/fixtures`.
- Parquet normalizado en `data/processed/parquet/api_football_fixtures`.
- Reporte de calidad en `data/interim/quality_reports`.
- Log de requests en `data/interim/request_logs`.

### Opcion C: stack completo con Airflow + DWH + Metabase

```bash
cp .env.example .env
# editar .env con APIFOOTBALL_API_KEY, API_FOOTBALL_LEAGUE_ID y API_FOOTBALL_SEASON
docker compose up -d --build
```

Servicios:

- Airflow UI: http://localhost:8080 (`admin` / `admin`)
- Metabase: http://localhost:3000
- PostgreSQL DWH desde host: `localhost:5433`, base `sports_dwh`, usuario `dwh`, password definido en `POSTGRES_DWH_PASSWORD` del `.env`

El DAG principal es `football_analytics_pipeline`.

## Airflow tokenizado

Las credenciales no se escriben en codigo. Se configuran con variables de entorno o Airflow Variables:

```text
APIFOOTBALL_API_KEY
API_FOOTBALL_LEAGUE_IDS
API_FOOTBALL_LEAGUE_ID
API_FOOTBALL_SEASON
API_FOOTBALL_NEXT_FIXTURES
DROPBOX_TOKEN
```

Nota: en el plan gratis de API-Football, dejar `API_FOOTBALL_NEXT_FIXTURES=0` o vacio porque ese plan no permite el parametro `next`.

Para consultar varias ligas en Airflow:

```text
API_FOOTBALL_LEAGUE_IDS=128,39,140
```

`API_FOOTBALL_LEAGUE_IDS` tiene prioridad sobre `API_FOOTBALL_LEAGUE_ID`.

Para armar una lista basada en las competencias del dataset local:

```bash
PYTHONPATH=src python scripts/export_league_mapping_template.py
```

El archivo generado queda en `data/interim/api_football_league_mapping_template.csv`; ahi se completan manualmente los `api_football_league_id` desde la documentacion de API-Football.

## Pestañas de la app

- `Equipos`: comparacion manual entre dos equipos o seleccion de un partido proximo desde API-Football. Muestra Win Rate, BTTS, Over 2.5, goles promedio, forma reciente, Head-to-Head y evolucion mensual.
- `Jugadores`: busqueda de un jugador y resumen de partidos, goles, asistencias, tarjetas, minutos y rendimiento por 90 minutos.
- `Árbitros`: analisis por arbitro con partidos dirigidos, goles promedio, tarjetas promedio y tendencia local/empate/visitante.

## Calidad, limpieza y trazabilidad

El pipeline valida columnas, genera reportes de calidad, normaliza datos y guarda Parquet con columnas de trazabilidad.

```bash
PYTHONPATH=src python scripts/quality_report.py --table games
PYTHONPATH=src python scripts/quality_report.py --output data/interim/reporte_calidad.csv
```

Para fixtures de API-Football, el pipeline valida `fixture_id`, fecha, liga, temporada y equipos local/visitante.

## Idea clave: chunks + Parquet

Los CSV grandes no se cargan completos en memoria. Se leen por chunks, es decir, bloques de filas, y cada bloque se guarda como Parquet. Luego la app lee Parquet, que es mas rapido y liviano para dashboards.

## Documentacion

- [Arquitectura inicial](docs/arquitectura.md)
- [Pipeline orquestado](docs/pipeline_orquestado.md)
- [Diccionario de datos](docs/diccionario_datos.md)
- [Plan de inicio](docs/plan_inicio.md)
- [Resumen SRS + PGP](docs/srs_pgp_resumen.md)
- [Matriz de requisitos](docs/matriz_requisitos.md)
