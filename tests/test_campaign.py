import tempfile
import unittest
from pathlib import Path

from src.campaign import CAMPAIGN_MISSIONS, campaign_mission
from src.config import maps_meta
from src.match import Match
from src.modes import MODES
from src.save import StatsDB


class CampaignProgress(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "campaign.db"
        self.db = StatsDB(self.path)

    def tearDown(self):
        self.db.db.close()
        self.temp.cleanup()

    def test_missions_reference_supported_modes_and_maps(self):
        map_ids = {item["id"] for item in maps_meta()}
        self.assertEqual(len(CAMPAIGN_MISSIONS), 9)
        for mission in CAMPAIGN_MISSIONS:
            with self.subTest(mission=mission["name"]):
                self.assertIn(mission["mode"], MODES)
                self.assertIn(mission["map"], map_ids)
                self.assertTrue(mission["briefing"])
                self.assertTrue(mission["objective"])
                match = Match(mission["map"], mission["mode"], seed=1)
                self.assertEqual(match.mode.id, mission["mode"])

    def test_progress_unlocks_chapters_in_order_and_allows_replays(self):
        self.assertEqual(self.db.campaign_progress(), 0)
        with self.assertRaises(ValueError):
            self.db.complete_campaign_mission(1)
        self.assertEqual(self.db.complete_campaign_mission(0), 1)
        self.assertEqual(self.db.complete_campaign_mission(0), 1)
        self.assertEqual(self.db.complete_campaign_mission(1), 2)
        self.assertEqual(self.db.campaign_progress(), 2)

    def test_progress_persists_and_finishes_at_campaign_length(self):
        for index in range(len(CAMPAIGN_MISSIONS)):
            self.assertEqual(self.db.complete_campaign_mission(index), index + 1)
        self.db.db.close()
        self.db = StatsDB(self.path)
        self.assertEqual(self.db.campaign_progress(), len(CAMPAIGN_MISSIONS))
        self.assertEqual(self.db.complete_campaign_mission(len(CAMPAIGN_MISSIONS) - 1),
                         len(CAMPAIGN_MISSIONS))

    def test_invalid_mission_indexes_are_rejected(self):
        for index in (-1, len(CAMPAIGN_MISSIONS), "0"):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    campaign_mission(index)
                with self.assertRaises(ValueError):
                    self.db.complete_campaign_mission(index)


if __name__ == "__main__":
    unittest.main()
