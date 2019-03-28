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


async def _fetch_data(session, url, params=None):
    async with session.get(url, params=params) as response:
        return await response.json()


async def _fetch_team_info(team_id=None):
    """Get general team information"""
    base_url = "https://statsapi.mlb.com/api/v1/"
    url = f"{base_url}teams/{team_id}"
    async with aiohttp.ClientSession() as session:
        data = await _fetch_data(session, url)
        team_info = data['teams'][0]
        return team_info


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
    try:
        if len(game['games']) > 1:
            print("eat shit")
            return True
    except KeyError:
        return

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

async def _home_team_record(game):
    return game['teams']['home']['leagueRecord']

async def _away_team_record(game):
    return game['teams']['away']['leagueRecord']

async def _away_team_runs(game):
    return game['teams']['away']['score']

async def _home_team_runs(game):
    return game['teams']['home']['score']

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
    game_data['home_team_record'] = await _home_team_record(game)
    game_data['away_team_record'] = await _away_team_record(game)
    return game_data

async def _parse_played_game(game):
    game_data = {}
    date = await _game_date(game)
    game_date, start_time = await _split_date_time(date)
    game_data['date'] = game_date
    game_data['start_time'] = start_time
    game_data['home_team'] = await _home_team(game)
    game_data['away_team'] = await _away_team(game)
    game_data['home_team_record'] = await _home_team_record(game)
    game_data['away_team_record'] = await _away_team_record(game)
    return game_data

async def _parse_live_game(game):
    game_data = {}
    date = await _game_date(game)
    game_date, start_time = await _split_date_time(date)
    game_data['date'] = game_date
    game_data['start_time'] = start_time
    game_data['home_team'] = await _home_team(game)
    game_data['away_team'] = await _away_team(game)
    game_data['home_team_record'] = await _home_team_record(game)
    game_data['away_team_record'] = await _away_team_record(game)
    game_data['home_team_runs'] = await _home_team_runs(game)
    game_data['away_team_runs'] = await _away_team_runs(game)
    return game_data


class MLB:
    """Create MLB object"""
    base_url = "https://statsapi.mlb.com/api/v1/"
    team_ids = _team_ids()

    def __init__(self, team=None):
        self._team = team
        self._loop = asyncio.get_event_loop()
        self.todays_unplayed_games = []
        self.todays_completed_games = []
        self.live_games = []

        self._gather_data(self._parse_todays_games)

    def __repr__(self):
        return f"MLB Season: {self.current_season}"

    @property
    def current_season(self):
        date = datetime.datetime.now()
        return date.year

    def _gather_data(self, job, **kwargs):
        if self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        result = self._loop.run_until_complete(job(**kwargs))
        self._loop.close()
        return result

    async def _fetch_todays_games(self):
        url = f"{self.base_url}schedule?sportId=1"
        async with aiohttp.ClientSession() as session:
            data = await _fetch_data(session, url)
            if data['totalGames'] == 0:
                games = []
            else:
                games = data['dates'][0]['games']
            return games

    async def _parse_game(self, game, double_header_check=True):
        if double_header_check:
            double_header = await _double_header_check(game)
        else:
            double_header = None
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
            elif game_type == 'R' and game_state == 'Live':
                game_data = await _parse_live_game(game)
                self.live_games.append(game_data)

    async def _parse_today_games(self, game):
        game_type = await _game_type(game)
        game_state = await _game_state(game)
        if game_type == 'R' and game_state == 'Preview':
            game_data = await _parse_unplayed_game(game)
            self.todays_unplayed_games.append(game_data)
        elif game_type == 'R' and game_state == 'Final':
            game_data = await _parse_played_game(game)
            self.todays_completed_games.append(game_data)
        elif game_type == 'R' and game_state == 'Live':
            game_data = await _parse_live_game(game)
            self.live_games.append(game_data)

    async def _parse_todays_games(self):
        games = await self._fetch_todays_games()
        if games:
            for game in games:
                await self._parse_today_games(game)


class MLBTeam(MLB):
    def __init__(self, team_name):
        super().__init__()
        self._team = team_name
        self.id = self._team_id()
        self.name = self._team_name()
        self.played_games = []
        self.remaining_games = []
        self.info = self._gather_data(self._parse_team_info)
        self.roster = self._gather_data(self._fetch_roster, team_id=self.id)

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

    async def _parse_games(self, season=None):
        if not season:
            season = self.current_season
        schedule = await self._fetch_schedule(team_id=self.id, season=season)
        self.schedule = schedule
        for game in schedule:
            await self._parse_game(game)
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
        url = f"{self.base_url}schedule"
        async with aiohttp.ClientSession() as session:
            data = await _fetch_data(session, url, params=params)
            games = data['dates']
            return games

    async def _fetch_roster(self, team_id='111'):
        url = f"{self.base_url}teams/{team_id}/roster"
        async with aiohttp.ClientSession() as session:
            data = await _fetch_data(session, url)
            return data['roster']


if __name__ == '__main__':
    import time
    s = time.perf_counter()
    elapsed = time.perf_counter() - s
    mlb = MLB()
    print(json.dumps(mlb.live_games, indent=2))
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
