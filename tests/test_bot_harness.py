import copy
import os
from pathlib import Path
import shutil
import unittest
import atexit

os.environ.setdefault("DISABLE_KEEP_ALIVE", "1")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
TEST_DATA_DIR = Path(__file__).resolve().parent / "_runtime_data"
shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TICKET_DATA_DIR", str(TEST_DATA_DIR))
atexit.register(lambda: shutil.rmtree(TEST_DATA_DIR, ignore_errors=True))

import main  # noqa: E402


class BotHarnessTests(unittest.TestCase):
    def setUp(self):
        self.default_rules = copy.deepcopy(main.DEFAULT_BOT_RULES)
        self.default_server_rules = copy.deepcopy(main.SERVER_RULES)
        main.BOT_RULES = copy.deepcopy(main.DEFAULT_BOT_RULES)
        main.SERVER_RULES = {}

    def tearDown(self):
        main.BOT_RULES = self.default_rules
        main.SERVER_RULES = self.default_server_rules

    def test_validate_rules_config_accepts_server_overrides(self):
        payload = {
            "flows": {
                "gw": {
                    "active": True,
                    "platforms": {
                        "twitter": {
                            "requirements": {
                                "winner_proof": "X proof",
                                "code_proof": "Code proof",
                                "youtube_proof": "YouTube proof",
                            }
                        },
                        "discord": {
                            "requirements": {
                                "winner_proof": "Discord proof",
                                "code_proof": "Code proof",
                                "level2_proof": "Level 2 proof",
                            }
                        },
                        "kick": {
                            "requirements": {
                                "winner_proof": "Kick proof",
                                "supporting_proof": "Extra proof",
                            }
                        },
                    },
                }
            },
            "servers": {
                "12345": {
                    "flows": {
                        "deposit": {
                            "active": True,
                            "inactive_reply": "unused",
                        }
                    }
                }
            },
        }
        normalized = main.validate_rules_config(payload)
        self.assertIn("12345", normalized["servers"])
        self.assertTrue(normalized["servers"]["12345"]["flows"]["deposit"]["active"])

    def test_giveaway_checklist_uses_server_specific_rules(self):
        main.SERVER_RULES = {
            "555": {
                "flows": {
                    "gw": {
                        "active": True,
                        "require_username": False,
                        "platforms": {
                            "twitter": {
                                "requirements": {
                                    "winner_proof": "Winner proof",
                                    "code_proof": "Code proof",
                                }
                            }
                        },
                    }
                }
            }
        }
        state = {
            "flow": "gw",
            "guild_id": 555,
            "gw_platform": "twitter",
            "username": None,
            "proof_signals": {
                "winner_detected": True,
                "code_proof_detected": True,
            },
            "analysis_confidence": 0.9,
            "attachments_total": 1,
            "proof_ready": True,
            "proof_type": "winner",
        }
        checklist = main.checklist_status(state)
        self.assertTrue(checklist["complete"])
        proof = main.proof_status_for_flow(state, "gw")
        self.assertTrue(proof["valid"])

    def test_admin_summary_includes_proof_verdict(self):
        state = {
            "flow": "gw",
            "guild_id": None,
            "gw_platform": "twitter",
            "proof_signals": {
                "winner_detected": True,
                "code_proof_detected": True,
                "youtube_proof_detected": True,
            },
            "analysis_confidence": 0.92,
            "attachments_total": 2,
            "proof_ready": True,
            "proof_type": "winner",
            "summary": "Giveaway winner review",
        }

        class DummyUser:
            guild = None
            id = 99

            def __str__(self):
                return "Tester"

        summary = main.build_admin_summary(DummyUser(), "giveaway payout review", "", True, state=state)
        self.assertIn("[valid proof]", summary)
        self.assertIn("support summary: Giveaway winner review", summary)


if __name__ == "__main__":
    unittest.main()
