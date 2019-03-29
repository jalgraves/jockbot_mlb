import sys
import unittest
import nose

from datetime import datetime

from jockbot_mlb.mlb import MLB, MLBTeam


class MLBTest(unittest.TestCase):

    def setUp(self):
        self.date = datetime.now()
        self.year = self.date.year
    
    def test_mlb_object(self):
        """Test MLB object is created without error"""
        mlb = MLB()
        self.assertEqual(mlb.current_season, self.year, "Wrong Season")

    def test_mlb_team(self):
        """Test MLBTeam object is created without error"""
        sox = MLBTeam('boston')
        season_games = len(sox.played_games) + len(sox.remaining_games)
        message = "Played games and remaining games do not equal 162"
        self.assertEqual(season_games, 162, message)


if __name__ == '__main__':
    sys.path.insert(1, "/jockbot_mlb/jockbot_mlb")
    nose.main()
