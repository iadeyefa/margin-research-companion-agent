import re


TEAM_ALIASES: dict[str, tuple[str, ...]] = {
    "Atlanta Hawks": ("atlanta hawks", "hawks", "atl"),
    "Boston Celtics": ("boston celtics", "celtics", "bos"),
    "Brooklyn Nets": ("brooklyn nets", "nets", "bkn", "bk"),
    "Charlotte Hornets": ("charlotte hornets", "hornets", "cha"),
    "Chicago Bulls": ("chicago bulls", "bulls", "chi"),
    "Cleveland Cavaliers": ("cleveland cavaliers", "cavaliers", "cavs", "cle"),
    "Dallas Mavericks": ("dallas mavericks", "mavericks", "mavs", "dal"),
    "Denver Nuggets": ("denver nuggets", "nuggets", "den"),
    "Detroit Pistons": ("detroit pistons", "pistons", "det"),
    "Golden State Warriors": ("golden state warriors", "warriors", "gsw", "golden state"),
    "Houston Rockets": ("houston rockets", "rockets", "hou"),
    "Indiana Pacers": ("indiana pacers", "pacers", "ind"),
    "LA Clippers": ("la clippers", "los angeles clippers", "clippers", "lac"),
    "Los Angeles Lakers": ("los angeles lakers", "lakers", "lal"),
    "Memphis Grizzlies": ("memphis grizzlies", "grizzlies", "mem"),
    "Miami Heat": ("miami heat", "heat", "mia"),
    "Milwaukee Bucks": ("milwaukee bucks", "bucks", "mil"),
    "Minnesota Timberwolves": ("minnesota timberwolves", "timberwolves", "wolves", "min"),
    "New Orleans Pelicans": ("new orleans pelicans", "pelicans", "pels", "nop"),
    "New York Knicks": ("new york knicks", "knicks", "nyk"),
    "Oklahoma City Thunder": ("oklahoma city thunder", "thunder", "okc"),
    "Orlando Magic": ("orlando magic", "magic", "orl"),
    "Philadelphia 76ers": ("philadelphia 76ers", "76ers", "sixers", "phi"),
    "Phoenix Suns": ("phoenix suns", "suns", "phx"),
    "Portland Trail Blazers": ("portland trail blazers", "trail blazers", "blazers", "por"),
    "Sacramento Kings": ("sacramento kings", "kings", "sac"),
    "San Antonio Spurs": ("san antonio spurs", "spurs", "sas"),
    "Toronto Raptors": ("toronto raptors", "raptors", "tor"),
    "Utah Jazz": ("utah jazz", "jazz", "uta"),
    "Washington Wizards": ("washington wizards", "wizards", "was"),
}

TEAM_BY_ABBREVIATION = {
    aliases[-1].upper(): team_name
    for team_name, aliases in TEAM_ALIASES.items()
}


def extract_mentioned_teams(question: str) -> list[str]:
    lowered = question.lower()
    found: list[str] = []

    alias_pairs = sorted(
        (
            (alias, team_name)
            for team_name, aliases in TEAM_ALIASES.items()
            for alias in aliases
        ),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )

    for alias, team_name in alias_pairs:
        if re.search(rf"\b{re.escape(alias)}\b", lowered) and team_name not in found:
            found.append(team_name)

    return found
