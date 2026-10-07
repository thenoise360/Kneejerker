"""Player risk signals for the This Week hub (release 1).

Pure functions turn database rows into tiers plus reason keys and facts. They
never write sentences: hubCopy.js and the Jinja macros turn keys into words.
"""

RECENT_GAMES = 5
REGULAR_MINUTES = 45          # below this usual average, one quiet game tells us nothing
SUBBED_EARLY_SHARE = 0.75     # last game under 75% of usual minutes counts as taken off early
BOOKED_MORE_OFTEN = 1.5       # recent card rate this many times the season rate
MIN_GAMES_FOR_RATE = 5
RULED_OUT_STATUSES = ('s', 'u', 'n')   # suspended, left the club, not available
# Yellow-card bans aren't in the official API: (last gameweek the count applies, cards
# that trigger a ban). Matches the 2026/27 rules; check them each summer.
BOOKING_BANS = ((19, 5), (32, 10))


#################################################
#                  Fetchers                     #
#################################################

def fetch_squad_history_rows(cursor, year_start, element_ids, before_gameweek):
    """Every game this season before the coming gameweek, for the given players."""
    if not element_ids:
        return []
    placeholders = ', '.join(['%s'] * len(element_ids))
    cursor.execute(f"""
        SELECT element, fixture, kickoff_time, minutes, yellow_cards
        FROM elementsummary_history
        WHERE year_start = %s AND round < %s AND element IN ({placeholders})
        ORDER BY kickoff_time
    """, (year_start, before_gameweek, *element_ids))
    return cursor.fetchall()


#################################################
#                 Pure shaping                  #
#################################################

def player_signals(history_rows):
    """Group each player's games, oldest first, into what assess_risk needs."""
    games = {}
    for r in history_rows:
        # Keyed by fixture so a row stored twice counts once.
        games.setdefault(r['element'], {})[r['fixture']] = r
    signals = {}
    for element, by_fixture in games.items():
        rows = sorted(by_fixture.values(), key=lambda r: str(r['kickoff_time'] or ''))
        recent = rows[-RECENT_GAMES:]
        signals[element] = {
            'minutes_recent': [int(r['minutes'] or 0) for r in recent],
            'yellows_recent': [int(r['yellow_cards'] or 0) for r in recent],
            'yellows_season': sum(int(r['yellow_cards'] or 0) for r in rows),
            'games_season': len(rows),
        }
    return signals


#################################################
#                Pure choosing                  #
#################################################

def _tier(pct):
    if pct >= 75:
        return 'high'
    if pct >= 50:
        return 'medium'
    return 'low'


def _ban_threshold(gameweek):
    for last_gameweek, cards in BOOKING_BANS:
        if gameweek <= last_gameweek:
            return cards
    return None


def assess_risk(player, signals, upcoming_gameweek):
    """Each kind of risk uses its own signal; the highest one sets the tier."""
    chance, status, news = player.get('chance'), player.get('status'), player.get('news') or ''
    if chance == 0 or status in RULED_OUT_STATUSES or (status == 'i' and chance is None):
        return {'pct': 100, 'tier': 'confirmed', 'reasons': [{'key': 'ruled_out', 'news': news}]}

    pct, reasons = 0, []
    if chance is not None and chance < 100:
        pct = max(pct, 100 - chance)
        reasons.append({'key': 'official_doubt', 'chance': chance, 'news': news})

    s = signals or {}
    minutes = s.get('minutes_recent') or []
    if len(minutes) >= 2:
        last, earlier = minutes[-1], minutes[:-1]
        usual = round(sum(earlier) / len(earlier))
        if usual >= REGULAR_MINUTES:
            if last == 0:
                pct = max(pct, 75)
                reasons.append({'key': 'missed_last_game', 'usual_minutes': usual})
            elif last < usual * SUBBED_EARLY_SHARE:
                pct = max(pct, 50)
                reasons.append({'key': 'subbed_early', 'minutes': last, 'usual_minutes': usual})

    season_cards = s.get('yellows_season', 0)
    ban_at = _ban_threshold(upcoming_gameweek)
    if ban_at is not None and season_cards == ban_at - 1:
        pct = max(pct, 75)
        reasons.append({'key': 'one_booking_from_ban', 'cards': season_cards})

    recent_cards, games = s.get('yellows_recent') or [], s.get('games_season', 0)
    if games >= MIN_GAMES_FOR_RATE and recent_cards and season_cards:
        if sum(recent_cards) / len(recent_cards) > (season_cards / games) * BOOKED_MORE_OFTEN:
            pct = max(pct, 50)
            reasons.append({'key': 'booked_more_often', 'recent_cards': sum(recent_cards),
                            'recent_games': len(recent_cards)})

    return {'pct': pct, 'tier': _tier(pct), 'reasons': reasons}
