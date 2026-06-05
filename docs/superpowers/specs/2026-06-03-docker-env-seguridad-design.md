# Diseño: Dockerización segura y portabilidad local

**Fecha:** 2026-06-03  
**Proyecto:** Sports Analytics Pipeline (TP Ingeniería de Software)

## Objetivo

Hacer el proyecto portable entre máquinas de desarrollo (equipo + evaluador) sin credenciales hardcodeadas. El evaluador debe poder levantar el stack con tres comandos: clonar, editar `.env`, ejecutar `setup.sh`.

## Alcance

- Mover todos los secretos hardcodeados del `docker-compose.yml` a un archivo `.env`
- Actualizar `.env.example` con todas las variables necesarias y placeholders claros
- Hacer que todos los servicios lean del mismo `.env`
- Agregar `setup.sh` como punto de entrada único
- Revisión de seguridad final para confirmar que ninguna credencial quede commiteada

## Variables a migrar

| Variable | Situación actual | Acción |
|---|---|---|
| `APIFOOTBALL_API_KEY` | Ya usa `${VAR:-}` pero falta en `.env.example` completo | Documentar en `.env.example` |
| `API_FOOTBALL_LEAGUE_IDS` | Ya usa `${VAR:-}` | Documentar en `.env.example` |
| `API_FOOTBALL_LEAGUE_ID` | Ya usa `${VAR:-}` | Documentar en `.env.example` |
| `API_FOOTBALL_SEASON` | Ya usa `${VAR:-}` | Documentar en `.env.example` |
| `API_FOOTBALL_NEXT_FIXTURES` | Ya usa `${VAR:-20}` | Documentar en `.env.example` |
| `POSTGRES_AIRFLOW_PASSWORD` | Hardcodeado: `airflow` | Mover a `.env` |
| `POSTGRES_DWH_PASSWORD` | Hardcodeado: `dwh123` | Mover a `.env` |
| `AIRFLOW_SECRET_KEY` | Hardcodeado: `sports-analytics-local-secret` | Mover a `.env` |

## Cambios en docker-compose.yml

- Agregar `env_file: .env` a todos los servicios que hoy no lo tienen (airflow-init, airflow-scheduler, airflow-webserver, postgres-airflow, postgres-dwh)
- Reemplazar valores literales por referencias `${VARIABLE}`
- La connection string del DWH pasa de literal a `postgres://dwh:${POSTGRES_DWH_PASSWORD}@postgres-dwh:5432/sports_dwh`

## setup.sh

Script de entrada para el evaluador o nuevo integrante del equipo:

```bash
#!/bin/bash
set -e
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Archivo .env creado. Completá APIFOOTBALL_API_KEY en .env antes de continuar."
    exit 1
fi
docker compose up -d --build
```

## Revisión de seguridad

Al finalizar la implementación verificar:
1. `git log --all -- .env` no muestra commits con el archivo
2. Ningún password real aparece en `.env.example`
3. La API key no aparece en logs de Airflow ni en mensajes de error del scheduler
4. `git grep -i "dwh123\|airflow\|sports-analytics-local-secret"` no encuentra matches en archivos commiteados

## Fuera de alcance

- Docker secrets / Swarm
- Perfiles de compose
- Cloud deployment
- CI/CD
