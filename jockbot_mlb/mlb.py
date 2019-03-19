import aiohttp
import asyncio
import datetime
import json
import os

from dateutil import tz


class MLBException(Exception):
    """Base class for MLB exceptions"""
    pass


def _team_ids():
    """Get configuration"""
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_file, 'r') as f:
        config = json.load(f)
    return config


async def _fetch_data(session, url):
    async with session.get(url) as response:
        return await response.json()


async def _convert_time(time):
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    utc = datetime.datetime.strptime(time, '%H:%M:%S')
    utc = utc.replace(tzinfo=from_zone)
    eastern = utc.astimezone(to_zone)
    start_time = datetime.datetime.strftime(eastern, '%H:%M')
    if int(start_time.split(':')[0]):
        hour, minute = start_time.split(':')
        hour = int(hour) - 12
        start_time = f"{hour}:{minute}"
    return start_time


async def _double_header_check(game):
    if len(game['games']) > 1:
        return True

async def _game_type(game):
    return game['gameType']

async def _game_state(game):
    return game['status']['abstractGameState']

async def _game_date(game):
    return game['gameDate']

async def _home_team(game):
    return game['teams']['home']['team']['name']

async def _away_team(game):
    return game['teams']['away']['team']['name']

async def _split_date_time(date_and_time):
    date, time = date_and_time.split('T')
    game_time = await _convert_time(time.strip('Z'))
    return date, game_time

async def _parse_unplayed_game(game):
    game_data = {}
    date = await _game_date(game)
    game_date, start_time = await _split_date_time(date)
    game_data['date'] = game_date
    game_data['start_time'] = start_time
    game_data['home_team'] = await _home_team(game)
    game_data['away_team'] = await _away_team(game)
    return game_data

async def _parse_played_game(game):
    game_data = {}
    date = await _game_date(game)
    game_date, start_time = await _split_date_time(date)
    game_data['date'] = game_date
    game_data['start_time'] = start_time
    game_data['home_team'] = await _home_team(game)
    game_data['away_team'] = await _away_team(game)
    return game_data


class MLB:
    """Create MLB object"""
    base_url = "https://statsapi.mlb.com/api/v1/"
    team_ids = _team_ids()

    def __init__(self, team=None):
        self._team = team
        self._loop = asyncio.get_event_loop()

    def __repr__(self):
        return f"MLB Season: {self.current_season}"

    @property
    def current_season(self):
        date = datetime.datetime.now()
        return date.year
        
    def _gather_data(self, job, **kwargs):
        if self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(job(**kwargs))
        self._loop.close()


class MLBTeam(MLB):
    def __init__(self, team_name):
        super().__init__()
        self._team = team_name
        self.played_games = []
        self.remaining_games = []

        self._gather_data(self._fetch_schedule, team_id=self.team_id)
        self._gather_data(self._fetch_roster, team_id=self.team_id)

    def __repr__(self):
        return f"Team: {self._team}"

    @property
    def team_id(self):
        team_id = None
        team_name = self._team.title()
        for team in self.team_ids.keys():
            if team_name in team:
                team_id = self.team_ids[team]
                break
        if not team_id:
            raise MLBException(f"Team {self._team} Not Found")
        return team_id

    async def _fetch_schedule(self, team_id='111'):
        url = f"{self.base_url}schedule?teamId={team_id}&sportId=1&startDate=2019-01-01&endDate=2019-12-31"
        async with aiohttp.ClientSession() as session:
            data = await _fetch_data(session, url)
            games = data['dates']
            for game in games:
                await self._parse_game(game)
            self.schedule = data
            return data

    async def _fetch_roster(self, team_id='111'):
        url = f"{self.base_url}teams/{team_id}/roster"
        async with aiohttp.ClientSession() as session:
            data = await _fetch_data(session, url)
            self.roster = data['roster']

    async def _parse_game(self, game):
        double_header = await _double_header_check(game)
        if not double_header:
            game = game['games'][0]
            game_type = await _game_type(game)
            game_state = await _game_state(game)
            if game_type == 'R' and game_state == 'Preview':
                game_data = await _parse_unplayed_game(game)
                self.remaining_games.append(game_data)
            elif game_type == 'R' and game_state == 'Final':
                game_data = await _parse_played_game(game)
                self.played_games.append(game_data)


if __name__ == '__main__':
    sox = MLBTeam('boston')
    print(sox)
