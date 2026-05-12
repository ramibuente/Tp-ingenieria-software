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

from sports_analytics.config import RAW_DIR
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
    fetch_upcoming_fixtures,
    get_api_football_key,
)
from sports_analytics.services.repository import data_version, load_table_columns, load_table_filtered_by_value
from sports_analytics.services.team_matching import build_team_name_index, find_best_team_match


st.set_page_config(page_title="Analisis deportivo", layout="wide")


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
    return load_table_columns("games", columns)


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


def render_data_admin() -> None:
    with st.sidebar.expander("Carga y calidad de datos"):
        table_name = st.selectbox("Tabla a revisar o actualizar", list(TABLES.keys()))
        spec = TABLES[table_name]
        uploaded = st.file_uploader("Cargar CSV actualizado", type="csv")

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
                if st.button("Guardar CSV y regenerar Parquet"):
                    try:
                        RAW_DIR.mkdir(parents=True, exist_ok=True)
                        (RAW_DIR / spec.file_name).write_bytes(raw_bytes)
                        convert_table_to_parquet(table_name)
                        st.cache_data.clear()
                        st.success("Datos actualizados correctamente.")
                    except Exception as exc:
                        st.error(f"No se pudo actualizar la tabla. Detalle: {exc}")

        if st.button("Ver reporte de calidad"):
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


def optional_int_filter(label: str, help_text: str = "") -> tuple[int | None, bool]:
    raw_value = st.text_input(label, help=help_text)
    if not raw_value.strip():
        return None, True

    try:
        return int(raw_value.strip()), True
    except ValueError:
        st.warning(f"{label} debe ser un numero entero.")
        return None, False


def render_h2h_summary_metrics(summary: dict[str, object], team_a_name: str, team_b_name: str) -> None:
    metric_columns = st.columns(4)
    metric_columns[0].metric("Enfrentamientos", f"{int(summary['played'])}")
    metric_columns[1].metric(f"Gano {team_a_name}", f"{float(summary['team_a_win_rate']) * 100:.1f}%")
    metric_columns[2].metric("Empates", f"{float(summary['draw_rate']) * 100:.1f}%")
    metric_columns[3].metric(f"Gano {team_b_name}", f"{float(summary['team_b_win_rate']) * 100:.1f}%")


def percent_label(value: object) -> str:
    return f"{float(value) * 100:.1f}%"


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
    st.subheader("Enfrentamientos directos")
    st.caption("Estos numeros usan solo partidos historicos entre los dos equipos seleccionados.")
    render_h2h_summary_metrics(h2h_summary, team_a_name, team_b_name)

    outcome_data = pd.DataFrame(
        {
            "Resultado": [team_a_name, "Empate", team_b_name],
            "Partidos": [
                int(h2h_summary["team_a_wins"]),
                int(h2h_summary["draws"]),
                int(h2h_summary["team_b_wins"]),
            ],
        }
    )
    chart_columns = st.columns([1, 1])
    with chart_columns[0]:
        st.plotly_chart(
            px.bar(
                outcome_data,
                x="Resultado",
                y="Partidos",
                text="Partidos",
                title="Resultados historicos",
            ),
            width="stretch",
        )

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
        st.dataframe(h2h_display, hide_index=True, width="stretch")


def render_api_football_oracle(games: pd.DataFrame) -> None:
    st.subheader("Oraculo API-Football")
    st.caption(
        "Consulta los proximos 5 partidos y cruza cada cruce con el historial local cargado en el proyecto."
    )

    configured_key = get_api_football_key()
    api_key_input = st.text_input(
        "API key API-Football",
        type="password",
        help="Tambien se puede configurar como APIFOOTBALL_API_KEY, API_FOOTBALL_KEY o APISPORTS_KEY.",
    )
    api_key = api_key_input.strip() or configured_key

    api_filters = st.columns([1, 1, 1])
    with api_filters[0]:
        league_id, league_ok = optional_int_filter("League ID API-Football")
    with api_filters[1]:
        season, season_ok = optional_int_filter("Season API-Football")
    with api_filters[2]:
        api_team_id, team_ok = optional_int_filter("Team ID API-Football")

    if not api_key:
        st.info(
            "Para activar el oraculo, pegá una API key de API-Football o configurá APIFOOTBALL_API_KEY en el entorno."
        )
        return

    if not (league_ok and season_ok and team_ok):
        return

    key_marker = f"{len(api_key)}:{api_key[-4:]}"
    try:
        with st.spinner("Consultando proximos partidos en API-Football..."):
            fixtures = load_upcoming_fixtures_from_api(
                5,
                league_id,
                season,
                api_team_id,
                "America/Argentina/Buenos_Aires",
                key_marker,
                _api_key=api_key,
            )
    except ApiFootballConfigError as exc:
        st.info(str(exc))
        return
    except ApiFootballError as exc:
        st.error(f"No se pudo consultar API-Football. {exc}")
        return

    if not fixtures:
        st.warning("API-Football no devolvio partidos proximos para esos filtros.")
        return

    team_index = build_team_name_index(games)
    for fixture in fixtures:
        home_match = find_best_team_match(fixture.home_team, team_index)
        away_match = find_best_team_match(fixture.away_team, team_index)

        with st.container(border=True):
            st.markdown(f"**{fixture.home_team} vs {fixture.away_team}**")
            detail_parts = [part for part in [fixture.date, fixture.league_name, fixture.round_name, fixture.status] if part]
            if detail_parts:
                st.caption(" | ".join(detail_parts))

            if home_match is None or away_match is None:
                st.info("No se pudo vincular uno de los equipos de API-Football con los nombres del dataset local.")
                continue

            if home_match.team_id == away_match.team_id:
                st.info("Ambos nombres se vincularon al mismo equipo local; no se calcula Head-to-Head.")
                continue

            summary = head_to_head_summary(games, home_match.team_id, away_match.team_id)
            st.caption(
                f"Coincidencias locales: {fixture.home_team} -> {home_match.team_name} "
                f"({home_match.score:.2f}); {fixture.away_team} -> {away_match.team_name} ({away_match.score:.2f})."
            )
            render_h2h_summary_metrics(summary, fixture.home_team, fixture.away_team)

            recent = head_to_head(games, home_match.team_id, away_match.team_id).head(5)
            if recent.empty:
                st.info("No hay enfrentamientos historicos cargados entre estos equipos.")
            else:
                st.dataframe(
                    recent[
                        [
                            "date",
                            "season",
                            "home_club_name",
                            "home_club_goals",
                            "away_club_goals",
                            "away_club_name",
                            "competition_id",
                        ]
                    ],
                    hide_index=True,
                    width="stretch",
                )


def render_match_tab(games: pd.DataFrame) -> None:
    filters = st.columns([1, 1])
    with filters[0]:
        selected_competition = select_optional("Competicion", games["competition_id"].dropna().unique().tolist())

    competition_games = games.copy()
    if selected_competition != "Todos":
        competition_games = competition_games[competition_games["competition_id"] == selected_competition]

    with filters[1]:
        selected_season = select_optional("Temporada", competition_games["season"].dropna().unique().tolist())

    filtered_games = competition_games.copy()
    if selected_season != "Todos":
        filtered_games = filtered_games[filtered_games["season"] == selected_season]

    if filtered_games.empty:
        st.warning("No hay partidos para los filtros elegidos.")
        return

    matches = build_team_match_view(filtered_games)
    discipline = load_appearances(data_version("appearances"))[
        ["game_id", "player_club_id", "yellow_cards", "red_cards"]
    ]
    matches = add_team_discipline(matches, discipline)
    team_options = team_options_from_matches(matches)

    if len(team_options) < 2:
        st.warning("No hay al menos dos equipos con datos para los filtros elegidos.")
        return

    left, right, period = st.columns([1, 1, 1])
    with left:
        team_a_name = select_required("Equipo local o candidato A", list(team_options.keys()))
    if team_a_name is None:
        return

    team_b_options = {name: team_id for name, team_id in team_options.items() if name != team_a_name}
    with right:
        team_b_name = select_required("Equipo visitante o candidato B", list(team_b_options.keys()))
    if team_b_name is None:
        return

    with period:
        last_n = st.slider("Ultimos partidos", min_value=5, max_value=50, value=10, step=5)

    team_a_id = int(team_options[team_a_name])
    team_b_id = int(team_b_options[team_b_name])
    comparison = compare_teams(matches, team_a_id, team_b_id, last_n=last_n)

    render_metric_glossary()
    render_individual_team_overview(comparison, team_a_name, team_b_name)

    competitiveness = league_competitiveness(
        matches,
        selected_competition if selected_competition != "Todos" else None,
        int(selected_season) if selected_season != "Todos" else None,
    )
    st.caption(
        f"Competitividad de liga: {competitiveness['parity_index'] * 100:.1f}% "
        f"({competitiveness['teams']} equipos, dispersion de puntos {competitiveness['points_std']})."
    )

    display = comparison[
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
    display["Over 2.5"] = display["Over 2.5"].map(percent_label)
    display["BTTS"] = display["BTTS"].map(percent_label)
    st.dataframe(display, hide_index=True, width="stretch")

    monthly = pd.concat(
        [
            monthly_team_performance(matches, team_a_id).assign(team=team_a_name),
            monthly_team_performance(matches, team_b_id).assign(team=team_b_name),
        ],
        ignore_index=True,
    )
    if not monthly.empty:
        st.subheader("Rendimiento por mes")
        st.plotly_chart(px.line(monthly, x="month", y="win_rate", color="team", markers=True), width="stretch")

    impact = pd.concat(
        [
            red_card_impact(matches, team_a_id).assign(team=team_a_name),
            red_card_impact(matches, team_b_id).assign(team=team_b_name),
        ],
        ignore_index=True,
    )
    st.subheader("Impacto de tarjeta roja")
    st.dataframe(impact, hide_index=True, width="stretch")

    h2h_summary = head_to_head_summary(filtered_games, team_a_id, team_b_id)
    h2h_by_team = summarize_head_to_head_by_team(matches, team_a_id, team_b_id)
    render_h2h_overview(h2h_summary, h2h_by_team, team_a_name, team_b_name)

    h2h = head_to_head(filtered_games, team_a_id, team_b_id).head(20)
    if not h2h.empty:
        game_labels = [
            f"{row.game_id} - {row.date} - {row.home_club_name} {row.home_club_goals}-{row.away_club_goals} {row.away_club_name}"
            for row in h2h.itertuples()
        ]
        selected_game = st.selectbox("Filtrar por partido historico", ["Todos"] + game_labels)
        if selected_game != "Todos":
            selected_game_id = int(selected_game.split(" - ")[0])
            h2h = h2h[h2h["game_id"] == selected_game_id]
        st.dataframe(
            h2h[
                [
                    "date",
                    "season",
                    "home_club_name",
                    "home_club_goals",
                    "away_club_goals",
                    "away_club_name",
                    "competition_id",
                ]
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No hay enfrentamientos directos para los equipos y filtros elegidos.")

    render_api_football_oracle(games)


def render_player_tab() -> None:
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
        selected_competition = select_optional("Competicion del jugador", enriched_history["competition_id"].dropna().unique().tolist())

    competition_history = enriched_history.copy()
    if selected_competition != "Todos":
        competition_history = competition_history[competition_history["competition_id"] == selected_competition]

    with filters[1]:
        selected_season = select_optional("Temporada del jugador", competition_history["date"].dt.year.dropna().astype(int).unique().tolist())

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
    st.caption(
        f"Impacto de cambios: ingreso como sustituto {substitutions['substituted_in']} veces "
        f"y fue reemplazado {substitutions['substituted_out']} veces."
    )

    season_summary = player_season_summary(filtered_history)
    chart_data = season_summary.melt(
        id_vars=["season"],
        value_vars=["goals", "assists", "yellow_cards", "red_cards"],
        var_name="KPI",
        value_name="Total",
    )
    st.plotly_chart(px.line(chart_data, x="season", y="Total", color="KPI", markers=True), width="stretch")

    role_summary = player_role_summary(filtered_history)
    st.subheader("Titularidad o suplencia")
    st.dataframe(role_summary, hide_index=True, width="stretch")

    formation_summary = player_formation_summary(filtered_history)
    st.subheader("Rendimiento por formacion")
    st.dataframe(formation_summary.head(10), hide_index=True, width="stretch")

    opponent_summary = player_vs_opponent(enriched_history, None if selected_opponent == "Todos" else selected_opponent)
    st.subheader("Conversion contra rival")
    st.dataframe(opponent_summary.head(10), hide_index=True, width="stretch")

    st.dataframe(
        filtered_history[
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
        ].head(30),
        hide_index=True,
        width="stretch",
    )


def render_referee_tab(games: pd.DataFrame) -> None:
    with st.spinner("Cargando estadisticas de arbitros..."):
        referee_matches, referee_summary = load_referee_data(
            games,
            data_version("appearances"),
            data_version("game_events"),
        )

    referees = referee_summary["referee"].dropna().sort_values().tolist()
    selected_referee = select_required("Arbitro", referees)
    if selected_referee is None:
        return

    history = referee_history(referee_matches, selected_referee)

    filters = st.columns([1, 1, 1])
    with filters[0]:
        selected_competition = select_optional("Competicion del arbitro", history["competition_id"].dropna().unique().tolist())

    competition_history = history.copy()
    if selected_competition != "Todos":
        competition_history = competition_history[competition_history["competition_id"] == selected_competition]

    with filters[1]:
        selected_season = select_optional("Temporada del arbitro", competition_history["season"].dropna().unique().tolist())

    season_history = competition_history.copy()
    if selected_season != "Todos":
        season_history = season_history[season_history["season"] == selected_season]

    team_options = {"Todos": None}
    team_options.update(team_options_from_referee_history(season_history))

    with filters[2]:
        selected_team_name = st.selectbox("Historial arbitro-equipo", list(team_options.keys()))

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

    st.caption(f"Sesgo local/visitante: local {selected_summary['home_win_rate'] * 100:.1f}%, visitante {selected_summary['away_win_rate'] * 100:.1f}%.")

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
    st.plotly_chart(px.bar(outcome_data, x="Resultado", y="Frecuencia"), width="stretch")

    st.dataframe(
        history[
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
        ].head(30),
        hide_index=True,
        width="stretch",
    )


render_data_admin()

try:
    games = load_games(data_version("games"))
except Exception as exc:
    st.error(f"No se pudieron cargar los datos principales. Detalle: {exc}")
    st.stop()

st.title("Analisis deportivo para toma de decisiones")

matches_tab, players_tab, referees_tab = st.tabs(
    ["Estadisticas de partidos proximos", "Estadisticas de jugadores especificos", "Estadisticas de arbitros"]
)

with matches_tab:
    safe_render(render_match_tab, games)

with players_tab:
    safe_render(render_player_tab)

with referees_tab:
    safe_render(render_referee_tab, games)
