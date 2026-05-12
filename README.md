# Tp-ingenieria-software

Proyecto academico de Ingenieria de Software: aplicacion web de analisis estadistico deportivo para apoyar decisiones con datos historicos de futbol.

## Stack recomendado

- Python + pandas para procesamiento.
- Parquet + pyarrow para guardar datos procesados.
- Streamlit + Plotly para la primera version del dashboard.

## Estructura

```text
app/                         App Streamlit
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

## Primeros pasos

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_data.py
PYTHONPATH=src python scripts/prepare_data.py --table games
PYTHONPATH=src streamlit run app/streamlit_app.py
```

Para activar el oraculo de proximos partidos de API-Football, usar una API key desde la app o exportarla antes de ejecutar Streamlit:

```bash
export APIFOOTBALL_API_KEY="tu_api_key"
PYTHONPATH=src streamlit run app/streamlit_app.py
```

## Pestañas de la app

- `Estadisticas de partidos proximos`: comparacion previa entre dos equipos con Win Rate, BTTS, Over 2.5, goles promedio, forma reciente, porcentajes Head-to-Head y oraculo de proximos 5 partidos desde API-Football.
- `Estadisticas de jugadores especificos`: busqueda de un jugador y resumen de partidos, goles, asistencias, tarjetas, minutos y rendimiento por 90 minutos.
- `Estadisticas de arbitros`: analisis por arbitro con partidos dirigidos, goles promedio, tarjetas promedio y tendencia local/empate/visitante.

## Calidad, limpieza y trazabilidad

El pipeline valida columnas, genera reportes de calidad, normaliza datos y guarda Parquet con columnas de trazabilidad.

```bash
PYTHONPATH=src python scripts/quality_report.py --table games
PYTHONPATH=src python scripts/quality_report.py --output data/interim/reporte_calidad.csv
```

## Idea clave: chunks + Parquet

Los CSV grandes no se cargan completos en memoria. Se leen por chunks, es decir, bloques de filas, y cada bloque se guarda como Parquet. Luego la app lee Parquet, que es mas rapido y liviano para dashboards.

## Documentacion

- [Arquitectura inicial](docs/arquitectura.md)
- [Diccionario de datos](docs/diccionario_datos.md)
- [Plan de inicio](docs/plan_inicio.md)
- [Resumen SRS + PGP](docs/srs_pgp_resumen.md)
- [Matriz de requisitos](docs/matriz_requisitos.md)
