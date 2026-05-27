# Plan de inicio

## Alcance recomendado para la primera demo

La primera version deberia enfocarse en comparar dos equipos. Es el camino mas directo para mostrar valor sin mezclar todos los datasets desde el dia uno.

KPIs iniciales:

- Win Rate de cada equipo.
- Promedio de goles a favor y en contra.
- Porcentaje de partidos Over 2.5.
- Porcentaje de BTTS.
- Racha reciente.
- Historial Head-to-Head.

## Organizacion del front

La app queda separada en tres pestañas:

- `Estadisticas de partidos proximos`: comparacion de dos equipos para analizar un partido futuro o hipotetico.
- `Estadisticas de jugadores especificos`: indicadores individuales por jugador.
- `Estadisticas de arbitros`: comportamiento historico de un arbitro y promedios relevantes.

## Orden de trabajo actualizado

1. Validar que los CSV tengan las columnas esperadas.
2. Convertir CSV a Parquet por chunks.
3. Crear funciones de KPIs sobre `games`.
4. Crear dashboard de comparacion de equipos.
5. Agregar jugadores con `appearances`.
6. Agregar arbitros con `games.referee` y eventos/tarjetas.
7. Crear cuenta en API-Football y obtener API key.
8. Consultar fixtures por liga y temporada para minimizar requests.
9. Guardar raw JSON, Parquet procesado y reporte de calidad.
10. Levantar Airflow + PostgreSQL DWH con Docker Compose.
11. Crear y ejecutar el DAG `football_analytics_pipeline`.
12. Cargar fixtures al DWH y construir marts.
13. Conectar dashboard a datos procesados.
14. Documentar limitaciones de datos, supuestos y trazabilidad.

## Comandos principales

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Descargar datos desde Drive:

```bash
python scripts/download_data.py
```

Convertir un CSV puntual a Parquet:

```bash
PYTHONPATH=src python scripts/prepare_data.py --table games
```

Convertir todo:

```bash
PYTHONPATH=src python scripts/prepare_data.py
```

Ejecutar la app:

```bash
PYTHONPATH=src streamlit run app/streamlit_app.py
```

Ingerir fixtures desde API-Football:

```bash
export APIFOOTBALL_API_KEY="tu_api_key"
PYTHONPATH=src python scripts/sync_api_football_fixtures.py --league 128 --season 2024 --next 20
```

Ingerir varias ligas:

```bash
PYTHONPATH=src python scripts/sync_api_football_fixtures.py --league 128,39,140 --season 2024
```

Generar plantilla de ligas locales para completar IDs de API-Football:

```bash
PYTHONPATH=src python scripts/export_league_mapping_template.py
```

Levantar el stack con Airflow:

```bash
cp .env.example .env
docker compose up -d --build
```
