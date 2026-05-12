# Diccionario de datos inicial

Datos detectados en `data/raw`.

| Tabla | Filas aprox. | Peso aprox. | Uso principal |
|---|---:|---:|---|
| `games` | 86.984 | 25 MB | Partidos, goles, local/visitante, arbitro, competicion |
| `club_games` | 173.967 | 10 MB | Vista por club de cada partido |
| `clubs` | 797 | 180 KB | Datos maestros de clubes |
| `players` | 47.703 | 16 MB | Datos maestros de jugadores |
| `appearances` | 1.862.209 | 140 MB | Participacion de jugadores por partido |
| `game_events` | 1.242.946 | 146 MB | Eventos: goles, tarjetas, cambios, penales segun disponibilidad |
| `game_lineups` | 3.049.834 | 322 MB | Formaciones, titulares/suplentes y posiciones |
| `player_valuations` | 616.378 | 29 MB | Evolucion del valor de mercado |
| `transfers` | 157.187 | 13 MB | Transferencias |
| `competitions` | 68 | 11 KB | Competencias |
| `countries` | 119 | 12 KB | Paises |
| `national_teams` | 119 | 25 KB | Selecciones |

## Relaciones clave

- `games.home_club_id` y `games.away_club_id` se relacionan con `clubs.club_id`.
- `club_games.game_id` se relaciona con `games.game_id`.
- `appearances.game_id`, `game_events.game_id` y `game_lineups.game_id` se relacionan con `games.game_id`.
- `appearances.player_id`, `game_events.player_id`, `game_lineups.player_id`, `player_valuations.player_id` y `transfers.player_id` se relacionan con `players.player_id`.

## Tablas recomendadas para empezar

1. `games`: permite comparacion de equipos, Win Rate, BTTS, Over/Under 2.5 y Head-to-Head.
2. `clubs`: permite mostrar nombres y datos base de equipos.
3. `appearances`: permite KPIs de jugadores por 90 minutos.
4. `game_events`: permite tarjetas, goles, asistencias y eventos especiales.
5. `game_lineups`: permite titularidad, suplencia y formaciones.

