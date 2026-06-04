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
