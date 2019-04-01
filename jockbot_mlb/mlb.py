import aiohttp
import asyncio
import json
import logging
import os

from datetime import datetime, timedelta
from dateutil import tz


BASE_URL = "https://statsapi.mlb.com/api/v1/"
DATE = datetime.now()


class MLBException(Exception):
    """Base class for MLB exceptions"""
    pass


def _team_ids():
    """Get configuration"""
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config


async def _fetch_data(session, url, params=None):
    async with session.get(url, params=params) as response:
        try:
            data = await response.json()
        except aiohttp.client_exceptions.ClientConnectorError:
            data = await response.json()
        return data


async def _fetch_team_info(team_id=None):
    """Get general team information"""
    url = f"{BASE_URL}teams/{team_id}"
    async with aiohttp.ClientSession() as session:
        data = await _fetch_data(session, url)
        team_info = data['teams'][0]
        return team_info


async def _fetch_roster(team_id=None):
    """Get team's roster"""
    url = f"{BASE_URL}teams/{team_id}/roster"
    async with aiohttp.ClientSession() as session:
        data = await _fetch_data(session, url)
        return data['roster']


async def _fetch_games_by_date(start_date=None, end_date=None):
    """Get all MLB games within a given time range"""
    params = {
        "sportId": "1",
        "startDate": start_date,
        "endDate": end_date
    }
    url = f"{BASE_URL}schedule"
    async with aiohttp.ClientSession() as session:
        data = await _fetch_data(session, url, params=params)
        if data['totalGames'] == 0:
            games = []
        else:
            games = data['dates'][0]['games']
        return games


async def _convert_time(time):
    """Convert time from UTC to local and from 24 hour to 12"""
    from_zone = tz.tzutc()
    to_zone = tz.gettz('US/Eastern')
    utc = datetime.strptime(time, '%H:%M:%S') + timedelta(hours=1)
    utc = utc.replace(tzinfo=from_zone)
    eastern = utc.astimezone(to_zone)
    start_time = datetime.strftime(eastern, '%I:%M')
    if start_time[0] == '0':
        start_time = start_time[1:]
    return start_time


async def _double_header_check(game):
    try:
        if len(game['games']) > 1:
            return True
    except KeyError:
        return


async def _split_date_time(date_and_time):
    date, time = date_and_time.split('T')
    game_time = await _convert_time(time.strip('Z'))
    return date, game_time


async def _fetch_linescore(game_id):
    url = f"{BASE_URL}game/{game_id}/linescore"
    async with aiohttp.ClientSession() as session:
        data = await _fetch_data(session, url)
        return data


async def _parse_game(game, game_state=None):
    game_data = {}
    date = game['gameDate']
    game_date, start_time = await _split_date_time(date)
    game_data['state'] = game_state
    game_data['detailed_state'] = game['status']['detailedState']
    if game_state == 'Live' or game_state == 'Final':
        game_data['linescore'] = await _fetch_linescore(game['gamePk'])
    game_data['date'] = game_date
    game_data['start_time'] = start_time
    game_data['home_team'] = game['teams']['home']['team']['name']
    game_data['away_team'] = game['teams']['away']['team']['name']
    game_data['home_team_score'] = game['teams']['home'].get('score')
    game_data['away_team_score'] = game['teams']['away'].get('score')
    game_data['home_team_record'] = game['teams']['home']['leagueRecord']
    game_data['away_team_record'] = game['teams']['away']['leagueRecord']
    return game_data


def _get_loop():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    return loop


class MLB:
    """Create MLB object"""
    team_ids = _team_ids()

    def __init__(self, team=None):
        self._team = team
        self._loop = _get_loop()
        self.todays_games = []
        self.todays_unplayed_games = []
        self.todays_completed_games = []
        self.live_games = []
        self.yesterdays_games = []

        self._gather_data(self._gather_todays_games)
        self._gather_data(self._gather_yesterdays_games)

    def __repr__(self):
        return f"MLB Season: {self.current_season}"

    @property
    def current_season(self):
        return DATE.year

    def _gather_data(self, job, **kwargs):
        if self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        result = self._loop.run_until_complete(job(**kwargs))
        self._loop.close()
        return result

    async def _parse_todays_games(self, game):
        game_type = game['gameType']
        game_state = game['status']['abstractGameState']
        if game_type == 'R':
            game_data = await _parse_game(game, game_state=game_state)
            if game_state == 'Preview':
                self.todays_unplayed_games.append(game_data)
            elif game_state == 'Live':
                self.live_games.append(game_data)
            elif game_state == 'Final':
                self.todays_completed_games.append(game_data)
            self.todays_games.append(game_data)

    async def _gather_todays_games(self):
        date = datetime.strftime(DATE, '%Y-%m-%d')
        games = await _fetch_games_by_date(start_date=date, end_date=date)
        if games:
            for game in games:
                await self._parse_todays_games(game)

    async def _gather_yesterdays_games(self):
        date = datetime.strftime(DATE - timedelta(1), '%Y-%m-%d')
        games = await _fetch_games_by_date(start_date=date, end_date=date)
        if games:
            for game in games:
                game_data = await _parse_game(game)
                self.yesterdays_games.append(game_data)


class MLBTeam(MLB):
    def __init__(self, team_name):
        super().__init__()
        self._team = team_name
        self.id = self._team_id()
        self.name = self._team_name()
        self.todays_games = []
        self.live_games = []
        self.played_games = []
        self.remaining_games = []
        self.info = self._gather_data(self._parse_team_info)
        self.roster = self._gather_data(_fetch_roster, team_id=self.id)

        self._gather_data(self._parse_games)

    def __repr__(self):
        message = [
            f"Team: {self.name}",
            f"Current Season: {self.current_season}",
            f"Games Played: {len(self.played_games)}",
            f"Games Remaining: {len(self.remaining_games)}"
        ]
        return "\n".join(message)

    def past_season_games(self, season=None):
        """Get all games played from a given season"""
        data = self._gather_data(self._fetch_schedule, season=season)
        yield from data

    def _team_id(self):
        team_id = None
        team_name = self._team.title()
        for team in self.team_ids.keys():
            if team_name in team:
                team_id = self.team_ids[team]
                break
        if not team_id:
            raise MLBException(f"Team {self._team} Not Found")
        return team_id

    def _team_name(self):
        name = None
        team_name = self._team.title()
        for team in self.team_ids.keys():
            if team_name in team:
                name = team
                break
        if not name:
            raise MLBException(f"Team {self._team} Not Found")
        return name

    async def _parse_team_game(self, game):
        double_header = await _double_header_check(game)
        if not double_header:
            game = game['games'][0]
            game_type = game['gameType']
            game_state = game['status']['abstractGameState']
            if game_type == 'R':
                game_data = await _parse_game(game, game_state=game_state)
                if game_state == 'Preview':
                    self.remaining_games.append(game_data)
                elif game_state == 'Live':
                    self.live_games.append(game_data)
                elif game_state == 'Final':
                    self.played_games.append(game_data)

    async def _parse_games(self, season=None):
        if not season:
            season = self.current_season
        schedule = await self._fetch_schedule(team_id=self.id, season=season)
        self.schedule = schedule
        for game in schedule:
            await self._parse_team_game(game)
        return schedule

    async def _parse_team_info(self):
        info = await _fetch_team_info(team_id=self.id)
        return info

    async def _fetch_schedule(self, team_id=None, season=None):
        """Get the full schedule for a given season"""
        if not team_id:
            team_id = self.id
        elif not season:
            season = self.current_season
        params = {
            "sportId": "1",
            "teamId": team_id,
            "startDate": f"{season}-01-01",
            "endDate": f"{season}-12-31"
        }
        url = f"{BASE_URL}schedule"
        async with aiohttp.ClientSession() as session:
            data = await _fetch_data(session, url, params=params)
            games = data['dates']
            return games


if __name__ == '__main__':
    import time
    s = time.perf_counter()
    elapsed = time.perf_counter() - s
    mlb = MLB()
    print(json.dumps(mlb.todays_games, indent=2))
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
