import json

from league_finder.sources.bowlero import feed_center_numbers, parse_centers, parse_feed

CENTER = {
    "centerNumber": 280,
    "centerType": "BOWLING",
    "name": "Lucky Strike Hemet",
    "brand": "Lucky Strike",
    "slug": "lucky-strike-hemet",
    "streetAddress": "2850 W. Florida Ave",
    "city": "Hemet",
    "state": "California",
    "zipCode": "92545",
    "location": {"lon": -117.004, "lat": 33.7474},
}

FEED = {
    "records": [
        {
            "centerNumber": 280,
            "leagues": [
                {
                    "bowlingCenterNumber": 280,
                    "description": "A semi-competitive Mixed League. ",
                    "endDate": "2027-06-08T00:00:00",
                    "leagueDays": [{"constantName": "Tuesday", "description": "Tuesday"}],
                    "leagueFrequencyDescription": "Once Every Week",
                    "leagueId": "ae45c94f-8429-4cfd-ab1e-813db4310f8b",
                    "leagueName": "Laughlin Mixers Fall 2026",
                    "leagueSkillLevels": ["Novice", "Experienced"],
                    "leagueSubTypeDescription": "Mixed",
                    "leagueTypeDescription": "Traditional",
                    "meetingDateTime": "2026-09-29T18:00:00",
                    "numberOfTeams": 28,
                    "numberOfWeeks": 36,
                    "playersPerTeam": 4,
                    "startDateTime": "2026-10-06T18:30:00",
                }
            ],
        }
    ]
}


def next_page(payload: str) -> str:
    # Mimic how Next.js embeds its payload: split across push() string chunks.
    half = len(payload) // 2
    return "".join(
        f"<script>self.__next_f.push([1,{json.dumps(part)}])</script>"
        for part in (payload[:half], payload[half:])
    )


def test_parse_centers():
    payload = '4:["$","$Lf",null,' + json.dumps({"centers": [CENTER]}) + "]\n"
    assert parse_centers(next_page(payload)) == [CENTER]


def test_parse_feed():
    [league] = parse_feed(FEED, {280: CENTER})
    assert league.source_id == "ae45c94f-8429-4cfd-ab1e-813db4310f8b"
    assert league.url == "https://www.bowlero.com/join-league/ae45c94f-8429-4cfd-ab1e-813db4310f8b"
    assert league.center_name == "Lucky Strike Hemet"
    assert (league.latitude, league.longitude) == (33.7474, -117.004)
    assert league.day_of_week == "Tuesday"
    assert (league.start_time, league.season_start, league.season_weeks) == ("18:30", "2026-10-06", 36)
    assert league.team_size == 4
    assert league.league_type == "Traditional"
    assert league.description == "A semi-competitive Mixed League."
    assert league.extra["skill_levels"] == ["Novice", "Experienced"]
    assert league.extra["end_date"] == "2027-06-08"


def test_parse_feed_unknown_center():
    [league] = parse_feed(FEED, {})
    assert league.center_name is None and league.name == "Laughlin Mixers Fall 2026"


def test_feed_center_numbers():
    url = "https://cheetah-api-proxy.bellum.ai/api/leagues?centerNumbers=262%2C638%2C777"
    assert feed_center_numbers(url) == {262, 638, 777}
