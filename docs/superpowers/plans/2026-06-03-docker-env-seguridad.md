# Docker + .env Seguro — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover todas las credenciales hardcodeadas del docker-compose.yml a un .env, hacer que todos los servicios lo lean, y agregar un setup.sh de entrada para el evaluador.

**Architecture:** Un único `.env` como fuente de verdad para todas las variables sensibles. El `docker-compose.yml` referencia las variables via `${VAR}` y cada servicio declara `env_file: .env`. El `setup.sh` es el único punto de entrada para quien levanta el proyecto por primera vez.

**Tech Stack:** Docker Compose v2, bash, Python 3.11, Apache Airflow 2.10.5, PostgreSQL 15, Streamlit.

---

### Task 1: Actualizar `.env.example` con todas las variables

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Reemplazar el contenido de `.env.example`**

Reemplazar el archivo completo con:

```dotenv
# ──────────────────────────────────────────────
# API-Football
# ──────────────────────────────────────────────
# Conseguila en https://dashboard.api-football.com/
APIFOOTBALL_API_KEY=tu_api_key_aqui

# Liga principal (una sola). Ejemplo: 128 = Liga Profesional Argentina
API_FOOTBALL_LEAGUE_ID=128

# Varias ligas separadas por coma. Si se define, tiene prioridad sobre API_FOOTBALL_LEAGUE_ID.
API_FOOTBALL_LEAGUE_IDS=128,39,140

# Temporada. Ejemplo: 2024
API_FOOTBALL_SEASON=2024

# Próximos fixtures a traer. Dejar en 0 si usás el plan gratuito.
API_FOOTBALL_NEXT_FIXTURES=0

# ──────────────────────────────────────────────
# PostgreSQL — base de Airflow (interna)
# ──────────────────────────────────────────────
POSTGRES_AIRFLOW_USER=airflow
POSTGRES_AIRFLOW_PASSWORD=airflow_change_me
POSTGRES_AIRFLOW_DB=airflow

# ──────────────────────────────────────────────
# PostgreSQL — Data Warehouse
# ──────────────────────────────────────────────
POSTGRES_DWH_USER=dwh
POSTGRES_DWH_PASSWORD=dwh_change_me
POSTGRES_DWH_DB=sports_dwh

# ──────────────────────────────────────────────
# Airflow
# ──────────────────────────────────────────────
# Generá una con: openssl rand -hex 32
AIRFLOW_SECRET_KEY=cambia_esta_clave_con_openssl_rand_hex_32
```

- [ ] **Step 2: Verificar que `.env` sigue en `.gitignore`**

Correr:
```bash
grep "^\.env$" .gitignore
```
Esperado: imprime `.env`. Si no aparece, agregar la línea `.env` al `.gitignore`.

- [ ] **Step 3: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore: actualizar .env.example con todas las variables del stack"
```

---

### Task 2: Actualizar `docker-compose.yml` — servicios Postgres

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Reemplazar el bloque `postgres-airflow`**

Ubicar el bloque actual (líneas ~1-15 del compose) y reemplazarlo con:

```yaml
  postgres-airflow:
    image: postgres:15-alpine
    container_name: sports-postgres-airflow
    env_file: .env
    environment:
      POSTGRES_USER: ${POSTGRES_AIRFLOW_USER}
      POSTGRES_PASSWORD: ${POSTGRES_AIRFLOW_PASSWORD}
      POSTGRES_DB: ${POSTGRES_AIRFLOW_DB}
    volumes:
      - postgres_airflow_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_AIRFLOW_USER}"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - sports-network
```

- [ ] **Step 2: Reemplazar el bloque `postgres-dwh`**

```yaml
  postgres-dwh:
    image: postgres:15-alpine
    container_name: sports-postgres-dwh
    env_file: .env
    environment:
      POSTGRES_USER: ${POSTGRES_DWH_USER}
      POSTGRES_PASSWORD: ${POSTGRES_DWH_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DWH_DB}
    volumes:
      - postgres_dwh_data:/var/lib/postgresql/data
      - ./db/init_dwh.sql:/docker-entrypoint-initdb.d/01_init_dwh.sql:ro
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_DWH_USER} -d ${POSTGRES_DWH_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - sports-network
```

- [ ] **Step 3: Verificar que el compose parsea sin errores**

```bash
docker compose config --quiet
```
Esperado: sin output (sin errores). Si falla, revisar que `.env` existe con las variables definidas.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: mover credenciales de postgres a .env"
```

---

### Task 3: Actualizar `docker-compose.yml` — servicios Airflow

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Reemplazar el bloque `airflow-init`**

```yaml
  airflow-init:
    build:
      context: .
      dockerfile: Dockerfile.airflow
    container_name: sports-airflow-init
    env_file: .env
    command: >
      bash -c "
        airflow db migrate &&
        airflow users create --username admin --password admin --firstname Admin --lastname Sports --role Admin --email admin@example.com || true
      "
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://${POSTGRES_AIRFLOW_USER}:${POSTGRES_AIRFLOW_PASSWORD}@postgres-airflow:5432/${POSTGRES_AIRFLOW_DB}
      AIRFLOW__CORE__LOAD_EXAMPLES: "False"
      AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "True"
      AIRFLOW__WEBSERVER__SECRET_KEY: ${AIRFLOW_SECRET_KEY}
    depends_on:
      postgres-airflow:
        condition: service_healthy
    networks:
      - sports-network
```

- [ ] **Step 2: Reemplazar el bloque `airflow-scheduler`**

```yaml
  airflow-scheduler:
    build:
      context: .
      dockerfile: Dockerfile.airflow
    container_name: sports-airflow-scheduler
    command: airflow scheduler
    env_file: .env
    dns:
      - 8.8.8.8
      - 1.1.1.1
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://${POSTGRES_AIRFLOW_USER}:${POSTGRES_AIRFLOW_PASSWORD}@postgres-airflow:5432/${POSTGRES_AIRFLOW_DB}
      AIRFLOW__CORE__LOAD_EXAMPLES: "False"
      AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "True"
      AIRFLOW__WEBSERVER__SECRET_KEY: ${AIRFLOW_SECRET_KEY}
      AIRFLOW_CONN_POSTGRES_DWH: postgres://${POSTGRES_DWH_USER}:${POSTGRES_DWH_PASSWORD}@postgres-dwh:5432/${POSTGRES_DWH_DB}
      API_FOOTBALL_LEAGUE_IDS: ${API_FOOTBALL_LEAGUE_IDS:-}
      APIFOOTBALL_API_KEY: ${APIFOOTBALL_API_KEY:-}
      API_FOOTBALL_LEAGUE_ID: ${API_FOOTBALL_LEAGUE_ID:-}
      API_FOOTBALL_SEASON: ${API_FOOTBALL_SEASON:-}
      API_FOOTBALL_NEXT_FIXTURES: ${API_FOOTBALL_NEXT_FIXTURES:-0}
      PYTHONPATH: /opt/airflow/src
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./data:/opt/airflow/data
      - ./src:/opt/airflow/src
    depends_on:
      airflow-init:
        condition: service_completed_successfully
      postgres-airflow:
        condition: service_healthy
      postgres-dwh:
        condition: service_healthy
    networks:
      - sports-network
```

- [ ] **Step 3: Reemplazar el bloque `airflow-webserver`**

```yaml
  airflow-webserver:
    build:
      context: .
      dockerfile: Dockerfile.airflow
    container_name: sports-airflow-webserver
    command: airflow webserver
    env_file: .env
    dns:
      - 8.8.8.8
      - 1.1.1.1
    ports:
      - "8080:8080"
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://${POSTGRES_AIRFLOW_USER}:${POSTGRES_AIRFLOW_PASSWORD}@postgres-airflow:5432/${POSTGRES_AIRFLOW_DB}
      AIRFLOW__CORE__LOAD_EXAMPLES: "False"
      AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "True"
      AIRFLOW__WEBSERVER__SECRET_KEY: ${AIRFLOW_SECRET_KEY}
      AIRFLOW_CONN_POSTGRES_DWH: postgres://${POSTGRES_DWH_USER}:${POSTGRES_DWH_PASSWORD}@postgres-dwh:5432/${POSTGRES_DWH_DB}
      API_FOOTBALL_LEAGUE_IDS: ${API_FOOTBALL_LEAGUE_IDS:-}
      APIFOOTBALL_API_KEY: ${APIFOOTBALL_API_KEY:-}
      API_FOOTBALL_LEAGUE_ID: ${API_FOOTBALL_LEAGUE_ID:-}
      API_FOOTBALL_SEASON: ${API_FOOTBALL_SEASON:-}
      API_FOOTBALL_NEXT_FIXTURES: ${API_FOOTBALL_NEXT_FIXTURES:-0}
      PYTHONPATH: /opt/airflow/src
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./data:/opt/airflow/data
      - ./src:/opt/airflow/src
    depends_on:
      airflow-init:
        condition: service_completed_successfully
      airflow-scheduler:
        condition: service_started
      postgres-airflow:
        condition: service_healthy
      postgres-dwh:
        condition: service_healthy
    networks:
      - sports-network
```

- [ ] **Step 4: Verificar que el compose parsea sin errores**

```bash
docker compose config --quiet
```
Esperado: sin output.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: mover credenciales de airflow a .env"
```

---

### Task 4: Crear `setup.sh`

**Files:**
- Create: `setup.sh`

- [ ] **Step 1: Crear el archivo**

```bash
#!/bin/bash
set -e

if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "✔ Archivo .env creado desde .env.example."
    echo "  Abrí .env y completá al menos APIFOOTBALL_API_KEY antes de continuar."
    echo "  Luego volvé a correr: ./setup.sh"
    echo ""
    exit 1
fi

echo "Levantando el stack..."
docker compose up -d --build
echo ""
echo "Stack levantado. Servicios disponibles:"
echo "  Airflow:    http://localhost:8080  (admin / admin)"
echo "  Streamlit:  http://localhost:8501"
echo "  Metabase:   http://localhost:3000"
echo "  PostgreSQL DWH: localhost:5433 / sports_dwh / dwh"
```

- [ ] **Step 2: Darle permisos de ejecución**

```bash
chmod +x setup.sh
```

- [ ] **Step 3: Verificar que funciona cuando no existe `.env`**

```bash
rm -f .env
./setup.sh
```
Esperado: imprime el mensaje de instrucciones y sale con código 1. **No** levanta Docker.

- [ ] **Step 4: Verificar que funciona cuando existe `.env`**

```bash
# Primero crear .env desde el example
cp .env.example .env
# Luego correr sin --build para solo verificar el flujo (no esperar el build completo)
# Solo verificamos que llega al docker compose
./setup.sh 2>&1 | head -5
```
Esperado: imprime "Levantando el stack..." (puede fallar el build si no hay Docker corriendo, eso es OK en este paso).

- [ ] **Step 5: Commit**

```bash
git add setup.sh
git commit -m "chore: agregar setup.sh como punto de entrada del proyecto"
```

---

### Task 5: Revisión de seguridad

**Files:**
- No se crean ni modifican archivos. Solo verificación.

- [ ] **Step 1: Verificar que `.env` no está en el historial de git**

```bash
git log --all -- .env
```
Esperado: sin output (ningún commit contiene `.env`).

- [ ] **Step 2: Verificar que no hay credenciales hardcodeadas en archivos commiteados**

```bash
git grep -i "dwh123\|airflow_change_me\|dwh_change_me\|sports-analytics-local-secret"
```
Esperado: sin output. Si aparece algún match, revisar en qué archivo está y corregirlo.

- [ ] **Step 3: Verificar que `.env.example` no tiene una API key real**

```bash
grep "APIFOOTBALL_API_KEY" .env.example
```
Esperado: `APIFOOTBALL_API_KEY=tu_api_key_aqui` (placeholder, no una key real).

- [ ] **Step 4: Verificar que el compose final no tiene valores hardcodeados**

```bash
grep -E "password|secret|key" docker-compose.yml | grep -v "\${"
```
Esperado: sin output (todo usa `${VAR}`).

- [ ] **Step 5: Commit final si todo pasó**

```bash
git add .
git status  # verificar que no hay archivos inesperados staged
git commit -m "chore: revisión de seguridad — sin credenciales hardcodeadas"
```
