"""Sports-specific display labels and alert text."""

COMPETITION_NAMES = {
    "PL": "PREMIER LEAGUE",
    "PD": "LA LIGA",
    "BL1": "BUNDESLIGA",
    "SA": "SERIE A",
    "FL1": "LIGUE 1",
    "CL": "CHAMPIONS LEAGUE",
    "ELC": "CHAMPIONSHIP",
    "EL1": "LEAGUE ONE",
    "EL2": "LEAGUE TWO",
    "DED": "EREDIVISIE",
    "PPL": "PRIMEIRA LIGA",
    "BSA": "BRASIL SERIE A",
    "WC": "WORLD CUP",
    "EC": "EUROPEAN CHAMPIONSHIP",
}


def competition_label(code):
    return COMPETITION_NAMES.get(code.upper(), code.upper())


def _score(home_goals, away_goals):
    if home_goals is None or away_goals is None:
        return "V"
    return f"{home_goals}-{away_goals}"


def _minute(minute, injury_time):
    if minute is None:
        return ""
    if injury_time:
        return f" {minute}+{injury_time}'"
    return f" {minute}'"


def alert_text(alert):
    if alert.kind == "KO":
        return f"KO {alert.home} V {alert.away}"
    score = _score(alert.home_goals, alert.away_goals)
    if alert.kind == "GOAL":
        return (
            f"GOAL {alert.home} {score} {alert.away}"
            f"{_minute(alert.minute, alert.injury_time)}"
        )
    return f"{alert.kind} {alert.home} {score} {alert.away}"
