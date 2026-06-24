from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sports_analytics.config import (
    API_FOOTBALL_FREE_PLAN_MIN_SEASON,
    API_FOOTBALL_MAX_SEASON,
    API_FOOTBALL_MIN_SEASON,
    CURRENT_DATE,
    CURRENT_SEASON,
    RAW_DIR,
)
from sports_analytics.data_catalog import TABLES
from sports_analytics.etl.csv_to_parquet import convert_table_to_parquet
from sports_analytics.etl.quality import build_quality_report
from sports_analytics.metrics.players import (
    PLAYER_APPEARANCE_COLUMNS,
    PLAYER_EVENT_COLUMNS,
    PLAYER_LINEUP_COLUMNS,
    build_player_summary,
    enrich_player_history,
    player_formation_summary,
    player_history,
    player_role_summary,
    player_season_summary,
    player_substitution_summary,
    player_vs_opponent,
)
from sports_analytics.metrics.referees import (
    PENALTY_EVENT_COLUMNS,
    build_referee_match_view,
    build_referee_summary,
    referee_history,
    referee_team_history,
)
from sports_analytics.metrics.teams import (
    add_team_discipline,
    build_team_match_view,
    compare_teams,
    head_to_head,
    head_to_head_summary,
    league_competitiveness,
    monthly_team_performance,
    red_card_impact,
    summarize_head_to_head_by_team,
)
from sports_analytics.services.api_football import (
    ApiFootballConfigError,
    ApiFootballError,
    TeamStanding,
    UpcomingFixture,
    fetch_league_standings,
    fetch_upcoming_fixtures,
    get_api_football_key,
)
from sports_analytics.services.repository import data_version, load_table_columns, load_table_filtered_by_value
from sports_analytics.services.team_matching import build_team_name_index, find_best_team_match


st.set_page_config(page_title="BetStats — Analisis deportivo", layout="wide", page_icon="⚽")

st.markdown("""
<style>
/* ── Fondo y tipografía general ── */
[data-testid="stAppViewContainer"] { background-color: #111314; }
[data-testid="stSidebar"] { background-color: #181b1f; }

/* ── Cards de partido ── */
.intro-panel {
    background: #171c20;
    border: 1px solid #2c333a;
    border-radius: 8px;
    padding: 18px 22px;
    margin: 12px 0 18px 0;
}

.intro-title {
    color: #f1f5f9;
    font-size: 20px;
    font-weight: 800;
    margin-bottom: 6px;
}

.intro-copy {
    color: #cbd5e1;
    font-size: 14px;
    line-height: 1.5;
}

.guide-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin: 12px 0 18px 0;
}

.guide-step {
    background: #171c20;
    border: 1px solid #2c333a;
    border-radius: 8px;
    padding: 12px 14px;
    color: #cbd5e1;
    font-size: 13px;
}

.guide-step strong {
    color: #49c38f;
    display: block;
    margin-bottom: 4px;
}

.match-card {
    background: #171c20;
    border: 1px solid #2c333a;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 16px;
    transition: border-color 0.2s;
}
.match-card:hover { border-color: #49c38f; }

.match-header {
    font-size: 11px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 10px;
}

.match-teams {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
}

.team-name {
    font-size: 18px;
    font-weight: 700;
    color: #f1f5f9;
    flex: 1;
}

.team-name.away { text-align: right; }

.vs-badge {
    background: #263038;
    color: #cbd5e1;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 20px;
    margin: 0 16px;
}

/* ── KPI badges ── */
.kpi-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 8px;
}

.kpi-badge {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
}

.kpi-green  { background: #0d2b1a; color: #34d399; border: 1px solid #065f46; }
.kpi-red    { background: #2b0d0d; color: #f87171; border: 1px solid #7f1d1d; }
.kpi-yellow { background: #2b250d; color: #fbbf24; border: 1px solid #78350f; }
.kpi-blue   { background: #0b2530; color: #67e8f9; border: 1px solid #155e75; }
.kpi-gray   { background: #202429; color: #cbd5e1; border: 1px solid #3b424a; }

/* ── Disclaimer ── */
.disclaimer {
    background: #1c1a0d;
    border: 1px solid #78350f;
    border-left: 4px solid #f59e0b;
    border-radius: 6px;
    padding: 10px 16px;
    color: #fbbf24;
    font-size: 13px;
    margin-bottom: 20px;
}

/* ── Section headers ── */
.section-title {
    font-size: 13px;
    font-weight: 700;
    color: #49c38f;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 4px;
    border-bottom: 1px solid #254437;
    padding-bottom: 6px;
}

/* ── Métricas ── */
[data-testid="metric-container"] {
    background: #171c20;
    border: 1px solid #2c333a;
    border-radius: 8px;
    padding: 12px 16px;
}

@media (max-width: 900px) {
    .guide-row { grid-template-columns: 1fr; }
}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_games(_data_version: tuple[float, ...]) -> pd.DataFrame:
    columns = [
        "game_id",
        "date",
        "season",
        "competition_id",
        "home_club_id",
        "away_club_id",
        "home_club_name",
        "away_club_name",
        "home_club_goals",
        "away_club_goals",
        "referee",
        "home_club_formation",
        "away_club_formation",
    ]
    games = load_table_columns("games", columns)
    games["date"] = pd.to_datetime(games["date"], errors="coerce")
    seasons = pd.to_numeric(games["season"], errors="coerce")
    current_cutoff = pd.Timestamp(CURRENT_DATE)
    current_mask = (
        (games["date"].isna() | (games["date"] <= current_cutoff))
        & (seasons.isna() | (seasons <= CURRENT_SEASON))
    )
    return games[current_mask]


@st.cache_data(show_spinner=False)
def load_appearances(_data_version: tuple[float, ...]) -> pd.DataFrame:
    return load_table_columns("appearances", PLAYER_APPEARANCE_COLUMNS)


@st.cache_data(show_spinner=False)
def load_game_events(_data_version: tuple[float, ...]) -> pd.DataFrame:
    columns = sorted(set(PLAYER_EVENT_COLUMNS + PENALTY_EVENT_COLUMNS))
    return load_table_columns("game_events", columns)


@st.cache_data(show_spinner=False)
def load_lineups_for_player(player_id: int, _data_version: tuple[float, ...]) -> pd.DataFrame:
    return load_table_filtered_by_value("game_lineups", PLAYER_LINEUP_COLUMNS, "player_id", player_id)


@st.cache_data(show_spinner=False)
def load_player_data(_appearances_version: tuple[float, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    appearances = load_appearances(_appearances_version)
    summary = build_player_summary(appearances)
    return appearances, summary


@st.cache_data(show_spinner=False)
def load_referee_data(
    games: pd.DataFrame,
    _appearances_version: tuple[float, ...],
    _events_version: tuple[float, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    appearances = load_appearances(_appearances_version)[["game_id", "yellow_cards", "red_cards"]]
    events = load_game_events(_events_version)[PENALTY_EVENT_COLUMNS]
    matches = build_referee_match_view(games, appearances, events)
    summary = build_referee_summary(matches)
    return matches, summary


@st.cache_data(ttl=900, show_spinner=False)
def load_upcoming_fixtures_from_api(
    next_count: int,
    league_id: int | None,
    season: int | None,
    team_id: int | None,
    timezone: str,
    api_key_marker: str,
    _api_key: str,
):
    return fetch_upcoming_fixtures(
        next_count=next_count,
        league_id=league_id,
        season=season,
        team_id=team_id,
        timezone=timezone,
        api_key=_api_key,
    )


@st.cache_data(ttl=1800, show_spinner=False)
def load_standings_from_api(
    league_id: int,
    season: int,
    api_key_marker: str,
    _api_key: str,
):
    return fetch_league_standings(league_id=league_id, season=season, api_key=_api_key)

def render_disclaimer() -> None:
    st.markdown(
        '<div class="disclaimer">⚠️ <strong>Solo análisis orientativo.</strong> '
        'Las estadísticas no garantizan resultados. No constituyen asesoramiento de apuestas.</div>',
        unsafe_allow_html=True,
    )


def render_intro_panel(title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="intro-panel">
            <div class="intro-title">{title}</div>
            <div class="intro-copy">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_guide_steps(steps: list[tuple[str, str]]) -> None:
    step_html = "".join(
        f'<div class="guide-step"><strong>{title}</strong>{body}</div>'
        for title, body in steps
    )
    st.markdown(f'<div class="guide-row">{step_html}</div>', unsafe_allow_html=True)


def kpi_badge(label: str, value: str, color: str = "gray") -> str:
    return f'<span class="kpi-badge kpi-{color}">{label}: <strong>{value}</strong></span>'


def render_fixture_card(
    home: str,
    away: str,
    league: str,
    date: str,
    round_name: str,
    status: str,
    home_stats: dict | None = None,
    away_stats: dict | None = None,
    score_ft: str | None = None,
) -> None:
    normalized_status = status.strip().upper()
    finished = normalized_status in ("FT", "AET", "PEN", "MATCH FINISHED")
    scheduled = normalized_status in ("NS", "TBD", "NOT STARTED", "TIME TO BE DEFINED", "")
    score_html = f'<span class="vs-badge">{score_ft}</span>' if (finished and score_ft) else '<span class="vs-badge">VS</span>'

    home_badges = ""
    away_badges = ""
    if home_stats and away_stats:
        def wr_color(v): return "green" if v >= 0.5 else ("yellow" if v >= 0.35 else "red")
        home_badges = "".join([
            kpi_badge("WR", f"{home_stats.get('win_rate', 0)*100:.0f}%", wr_color(home_stats.get('win_rate', 0))),
            kpi_badge("BTTS", f"{home_stats.get('btts_rate', 0)*100:.0f}%", "blue"),
            kpi_badge("O2.5", f"{home_stats.get('over_2_5_rate', 0)*100:.0f}%", "blue"),
            kpi_badge("Forma", str(home_stats.get('recent_form', '')), "gray"),
        ])
        away_badges = "".join([
            kpi_badge("WR", f"{away_stats.get('win_rate', 0)*100:.0f}%", wr_color(away_stats.get('win_rate', 0))),
            kpi_badge("BTTS", f"{away_stats.get('btts_rate', 0)*100:.0f}%", "blue"),
            kpi_badge("O2.5", f"{away_stats.get('over_2_5_rate', 0)*100:.0f}%", "blue"),
            kpi_badge("Forma", str(away_stats.get('recent_form', '')), "gray"),
        ])

    if finished:
        status_html = '<span style="color:#34d399;">Finalizado</span>'
    elif scheduled:
        status_html = f'<span style="color:#cbd5e1;">{status or "Programado"}</span>'
    else:
        status_html = f'<span style="color:#f87171;font-weight:700;">{status}</span>'

    st.markdown(f"""
    <div class="match-card">
        <div class="match-header">
            {league} &nbsp;·&nbsp; {round_name} &nbsp;·&nbsp; {date} &nbsp;·&nbsp; {status_html}
        </div>
        <div class="match-teams">
            <div class="team-name">{home}</div>
            {score_html}
            <div class="team-name away">{away}</div>
        </div>
        <div style="display:flex; justify-content:space-between; gap:8px;">
            <div class="kpi-row">{home_badges}</div>
            <div class="kpi-row" style="justify-content:flex-end;">{away_badges}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_data_admin() -> None:
    with st.sidebar.expander("Administración de datos"):
        st.caption("Usá esta sección solo si necesitás cargar CSV nuevos o revisar calidad.")
        table_name = st.selectbox("Tabla", list(TABLES.keys()))
        spec = TABLES[table_name]
        uploaded = st.file_uploader("Subir CSV actualizado", type="csv")

        if uploaded is not None:
            raw_bytes = uploaded.getvalue()
            try:
                header = pd.read_csv(io.BytesIO(raw_bytes), nrows=0)
                missing = [column for column in spec.columns if column not in header.columns]
            except Exception as exc:
                st.error(f"No se pudo leer el archivo. Revisá que sea un CSV válido. Detalle: {exc}")
                missing = list(spec.columns)

            if missing:
                st.error(f"El archivo no tiene la estructura esperada. Faltan columnas: {missing}")
            else:
                st.success("El archivo tiene las columnas esperadas.")
                if st.button("Actualizar datos"):
                    try:
                        RAW_DIR.mkdir(parents=True, exist_ok=True)
                        (RAW_DIR / spec.file_name).write_bytes(raw_bytes)
                        convert_table_to_parquet(table_name)
                        st.cache_data.clear()
                        st.success("Datos actualizados correctamente.")
                    except Exception as exc:
                        st.error(f"No se pudo actualizar la tabla. Detalle: {exc}")

        if st.button("Revisar calidad"):
            try:
                sample = pd.read_csv(RAW_DIR / spec.file_name, nrows=50_000, low_memory=False)
                report = build_quality_report(table_name, sample)
                if report.empty:
                    st.success("No se detectaron problemas en la muestra revisada.")
                else:
                    st.dataframe(report, hide_index=True, width="stretch")
            except Exception as exc:
                st.error(f"No se pudo generar el reporte de calidad. Detalle: {exc}")


def select_optional(label: str, values: list[object], default: str = "Todos") -> object:
    options = [default] + clean_options(values)
    return st.selectbox(label, options)


def select_required(label: str, values: list[object]) -> object | None:
    options = clean_options(values)
    if not options:
        st.warning(f"No hay opciones disponibles para {label}.")
        return None
    return st.selectbox(label, options)


def clean_options(values: list[object]) -> list[object]:
    unique_values = pd.Series(values).dropna().drop_duplicates().tolist()
    return sorted(unique_values, key=lambda value: str(value))


def team_options_from_matches(matches: pd.DataFrame) -> dict[str, int]:
    teams = matches[["team_id", "team_name"]].dropna().drop_duplicates().sort_values("team_name")
    return dict(zip(teams["team_name"], teams["team_id"]))


def team_options_from_referee_history(history: pd.DataFrame) -> dict[str, int]:
    home = history[["home_club_id", "home_club_name"]].rename(
        columns={"home_club_id": "team_id", "home_club_name": "team_name"}
    )
    away = history[["away_club_id", "away_club_name"]].rename(
        columns={"away_club_id": "team_id", "away_club_name": "team_name"}
    )
    teams = pd.concat([home, away], ignore_index=True).dropna().drop_duplicates().sort_values("team_name")
    return dict(zip(teams["team_name"], teams["team_id"]))


def safe_render(render_function, *args) -> None:
    try:
        render_function(*args)
    except Exception as exc:
        st.error(f"No se pudo mostrar esta sección. Detalle: {exc}")


def optional_int_filter(
    label: str,
    help_text: str = "",
    key: str | None = None,
    value: str = "",
    max_value: int | None = None,
) -> tuple[int | None, bool]:
    raw_value = st.text_input(label, value=value, help=help_text, key=key)
    if not raw_value.strip():
        return None, True

    try:
        parsed = int(raw_value.strip())
    except ValueError:
        st.warning(f"{label} debe ser un numero entero.")
        return None, False
    if max_value is not None and parsed > max_value:
        st.warning(f"{label} no puede ser mayor a {max_value}.")
        return None, False
    return parsed, True


def format_fixture_datetime(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return str(value or "")
    return parsed.tz_convert("America/Argentina/Buenos_Aires").strftime("%d/%m/%Y %H:%M")


def render_h2h_summary_metrics(summary: dict[str, object], team_a_name: str, team_b_name: str) -> None:
    metric_columns = st.columns(4)
    metric_columns[0].metric("Enfrentamientos", f"{int(summary['played'])}")
    metric_columns[1].metric(f"Gano {team_a_name}", f"{float(summary['team_a_win_rate']) * 100:.1f}%")
    metric_columns[2].metric("Empates", f"{float(summary['draw_rate']) * 100:.1f}%")
    metric_columns[3].metric(f"Gano {team_b_name}", f"{float(summary['team_b_win_rate']) * 100:.1f}%")


def percent_label(value: object) -> str:
    return f"{float(value) * 100:.1f}%"


def format_display_date(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value or "")
    return parsed.strftime("%d/%m/%Y")


def render_team_insight_text(
    comparison: pd.DataFrame,
    h2h_summary: dict[str, object],
    team_a_name: str,
    team_b_name: str,
    last_n: int,
) -> None:
    if comparison.empty or len(comparison) < 2:
        return

    team_a = comparison.iloc[0]
    team_b = comparison.iloc[1]
    team_a_wr = float(team_a["win_rate"])
    team_b_wr = float(team_b["win_rate"])
    team_a_goals = float(team_a["avg_goals_for"])
    team_b_goals = float(team_b["avg_goals_for"])
    team_a_conceded = float(team_a["avg_goals_against"])
    team_b_conceded = float(team_b["avg_goals_against"])
    btts_avg = (float(team_a["btts_rate"]) + float(team_b["btts_rate"])) / 2
    over_avg = (float(team_a["over_2_5_rate"]) + float(team_b["over_2_5_rate"])) / 2

    if abs(team_a_wr - team_b_wr) >= 0.15:
        better_team = team_a_name if team_a_wr > team_b_wr else team_b_name
        result_note = f"{better_team} llega con mejor porcentaje de victorias recientes."
    else:
        result_note = "El rendimiento reciente de ambos equipos es parejo."

    if over_avg >= 0.55:
        goals_note = "El cruce tiene tendencia a partidos con varios goles."
    elif over_avg <= 0.35:
        goals_note = "Los datos recientes sugieren partidos de marcador más bajo."
    else:
        goals_note = "La tendencia de goles es intermedia, sin una señal fuerte hacia partido abierto o cerrado."

    if btts_avg >= 0.55:
        btts_note = "También aparece una señal relativamente alta de que ambos equipos conviertan."
    elif btts_avg <= 0.35:
        btts_note = "La frecuencia de ambos equipos convirtiendo es baja en los partidos recientes."
    else:
        btts_note = "La métrica BTTS no marca una tendencia clara."

    h2h_played = int(h2h_summary["played"])
    if h2h_played:
        h2h_note = (
            f"En el historial directo cargado hay {h2h_played} enfrentamiento(s): "
            f"{team_a_name} ganó {int(h2h_summary['team_a_wins'])}, "
            f"empataron {int(h2h_summary['draws'])} y "
            f"{team_b_name} ganó {int(h2h_summary['team_b_wins'])}."
        )
    else:
        h2h_note = (
            "No hay enfrentamientos directos cargados entre estos dos equipos. "
            "Eso no significa que nunca hayan jugado: solo indica que ese cruce no aparece en el dataset local."
        )

    st.info(
        f"Lectura rápida: se comparan los últimos {last_n} partidos disponibles de cada equipo. "
        f"{result_note} {team_a_name} promedia {team_a_goals:.2f} goles a favor y {team_a_conceded:.2f} en contra; "
        f"{team_b_name} promedia {team_b_goals:.2f} a favor y {team_b_conceded:.2f} en contra. "
        f"{goals_note} {btts_note} {h2h_note}"
    )


def render_metric_glossary() -> None:
    with st.expander("Que significa cada metrica"):
        st.markdown(
            """
- **Win Rate**: porcentaje de partidos ganados.
- **BTTS**: partidos donde ambos equipos hicieron al menos un gol.
- **Over 2.5**: partidos con 3 goles o mas en total.
- **GF prom.**: goles a favor promedio por partido.
- **GC prom.**: goles recibidos promedio por partido.
- **Forma**: ultimos resultados, donde W es victoria, D empate y L derrota.
- **Head-to-Head**: solo partidos historicos entre los dos equipos seleccionados.
- **Amarillas/Rojas prom.**: tarjetas promedio por partido para cada equipo.
            """
        )


def render_individual_team_overview(comparison: pd.DataFrame, team_a_name: str, team_b_name: str) -> None:
    st.subheader("Rendimiento individual")
    st.caption("Cada equipo se mide contra todos sus rivales recientes dentro de los filtros elegidos.")

    team_a = comparison.iloc[0]
    team_b = comparison.iloc[1]
    columns = st.columns(4)
    columns[0].metric(f"Win Rate {team_a_name}", percent_label(team_a["win_rate"]))
    columns[1].metric(f"Win Rate {team_b_name}", percent_label(team_b["win_rate"]))
    columns[2].metric(f"BTTS {team_a_name}", percent_label(team_a["btts_rate"]))
    columns[3].metric(f"Over 2.5 {team_b_name}", percent_label(team_b["over_2_5_rate"]))

    visual_data = comparison.melt(
        id_vars=["team_name"],
        value_vars=["win_rate", "over_2_5_rate", "btts_rate"],
        var_name="Metrica",
        value_name="Valor",
    )
    visual_data["Metrica"] = visual_data["Metrica"].replace(
        {
            "win_rate": "Win Rate",
            "over_2_5_rate": "Over 2.5",
            "btts_rate": "BTTS",
        }
    )
    st.plotly_chart(
        px.bar(
            visual_data,
            x="Metrica",
            y="Valor",
            color="team_name",
            barmode="group",
            text=visual_data["Valor"].map(lambda value: f"{value * 100:.0f}%"),
            labels={"team_name": "Equipo", "Valor": "Porcentaje"},
            range_y=[0, 1],
        ),
        width="stretch",
    )


def render_h2h_overview(
    h2h_summary: dict[str, object],
    h2h_by_team: pd.DataFrame,
    team_a_name: str,
    team_b_name: str,
) -> None:
    st.subheader("Historial directo entre equipos")
    st.caption("Estos numeros usan solo los partidos historicos jugados entre los dos equipos seleccionados.")
    render_h2h_summary_metrics(h2h_summary, team_a_name, team_b_name)

    outcome_data = pd.DataFrame(
        {
            "Resultado": [team_a_name, "Empate", team_b_name],
            "Partidos": [
                int(h2h_summary["team_a_wins"]),
                int(h2h_summary["draws"]),
                int(h2h_summary["team_b_wins"]),
            ],
            "Porcentaje": [
                float(h2h_summary["team_a_win_rate"]),
                float(h2h_summary["draw_rate"]),
                float(h2h_summary["team_b_win_rate"]),
            ],
        }
    )
    chart_columns = st.columns([1, 1])
    with chart_columns[0]:
        if int(h2h_summary["played"]) > 0:
            st.plotly_chart(
                px.pie(
                    outcome_data,
                    names="Resultado",
                    values="Partidos",
                    hole=0.45,
                    title="Reparto del historial",
                ),
                width="stretch",
            )
        else:
            st.info("No hay historial directo cargado para graficar.")

    if not h2h_by_team.empty:
        h2h_display = h2h_by_team[
            [
                "team_name",
                "played",
                "wins",
                "draws",
                "losses",
                "avg_goals_for",
                "avg_goals_against",
                "over_2_5_rate",
                "btts_rate",
                "avg_yellow_cards",
                "avg_red_cards",
                "recent_form",
            ]
        ].rename(
            columns={
                "team_name": "Equipo",
                "played": "PJ",
                "wins": "G",
                "draws": "E",
                "losses": "P",
                "avg_goals_for": "GF prom.",
                "avg_goals_against": "GC prom.",
                "over_2_5_rate": "Over 2.5",
                "btts_rate": "BTTS",
                "avg_yellow_cards": "Amarillas prom.",
                "avg_red_cards": "Rojas prom.",
                "recent_form": "Forma",
            }
        )
        h2h_display["Over 2.5"] = h2h_display["Over 2.5"].map(percent_label)
        h2h_display["BTTS"] = h2h_display["BTTS"].map(percent_label)

        discipline_data = h2h_by_team.melt(
            id_vars=["team_name"],
            value_vars=["avg_yellow_cards", "avg_red_cards"],
            var_name="Tarjeta",
            value_name="Promedio",
        )
        discipline_data["Tarjeta"] = discipline_data["Tarjeta"].replace(
            {
                "avg_yellow_cards": "Amarillas",
                "avg_red_cards": "Rojas",
            }
        )
        with chart_columns[1]:
            st.plotly_chart(
                px.bar(
                    discipline_data,
                    x="Tarjeta",
                    y="Promedio",
                    color="team_name",
                    barmode="group",
                    text="Promedio",
                    title="Tarjetas en el historial",
                    labels={"team_name": "Equipo"},
                ),
                width="stretch",
            )
        outcome_display = outcome_data.copy()
        outcome_display["Porcentaje"] = outcome_display["Porcentaje"].map(percent_label)
        with st.expander("Ver datos del historial directo"):
            st.dataframe(outcome_display, hide_index=True, width="stretch")
            st.dataframe(h2h_display, hide_index=True, width="stretch")


def render_selected_fixture_analysis(
    games: pd.DataFrame,
    selected: dict[str, object],
    *,
    widget_key_prefix: str,
) -> None:
    home_name = str(selected["home"])
    away_name = str(selected["away"])

    render_fixture_card(
        home=home_name,
        away=away_name,
        league=str(selected.get("league", "")),
        date=str(selected.get("date_str", "")),
        round_name=str(selected.get("round_name", "")),
        status=str(selected.get("status", "")),
    )

    team_index = build_team_name_index(games)
    home_match = find_best_team_match(home_name, team_index)
    away_match = find_best_team_match(away_name, team_index)

    if home_match is None or away_match is None:
        st.warning("No se pudo vincular uno o ambos equipos con el dataset histórico de Transfermarkt.")
        return

    if home_match.team_id == away_match.team_id:
        st.warning("Ambos equipos se mapearon al mismo registro histórico.")
        return

    with st.expander("Coincidencia con datos históricos"):
        st.write(
            f"{home_name} -> {home_match.team_name} ({home_match.score:.2f}) | "
            f"{away_name} -> {away_match.team_name} ({away_match.score:.2f})"
        )

    render_team_comparison_content(
        games=games,
        team_a_id=home_match.team_id,
        team_b_id=away_match.team_id,
        team_a_name=home_match.team_name,
        team_b_name=away_match.team_name,
        widget_key_prefix=widget_key_prefix,
    )


def api_fixture_rows(fixtures: list[UpcomingFixture]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fixture in fixtures:
        date_str = format_fixture_datetime(fixture.date)
        label = f"{fixture.league_name}  ·  {date_str}  ·  {fixture.home_team} vs {fixture.away_team}"
        rows.append(
            {
                "label": label,
                "home": fixture.home_team,
                "away": fixture.away_team,
                "league": fixture.league_name,
                "round_name": fixture.round_name,
                "date_str": date_str,
                "status": fixture.status,
            }
        )
    return rows


API_FOOTBALL_LEAGUE_PRESETS = {
    "Personalizado": {"league_id": "", "season": ""},
    "Argentina - Liga Profesional": {"league_id": "128", "season": str(CURRENT_SEASON)},
    "España - LaLiga": {"league_id": "140", "season": str(CURRENT_SEASON)},
    "Inglaterra - Premier League": {"league_id": "39", "season": str(CURRENT_SEASON)},
}


API_FOOTBALL_SEASON_OPTIONS = list(range(API_FOOTBALL_MAX_SEASON, API_FOOTBALL_MIN_SEASON - 1, -1))
API_FOOTBALL_FREE_PLAN_SEASON_OPTIONS = list(
    range(API_FOOTBALL_MAX_SEASON, API_FOOTBALL_FREE_PLAN_MIN_SEASON - 1, -1)
)


TEAM_COMPARISON_PRESETS = {
    "Elegir manualmente": None,
    "Barcelona vs Real Madrid": ("Futbol Club Barcelona", "Real Madrid Club de Fútbol"),
    "Atlético Madrid vs Real Madrid": ("Club Atlético de Madrid S.A.D.", "Real Madrid Club de Fútbol"),
    "Dortmund vs Bayern": ("Borussia Dortmund", "FC Bayern München"),
    "Milan vs Inter": ("Associazione Calcio Milan", "Football Club Internazionale Milano S.p.A."),
    "Aberdeen vs Celtic": ("Aberdeen Football Club", "The Celtic Football Club"),
}


def render_api_fixture_selector(games: pd.DataFrame) -> None:
    render_guide_steps(
        [
            ("Elegí una liga", "Usá una de las opciones frecuentes. No necesitás saber el ID."),
            ("Buscá partidos", "La app trae próximos partidos reales de esa liga."),
            ("Seleccioná uno", "Después muestra el mismo análisis histórico que la comparación manual."),
        ]
    )

    configured_key = get_api_football_key()
    if configured_key:
        api_key = configured_key
        st.caption("La conexión con partidos próximos ya está configurada para esta app.")
    else:
        with st.expander("Clave de acceso para partidos próximos", expanded=True):
            st.markdown(
                """
La app necesita una clave de API-Football para consultar partidos reales en internet.
En una versión publicada, esta clave debería estar configurada por el equipo del proyecto y no debería pedirse a cada usuario.

Este campo aparece solo porque no se detectó una clave configurada en el entorno local.
                """
            )
            api_key_input = st.text_input(
                "Clave de API-Football",
                type="password",
                key="upcoming_api_key",
                help="Para desarrollo local. En producción conviene configurar APIFOOTBALL_API_KEY en el servidor.",
            )
        api_key = api_key_input.strip()

    search_cols = st.columns([2, 1])
    with search_cols[0]:
        preset_name = st.selectbox("Liga", list(API_FOOTBALL_LEAGUE_PRESETS.keys())[1:] + ["Personalizado"])
    with search_cols[1]:
        next_count = st.slider("Cantidad", min_value=5, max_value=30, value=10, step=5)
    preset = API_FOOTBALL_LEAGUE_PRESETS[preset_name]

    with st.expander("Ajustes avanzados"):
        st.caption("Solo cambiá estos campos si conocés los IDs de API-Football.")
        controls = st.columns([1, 1, 1])
        with controls[0]:
            league_id, league_ok = optional_int_filter(
                "ID de liga",
                key=f"upcoming_league_id_{preset_name}",
                value=preset["league_id"],
                help_text="Ejemplo: Argentina 128, LaLiga 140, Premier League 39.",
            )
        with controls[1]:
            season, season_ok = optional_int_filter(
                "Temporada",
                key=f"upcoming_season_{preset_name}",
                value=preset["season"],
                help_text=f"La API y los datos del proyecto llegan hasta {API_FOOTBALL_MAX_SEASON}.",
                max_value=API_FOOTBALL_MAX_SEASON,
            )
        with controls[2]:
            api_team_id, team_ok = optional_int_filter(
                "ID de equipo",
                key="upcoming_team_id",
                help_text="Opcional. Si queda vacío, se buscan partidos de toda la liga.",
            )

    if not api_key:
        st.info("Falta configurar la clave de API-Football para buscar partidos próximos.")
        return

    if not (league_ok and season_ok and team_ok):
        return

    if "upcoming_api_fixtures" not in st.session_state:
        st.session_state.upcoming_api_fixtures = None
        st.session_state.upcoming_api_query = None

    current_query = (next_count, league_id, season, api_team_id)
    if st.session_state.upcoming_api_query not in (None, current_query):
        st.session_state.upcoming_api_fixtures = None
        st.session_state.upcoming_api_query = None

    if st.button("Buscar próximos partidos", type="primary"):
        key_marker = f"{len(api_key)}:{api_key[-4:]}"
        try:
            with st.spinner("Buscando partidos próximos..."):
                fixtures = load_upcoming_fixtures_from_api(
                    next_count,
                    league_id,
                    season,
                    api_team_id,
                    "America/Argentina/Buenos_Aires",
                    key_marker,
                    _api_key=api_key,
                )
            st.session_state.upcoming_api_fixtures = fixtures
            st.session_state.upcoming_api_query = current_query
        except ApiFootballConfigError as exc:
            st.info(str(exc))
            return
        except ApiFootballError as exc:
            if "Free plans do not have access to this season" in str(exc):
                st.warning(
                    f"El plan gratuito de API-Football solo permite temporadas "
                    f"entre {API_FOOTBALL_FREE_PLAN_MIN_SEASON} y {API_FOOTBALL_MAX_SEASON}."
                )
                return
            st.error(f"No se pudo consultar API-Football. {exc}")
            return

    fixtures: list[UpcomingFixture] | None = st.session_state.upcoming_api_fixtures

    if fixtures is None:
        return

    if not fixtures:
        st.warning("No se encontraron partidos próximos para esos filtros.")
        return

    fixture_rows = api_fixture_rows(fixtures)
    selected_idx = st.selectbox(
        "Partido",
        range(len(fixture_rows)),
        format_func=lambda i: fixture_rows[i]["label"],
        key="api_upcoming_fixture",
    )
    render_selected_fixture_analysis(
        games,
        fixture_rows[selected_idx],
        widget_key_prefix="api_fixture",
    )


def _safe_div(numerator: float, denominator: float) -> float:
    try:
        if not denominator:
            return 0.0
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def standings_to_dataframe(standings: list[TeamStanding]) -> pd.DataFrame:
    records = []
    for s in standings:
        played = s.played or 0
        home_p = s.home_played or 0
        away_p = s.away_played or 0
        records.append(
            {
                "Pos": s.rank,
                "Equipo": s.team_name,
                "PJ": played,
                "Pts": s.points,
                "PPG": round(_safe_div(s.points or 0, played), 2),
                "G": s.win,
                "E": s.draw,
                "P": s.loss,
                "GF": s.goals_for,
                "GC": s.goals_against,
                "DG": s.goals_diff,
                "Prom goles/p": round(_safe_div((s.goals_for or 0) + (s.goals_against or 0), played), 2),
                "PPG local": round(_safe_div((s.home_win or 0) * 3 + (s.home_draw or 0), home_p), 2),
                "PPG visit": round(_safe_div((s.away_win or 0) * 3 + (s.away_draw or 0), away_p), 2),
                "Goles local/p": round(_safe_div((s.home_goals_for or 0) + (s.home_goals_against or 0), home_p), 2),
                "Goles visit/p": round(_safe_div((s.away_goals_for or 0) + (s.away_goals_against or 0), away_p), 2),
                "Forma": s.form or "",
                "Zona": s.group_name or "",
            }
        )
    return pd.DataFrame(records)


def _form_breakdown(form: str) -> str:
    form = (form or "").upper()
    wins = form.count("W")
    draws = form.count("D")
    losses = form.count("L")
    return f"{wins}G {draws}E {losses}P en los últimos {len(form)}" if form else "sin datos de forma"


def render_standings_betting_cards(df: pd.DataFrame) -> None:
    if df.empty:
        return
    leader = df.sort_values("Pos").iloc[0]
    best_home = df.sort_values("PPG local", ascending=False).iloc[0]
    best_away = df.sort_values("PPG visit", ascending=False).iloc[0]
    most_goals = df.sort_values("Prom goles/p", ascending=False).iloc[0]
    best_defense = df.sort_values("GC").iloc[0]

    st.markdown("**Claves para la previa**")
    cols = st.columns(5)
    cols[0].metric("Puntero", str(leader["Equipo"]), f'{leader["Pts"]} pts')
    cols[1].metric("Más fuerte de local", str(best_home["Equipo"]), f'{best_home["PPG local"]} PPG')
    cols[2].metric("Más fuerte de visitante", str(best_away["Equipo"]), f'{best_away["PPG visit"]} PPG')
    cols[3].metric("Partidos con más goles", str(most_goals["Equipo"]), f'{most_goals["Prom goles/p"]} goles/p')
    cols[4].metric("Defensa más sólida", str(best_defense["Equipo"]), f'{best_defense["GC"]} GC')


def render_team_betting_read(standings: list[TeamStanding], team_name: str) -> None:
    s = next((x for x in standings if x.team_name == team_name), None)
    if s is None:
        return

    home_p = s.home_played or 0
    away_p = s.away_played or 0
    home_ppg = round(_safe_div((s.home_win or 0) * 3 + (s.home_draw or 0), home_p), 2)
    away_ppg = round(_safe_div((s.away_win or 0) * 3 + (s.away_draw or 0), away_p), 2)
    home_goals = round(_safe_div((s.home_goals_for or 0) + (s.home_goals_against or 0), home_p), 2)
    away_goals = round(_safe_div((s.away_goals_for or 0) + (s.away_goals_against or 0), away_p), 2)

    st.markdown(f"#### Lectura para la previa — {team_name}")
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**De local**")
        st.metric("Puntos por partido", f"{home_ppg}")
        st.metric("Goles totales por partido", f"{home_goals}")
        st.caption(f"Récord local: {s.home_win or 0}G {s.home_draw or 0}E {s.home_loss or 0}P")
        tendency = "tiende a superar los 2.5 goles (Over)" if home_goals >= 2.5 else "tiende a quedar bajo 2.5 goles (Under)"
        st.caption(f"Cuando juega de local, el partido {tendency}.")
    with cols[1]:
        st.markdown("**De visitante**")
        st.metric("Puntos por partido", f"{away_ppg}")
        st.metric("Goles totales por partido", f"{away_goals}")
        st.caption(f"Récord visitante: {s.away_win or 0}G {s.away_draw or 0}E {s.away_loss or 0}P")
        tendency = "tiende a superar los 2.5 goles (Over)" if away_goals >= 2.5 else "tiende a quedar bajo 2.5 goles (Under)"
        st.caption(f"Cuando juega de visitante, el partido {tendency}.")

    st.caption(f"Forma reciente: {s.form or 'sin datos'} ({_form_breakdown(s.form)}).")


def render_league_tab() -> None:
    render_intro_panel(
        "Tabla de posiciones de la liga",
        "Mirá cómo llega cada equipo a la fecha: rendimiento de local y de visitante, "
        "promedio de goles y forma reciente. Son señales útiles para la previa de un partido.",
    )
    render_guide_steps(
        [
            ("Elegí una liga", "No necesitás saber el ID, usá una de las opciones frecuentes."),
            ("Traé la tabla", "La app consulta la posición actual con una sola consulta a internet."),
            ("Leé las señales", "Fijate el rendimiento local/visitante y la tendencia de goles del equipo que te interesa."),
        ]
    )

    configured_key = get_api_football_key()
    if configured_key:
        api_key = configured_key
        st.caption("La conexión con la tabla de posiciones ya está configurada para esta app.")
    else:
        with st.expander("Clave de acceso para la tabla de posiciones", expanded=True):
            st.markdown(
                "La app necesita una clave de API-Football para consultar la tabla en internet. "
                "En una versión publicada debería configurarla el equipo del proyecto."
            )
            api_key = st.text_input(
                "Clave de API-Football",
                type="password",
                key="standings_api_key",
                help="Para desarrollo local. En producción conviene configurar APIFOOTBALL_API_KEY en el servidor.",
            ).strip()

    preset_name = st.selectbox(
        "Liga",
        list(API_FOOTBALL_LEAGUE_PRESETS.keys())[1:] + ["Personalizado"],
        key="standings_preset",
    )
    preset = API_FOOTBALL_LEAGUE_PRESETS[preset_name]
    with st.expander("Ajustes avanzados"):
        st.caption(
            f"El plan gratuito de API-Football permite consultar tablas entre "
            f"{API_FOOTBALL_FREE_PLAN_MIN_SEASON} y {API_FOOTBALL_MAX_SEASON}."
        )
        controls = st.columns(2)
        with controls[0]:
            league_id, league_ok = optional_int_filter(
                "ID de liga",
                key=f"standings_league_id_{preset_name}",
                value=preset["league_id"],
                help_text="Ejemplo: Argentina 128, LaLiga 140, Premier League 39.",
            )
        with controls[1]:
            preset_season = int(preset["season"] or CURRENT_SEASON)
            season = st.selectbox(
                "Temporada",
                API_FOOTBALL_FREE_PLAN_SEASON_OPTIONS,
                index=API_FOOTBALL_FREE_PLAN_SEASON_OPTIONS.index(preset_season)
                if preset_season in API_FOOTBALL_FREE_PLAN_SEASON_OPTIONS
                else 0,
                key=f"standings_season_{preset_name}",
                help=f"Con plan gratuito: {API_FOOTBALL_FREE_PLAN_MIN_SEASON} a {API_FOOTBALL_MAX_SEASON}.",
            )
            season_ok = True

    if not api_key:
        st.info("Falta configurar la clave de API-Football para consultar la tabla de posiciones.")
        return
    if not (league_ok and season_ok) or league_id is None or season is None:
        st.info("Ingresá una liga y una temporada válidas.")
        return

    if st.button("Traer tabla de posiciones", type="primary"):
        key_marker = f"{len(api_key)}:{api_key[-4:]}"
        try:
            with st.spinner("Consultando tabla de posiciones..."):
                standings = load_standings_from_api(league_id, season, key_marker, _api_key=api_key)
            st.session_state.league_standings = standings
            st.session_state.league_standings_query = (league_id, season)
        except ApiFootballConfigError as exc:
            st.info(str(exc))
            return
        except ApiFootballError as exc:
            if "Free plans do not have access to this season" in str(exc):
                st.warning(
                    f"El plan gratuito de API-Football solo permite tablas de posiciones "
                    f"entre {API_FOOTBALL_FREE_PLAN_MIN_SEASON} y {API_FOOTBALL_MAX_SEASON}."
                )
                return
            st.error(f"No se pudo consultar API-Football. {exc}")
            return

    standings: list[TeamStanding] | None = st.session_state.get("league_standings")
    if not standings:
        if standings is not None:
            st.warning(f"No se encontraron posiciones para esa liga y temporada. Probá con otra temporada hasta {API_FOOTBALL_MAX_SEASON}.")
        return

    df = standings_to_dataframe(standings)
    render_standings_betting_cards(df)
    st.dataframe(df.set_index("Pos"), width="stretch")

    team_names = df["Equipo"].tolist()
    selected_team = st.selectbox("Ver lectura para la previa de un equipo", team_names, key="standings_team_read")
    render_team_betting_read(standings, selected_team)

    render_disclaimer()


def render_team_comparison_content(
    games: pd.DataFrame,
    team_a_id: int,
    team_b_id: int,
    team_a_name: str,
    team_b_name: str,
    last_n: int = 10,
    widget_key_prefix: str = "team_compare",
) -> None:
    matches = build_team_match_view(games)
    discipline = load_appearances(data_version("appearances"))[["game_id", "player_club_id", "yellow_cards", "red_cards"]]
    matches = add_team_discipline(matches, discipline)
    comparison = compare_teams(matches, team_a_id, team_b_id, last_n=last_n)

    render_metric_glossary()
    h2h_summary = head_to_head_summary(games, team_a_id, team_b_id)
    h2h_by_team = summarize_head_to_head_by_team(matches, team_a_id, team_b_id)

    render_individual_team_overview(comparison, team_a_name, team_b_name)

    display = comparison[
        ["team_name", "played", "wins", "draws", "losses", "avg_goals_for", "avg_goals_against", "over_2_5_rate", "btts_rate", "avg_yellow_cards", "avg_red_cards", "recent_form"]
    ].rename(
        columns={
            "team_name": "Equipo", "played": "PJ", "wins": "G", "draws": "E", "losses": "P",
            "avg_goals_for": "GF prom.", "avg_goals_against": "GC prom.",
            "over_2_5_rate": "Over 2.5", "btts_rate": "BTTS",
            "avg_yellow_cards": "Amarillas prom.", "avg_red_cards": "Rojas prom.", "recent_form": "Forma",
        }
    )
    display["Over 2.5"] = display["Over 2.5"].map(percent_label)
    display["BTTS"] = display["BTTS"].map(percent_label)
    render_team_insight_text(comparison, h2h_summary, team_a_name, team_b_name, last_n)
    with st.expander("Ver tabla de rendimiento reciente"):
        st.dataframe(display, hide_index=True, width="stretch")

    competitiveness = league_competitiveness(matches, None, None)
    st.caption(
        f"Competitividad de liga: {competitiveness['parity_index'] * 100:.1f}% "
        f"({competitiveness['teams']} equipos, dispersion de puntos {competitiveness['points_std']})."
    )

    monthly = pd.concat(
        [
            monthly_team_performance(matches, team_a_id).assign(team=team_a_name),
            monthly_team_performance(matches, team_b_id).assign(team=team_b_name),
        ],
        ignore_index=True,
    )
    if not monthly.empty:
        st.subheader("Rendimiento por mes")
        monthly = monthly.copy()
        monthly["month_date"] = pd.to_datetime(monthly["month"] + "-01", errors="coerce")
        monthly = monthly.sort_values(["team", "month_date"])
        monthly["win_rate_suavizado"] = (
            monthly.groupby("team")["win_rate"]
            .transform(lambda values: values.rolling(window=3, min_periods=1).mean())
        )
        st.plotly_chart(
            px.line(
                monthly,
                x="month_date",
                y="win_rate_suavizado",
                color="team",
                line_shape="spline",
                labels={"month_date": "Mes", "win_rate_suavizado": "Win Rate suavizado", "team": "Equipo"},
                range_y=[0, 1],
            ),
            width="stretch",
        )

    impact = pd.concat(
        [
            red_card_impact(matches, team_a_id).assign(team=team_a_name),
            red_card_impact(matches, team_b_id).assign(team=team_b_name),
        ],
        ignore_index=True,
    )
    st.subheader("Impacto de tarjeta roja")
    if not impact.empty:
        impact_chart = impact.copy()
        impact_chart["Win Rate"] = impact_chart["win_rate"].astype(float)
        st.plotly_chart(
            px.bar(
                impact_chart,
                x="had_red_card",
                y="Win Rate",
                color="team",
                barmode="group",
                text=impact_chart["Win Rate"].map(lambda value: f"{value * 100:.0f}%"),
                labels={"had_red_card": "Condición", "team": "Equipo"},
                range_y=[0, 1],
            ),
            width="stretch",
        )
        with st.expander("Ver datos de impacto de tarjeta roja"):
            st.dataframe(impact, hide_index=True, width="stretch")

    st.divider()

    render_h2h_overview(h2h_summary, h2h_by_team, team_a_name, team_b_name)

    h2h = head_to_head(games, team_a_id, team_b_id).head(20)
    if not h2h.empty:
        game_labels = [
            f"{row.game_id} - {format_display_date(row.date)} - {row.home_club_name} {row.home_club_goals}-{row.away_club_goals} {row.away_club_name}"
            for row in h2h.itertuples()
        ]
        with st.expander("Ver partidos históricos cargados"):
            selected_game = st.selectbox(
                "Filtrar por partido",
                ["Todos"] + game_labels,
                key=f"{widget_key_prefix}_h2h_game_{team_a_id}_{team_b_id}",
            )
            if selected_game != "Todos":
                selected_game_id = int(selected_game.split(" - ")[0])
                h2h = h2h[h2h["game_id"] == selected_game_id]
            h2h_display = h2h[
                ["date", "season", "home_club_name", "home_club_goals", "away_club_goals", "away_club_name", "competition_id"]
            ].rename(
                columns={
                    "date": "Fecha",
                    "season": "Temporada",
                    "home_club_name": "Local",
                    "home_club_goals": "Goles local",
                    "away_club_goals": "Goles visitante",
                    "away_club_name": "Visitante",
                    "competition_id": "Competición",
                }
            )
            h2h_display["Fecha"] = h2h_display["Fecha"].map(format_display_date)
            st.dataframe(h2h_display, hide_index=True, width="stretch")
    else:
        st.info("No hay enfrentamientos directos para los equipos y filtros elegidos.")


def render_match_tab(games: pd.DataFrame) -> None:
    render_disclaimer()
    render_intro_panel(
        "Analizar equipos",
        "Compará dos equipos con datos históricos para revisar rendimiento reciente, tendencias y enfrentamientos directos.",
    )

    st.markdown('<div class="section-title">Compará dos equipos</div>', unsafe_allow_html=True)
    render_guide_steps(
        [
            ("Filtros", "Podés dejarlos en Todos para usar toda la base."),
            ("Atajo", "Elegí un cruce sugerido si querés probar con equipos que tienen muchos datos."),
            ("Lectura", "La app resume el rendimiento reciente y el historial directo."),
        ]
    )

    selected_competition = "Todos"
    selected_season = "Todos"
    with st.expander("Filtros opcionales"):
        filters = st.columns([1, 1])
        with filters[0]:
            selected_competition = select_optional("Competición", games["competition_id"].dropna().unique().tolist())

        competition_preview = games.copy()
        if selected_competition != "Todos":
            competition_preview = competition_preview[competition_preview["competition_id"] == selected_competition]

        with filters[1]:
            selected_season = select_optional("Temporada", competition_preview["season"].dropna().unique().tolist())

    competition_games = games.copy()
    if selected_competition != "Todos":
        competition_games = competition_games[competition_games["competition_id"] == selected_competition]

    filtered_games = competition_games.copy()
    if selected_season != "Todos":
        filtered_games = filtered_games[filtered_games["season"] == selected_season]

    if filtered_games.empty:
        st.warning("No hay partidos para los filtros elegidos.")
        return

    matches = build_team_match_view(filtered_games)
    discipline = load_appearances(data_version("appearances"))[["game_id", "player_club_id", "yellow_cards", "red_cards"]]
    matches = add_team_discipline(matches, discipline)
    team_options = team_options_from_matches(matches)

    if len(team_options) < 2:
        st.warning("No hay al menos dos equipos con datos para los filtros elegidos.")
        return

    available_presets = {
        label: teams
        for label, teams in TEAM_COMPARISON_PRESETS.items()
        if teams is None or (teams[0] in team_options and teams[1] in team_options)
    }
    selected_preset = st.selectbox("Cruce sugerido", list(available_presets.keys()))

    if available_presets[selected_preset] is None:
        left, right = st.columns([1, 1])
        with left:
            team_a_name = select_required("Primer equipo", list(team_options.keys()))
        if team_a_name is None:
            return

        team_b_options = {name: team_id for name, team_id in team_options.items() if name != team_a_name}
        with right:
            team_b_name = select_required("Segundo equipo", list(team_b_options.keys()))
        if team_b_name is None:
            return
    else:
        team_a_name, team_b_name = available_presets[selected_preset]
        team_b_options = {name: team_id for name, team_id in team_options.items() if name != team_a_name}
        st.success(f"Comparando {team_a_name} contra {team_b_name}.")

    last_n = st.slider(
        "Partidos recientes a considerar",
        min_value=5,
        max_value=50,
        value=10,
        step=5,
        help="Define cuántos partidos recientes de cada equipo se usan para calcular forma, goles y porcentajes.",
    )

    team_a_id = int(team_options[team_a_name])
    team_b_id = int(team_b_options[team_b_name])

    render_team_comparison_content(
        games=filtered_games,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        last_n=last_n,
    )


def render_player_tab() -> None:
    render_intro_panel(
        "Analizar jugadores",
        "Elegí un jugador para ver producción ofensiva, minutos, disciplina y contexto de participación.",
    )
    with st.spinner("Cargando estadisticas de jugadores..."):
        appearances, summary = load_player_data(data_version("appearances"))

    player_names = summary["player_name"].dropna().sort_values().unique().tolist()
    selected_name = select_required("Jugador", player_names)
    if selected_name is None:
        return

    candidates = summary[summary["player_name"] == selected_name].sort_values("minutes", ascending=False)
    selected_player_id = int(candidates.iloc[0]["player_id"])
    selected_summary = candidates.iloc[0]
    history = player_history(appearances, selected_player_id)
    games = load_games(data_version("games"))
    lineups = load_lineups_for_player(selected_player_id, data_version("game_lineups"))
    events = load_game_events(data_version("game_events"))
    player_events = events[(events["player_id"] == selected_player_id) | (events["player_in_id"] == selected_player_id)]
    enriched_history = enrich_player_history(history, games, lineups)

    filters = st.columns([1, 1, 1])
    with filters[0]:
        selected_competition = select_optional("Competición", enriched_history["competition_id"].dropna().unique().tolist())

    competition_history = enriched_history.copy()
    if selected_competition != "Todos":
        competition_history = competition_history[competition_history["competition_id"] == selected_competition]

    with filters[1]:
        selected_season = select_optional("Temporada", competition_history["date"].dt.year.dropna().astype(int).unique().tolist())

    season_history = competition_history.copy()
    if selected_season != "Todos":
        season_history = season_history[season_history["date"].dt.year == int(selected_season)]

    with filters[2]:
        selected_opponent = select_optional("Rival", season_history["opponent_name"].dropna().unique().tolist())

    filtered_history = season_history.copy()
    if selected_opponent != "Todos":
        filtered_history = filtered_history[filtered_history["opponent_name"] == selected_opponent]

    if filtered_history.empty:
        st.warning("No hay datos para los filtros elegidos.")
        return

    metric_columns = st.columns(5)
    metric_columns[0].metric("Partidos", f"{int(selected_summary['matches'])}")
    metric_columns[1].metric("Goles", f"{int(selected_summary['goals'])}")
    metric_columns[2].metric("Asistencias", f"{int(selected_summary['assists'])}")
    metric_columns[3].metric("Goles / 90", f"{selected_summary['goals_per_90']:.2f}")
    metric_columns[4].metric("Contrib. / 90", f"{selected_summary['contributions_per_90']:.2f}")

    substitutions = player_substitution_summary(player_events, selected_player_id)
    st.info(
        f"Lectura rápida: registra {int(selected_summary['goals'])} goles y {int(selected_summary['assists'])} asistencias. "
        f"Cada 90 minutos promedia {selected_summary['goals_per_90']:.2f} goles y "
        f"{selected_summary['contributions_per_90']:.2f} contribuciones directas. "
        f"Ingresó como sustituto {substitutions['substituted_in']} veces y fue reemplazado {substitutions['substituted_out']} veces."
    )

    season_summary = player_season_summary(filtered_history)
    chart_data = season_summary.melt(
        id_vars=["season"],
        value_vars=["goals", "assists"],
        var_name="KPI",
        value_name="Total",
    )
    chart_data["KPI"] = chart_data["KPI"].replace({"goals": "Goles", "assists": "Asistencias"})
    st.plotly_chart(
        px.bar(
            chart_data,
            x="season",
            y="Total",
            color="KPI",
            barmode="group",
            text="Total",
            labels={"season": "Temporada"},
            title="Producción ofensiva por temporada",
        ),
        width="stretch",
    )

    role_summary = player_role_summary(filtered_history)
    st.subheader("Titularidad o suplencia")
    if not role_summary.empty:
        st.plotly_chart(
            px.pie(
                role_summary,
                names="lineup_role",
                values="matches",
                hole=0.45,
                title="Partidos por rol",
            ),
            width="stretch",
        )
        with st.expander("Ver datos de titularidad"):
            st.dataframe(role_summary, hide_index=True, width="stretch")

    formation_summary = player_formation_summary(filtered_history)
    st.subheader("Formaciones más usadas")
    if not formation_summary.empty:
        formation_chart = formation_summary.head(8)
        st.plotly_chart(
            px.bar(
                formation_chart,
                x="team_formation",
                y="matches",
                text="matches",
                labels={"team_formation": "Formación", "matches": "Partidos"},
            ),
            width="stretch",
        )
        with st.expander("Ver datos por formación"):
            st.dataframe(formation_summary.head(10), hide_index=True, width="stretch")

    opponent_summary = player_vs_opponent(enriched_history, None if selected_opponent == "Todos" else selected_opponent)
    st.subheader("Rivales contra los que más produjo")
    if not opponent_summary.empty:
        opponent_chart = opponent_summary.head(8)
        st.plotly_chart(
            px.bar(
                opponent_chart,
                x="opponent_name",
                y="goals",
                text="goals",
                labels={"opponent_name": "Rival", "goals": "Goles"},
            ),
            width="stretch",
        )
        with st.expander("Ver datos por rival"):
            st.dataframe(opponent_summary.head(10), hide_index=True, width="stretch")

    with st.expander("Ver partidos del jugador"):
        player_detail = filtered_history[
            [
                "date",
                "competition_id",
                "opponent_name",
                "lineup_role",
                "team_formation",
                "goals",
                "assists",
                "yellow_cards",
                "red_cards",
                "minutes_played",
            ]
        ].head(30).copy()
        player_detail["date"] = player_detail["date"].map(format_display_date)
        st.dataframe(player_detail, hide_index=True, width="stretch")


def render_referee_tab(games: pd.DataFrame) -> None:
    render_intro_panel(
        "Analizar árbitros",
        "Elegí un árbitro para revisar promedios de goles, tarjetas, penales y tendencia local/visitante.",
    )
    with st.spinner("Cargando estadisticas de arbitros..."):
        referee_matches, referee_summary = load_referee_data(
            games,
            data_version("appearances"),
            data_version("game_events"),
        )

    referees = referee_summary["referee"].dropna().sort_values().tolist()
    selected_referee = select_required("Árbitro", referees)
    if selected_referee is None:
        return

    history = referee_history(referee_matches, selected_referee)

    filters = st.columns([1, 1, 1])
    with filters[0]:
        selected_competition = select_optional("Competición", history["competition_id"].dropna().unique().tolist())

    competition_history = history.copy()
    if selected_competition != "Todos":
        competition_history = competition_history[competition_history["competition_id"] == selected_competition]

    with filters[1]:
        selected_season = select_optional("Temporada", competition_history["season"].dropna().unique().tolist())

    season_history = competition_history.copy()
    if selected_season != "Todos":
        season_history = season_history[season_history["season"] == selected_season]

    team_options = {"Todos": None}
    team_options.update(team_options_from_referee_history(season_history))

    with filters[2]:
        selected_team_name = st.selectbox("Equipo específico", list(team_options.keys()))

    history = season_history.copy()
    if selected_team_name != "Todos":
        selected_team_id = int(team_options[selected_team_name])
        history = history[(history["home_club_id"] == selected_team_id) | (history["away_club_id"] == selected_team_id)]

    if history.empty:
        st.warning("No hay partidos para los filtros elegidos.")
        return

    selected_summary = build_referee_summary(history).iloc[0]

    metric_columns = st.columns(6)
    metric_columns[0].metric("Partidos", f"{int(selected_summary['matches'])}")
    metric_columns[1].metric("Goles prom.", f"{selected_summary['avg_goals']:.2f}")
    metric_columns[2].metric("Amarillas prom.", f"{selected_summary['avg_yellow_cards']:.2f}")
    metric_columns[3].metric("Rojas prom.", f"{selected_summary['avg_red_cards']:.2f}")
    metric_columns[4].metric("Frec. roja", f"{selected_summary['red_card_frequency'] * 100:.1f}%")
    metric_columns[5].metric("Penales prom.", f"{selected_summary['avg_penalties']:.2f}")

    st.info(
        f"Lectura rápida: sus partidos tienen {selected_summary['avg_goals']:.2f} goles de promedio, "
        f"{selected_summary['avg_yellow_cards']:.2f} amarillas y {selected_summary['avg_red_cards']:.2f} rojas. "
        f"El local gana el {selected_summary['home_win_rate'] * 100:.1f}% y el visitante el {selected_summary['away_win_rate'] * 100:.1f}%."
    )

    outcome_data = pd.DataFrame(
        {
            "Resultado": ["Local", "Empate", "Visitante"],
            "Frecuencia": [
                selected_summary["home_win_rate"],
                selected_summary["draw_rate"],
                selected_summary["away_win_rate"],
            ],
        }
    )
    st.plotly_chart(
        px.pie(
            outcome_data,
            names="Resultado",
            values="Frecuencia",
            hole=0.45,
            title="Distribución de resultados",
        ),
        width="stretch",
    )

    with st.expander("Ver partidos dirigidos"):
        referee_detail = history[
            [
                "date",
                "season",
                "home_club_name",
                "home_club_goals",
                "away_club_goals",
                "away_club_name",
                "yellow_cards",
                "red_cards",
                "penalties",
                "competition_id",
            ]
        ].head(30).copy()
        referee_detail["date"] = referee_detail["date"].map(format_display_date)
        st.dataframe(referee_detail, hide_index=True, width="stretch")


render_data_admin()

try:
    games = load_games(data_version("games"))
except Exception as exc:
    st.error(f"No se pudieron cargar los datos principales. Detalle: {exc}")
    st.stop()

st.markdown("""
<div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
    <span style="font-size:32px;">⚽</span>
    <div>
        <div style="font-size:28px; font-weight:800; color:#f1f5f9; line-height:1.1;">BetStats</div>
        <div style="font-size:13px; color:#6b7280; letter-spacing:1px; text-transform:uppercase;">Análisis deportivo para toma de decisiones</div>
    </div>
</div>
""", unsafe_allow_html=True)

matches_tab, players_tab, referees_tab, league_tab = st.tabs(
    [
        "⚽ Equipos",
        "👤 Jugadores",
        "🟨 Árbitros",
        "🏆 Liga",
    ]
)

with matches_tab:
    safe_render(render_match_tab, games)

with players_tab:
    safe_render(render_player_tab)

with referees_tab:
    safe_render(render_referee_tab, games)

with league_tab:
    safe_render(render_league_tab)
