# Pipeline orquestado con Airflow

Este documento adapta el proyecto ejemplo de Black Friday al dominio del proyecto: analisis deportivo con datos historicos y fixtures futuros desde API-Football.

## 1. Objetivo del pipeline

Actualizar datos de partidos futuros y combinarlos con datos historicos para alimentar metricas de comparacion entre equipos, jugadores y arbitros.

Producto final:

- Dashboard Streamlit con analisis deportivo.
- Tablas DWH listas para Metabase.
- Reportes de calidad y trazabilidad de ingesta.

## 2. Fuentes de datos

- CSV historicos: partidos, jugadores, apariciones, eventos, clubes y competiciones.
- API-Football: endpoint `/fixtures`, consultado por liga y temporada.
- Storage externo opcional: Dropbox para respaldar raw, processed y reportes.

## 3. Estrategia de ingesta

La ingesta de API-Football es batch diaria mediante Airflow. Se consulta por liga y temporada, no por equipo, para minimizar requests.

Ejemplo:

```text
/fixtures?league=128&season=2024
```

El DAG tambien acepta multiples ligas:

```text
API_FOOTBALL_LEAGUE_IDS=128,39,140
```

Cada liga configurada genera una request separada, por lo que hay que cuidar la cuota del plan gratis.

El JSON original se guarda sin modificar para auditoria.

## 4. Procesamiento

El pipeline transforma la respuesta de API-Football a una tabla normalizada con:

- fixture_id
- fecha del partido
- estado
- liga
- temporada
- equipo local
- equipo visitante
- goles si existen
- endpoint y parametros de origen
- fecha de ingesta

## 5. Almacenamiento

Se usan tres niveles:

- Raw: JSON original en `data/raw/api_football/fixtures`.
- Processed: Parquet en `data/processed/parquet/api_football_fixtures`.
- DWH: PostgreSQL con staging, logs y marts.

## 6. Flujo de tareas

```text
validate_dwh + validate_config
  -> fetch_api_football_fixtures
  -> validate_fixtures_schema
  -> normalize_fixtures_to_parquet
  -> load_fixtures_to_dwh
  -> build_fixture_marts
  -> quality_check
```

## 7. Gobernanza y monitoreo

El pipeline deja evidencia de:

- Requests realizadas a API-Football.
- Parametros usados.
- Cantidad de filas recibidas.
- Requests restantes si la API lo informa.
- Errores y warnings de calidad.
- Logs por tarea en Airflow.

Las credenciales se configuran con variables:

```text
APIFOOTBALL_API_KEY
API_FOOTBALL_LEAGUE_IDS
API_FOOTBALL_LEAGUE_ID
API_FOOTBALL_SEASON
API_FOOTBALL_NEXT_FIXTURES
DROPBOX_TOKEN
```

En plan gratis, `API_FOOTBALL_NEXT_FIXTURES` debe quedar en `0` o vacio porque API-Football no permite el parametro `next`.

Para mapear las competencias historicas locales con IDs de API-Football:

```bash
PYTHONPATH=src python scripts/export_league_mapping_template.py
```

Luego completar `api_football_league_id` en `data/interim/api_football_league_mapping_template.csv`.

## 8. Consumo

Streamlit lee los fixtures procesados en Parquet y los cruza con el historial local. Metabase puede conectarse al DWH y consultar `mart_upcoming_fixtures`.

## Como ejecutar

### Ingesta manual

```bash
export APIFOOTBALL_API_KEY="tu_api_key"
PYTHONPATH=src python scripts/sync_api_football_fixtures.py --league 128 --season 2024 --next 20
```

### Stack completo

```bash
cp .env.example .env
docker compose up -d --build
```

Abrir Airflow en http://localhost:8080 y activar `football_analytics_pipeline`.

## Criterio de aceptacion

El avance se considera completo cuando:

- El DAG corre sin errores.
- Existe raw JSON de API-Football.
- Existe Parquet normalizado.
- El DWH tiene fixtures en `stg_api_football_fixtures`.
- El mart `mart_upcoming_fixtures` se actualiza.
- Streamlit muestra fixtures procesados sin consultar la API en cada carga.
