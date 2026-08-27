"""
Unit tests for the parts of the ingestion script that don't require hitting
the live API: record validation and raw-file writing.

Deliberately not mocking the whole HTTP layer here yet -- that's a natural
next addition (responses/requests-mock) once the client has more logic
worth testing in isolation. Starting with the cheap, high-value tests.
"""

import json

from ingestion.fetch_games import validate_game, write_raw_json

VALID_GAME = {
    "id": 1,
    "date": "2024-10-22",
    "season": 2024,
    "home_team": {"id": 1, "abbreviation": "BOS"},
    "visitor_team": {"id": 2, "abbreviation": "NYK"},
}


def test_validate_game_accepts_complete_record():
    assert validate_game(VALID_GAME) is True


def test_validate_game_rejects_missing_fields():
    broken_game = {"id": 1, "date": "2024-10-22"}  # missing team/season fields
    assert validate_game(broken_game) is False


def test_validate_game_rejects_empty_record():
    assert validate_game({}) is False


def test_write_raw_json_creates_file_with_expected_contents(tmp_path):
    games = [VALID_GAME]

    output_path = write_raw_json(games, season=2024, raw_data_dir=tmp_path)

    assert output_path.exists()
    contents = json.loads(output_path.read_text())
    assert contents["season"] == 2024
    assert contents["record_count"] == 1
    assert contents["data"] == games


def test_write_raw_json_creates_missing_directory(tmp_path):
    nested_dir = tmp_path / "does" / "not" / "exist"

    output_path = write_raw_json([VALID_GAME], season=2024, raw_data_dir=nested_dir)

    assert output_path.exists()
