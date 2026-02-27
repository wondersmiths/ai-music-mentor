"""
Tests for ARCH1: Multi-instrument profiles.
"""

from __future__ import annotations

from ai.instruments.profiles import (
    ERHU_PROFILE,
    INSTRUMENT_PROFILES,
    InstrumentProfile,
    get_profile,
    list_instruments,
)


class TestInstrumentProfiles:
    def test_erhu_profile_exists(self):
        assert "erhu" in INSTRUMENT_PROFILES
        p = INSTRUMENT_PROFILES["erhu"]
        assert p.freq_min == 260.0
        assert p.freq_max == 2400.0
        assert p.default_tonic == "D"

    def test_violin_profile_exists(self):
        p = INSTRUMENT_PROFILES["violin"]
        assert p.freq_min == 196.0
        assert p.family == "bowed_string"

    def test_flute_profile_exists(self):
        p = INSTRUMENT_PROFILES["flute"]
        assert p.family == "wind"
        assert p.pre_emphasis < 0.97  # less pre-emphasis than bowed

    def test_voice_profile_exists(self):
        p = INSTRUMENT_PROFILES["voice"]
        assert p.freq_min == 80.0
        assert p.pre_emphasis == 0.0

    def test_guzheng_profile_exists(self):
        p = INSTRUMENT_PROFILES["guzheng"]
        assert p.family == "plucked_string"

    def test_all_profiles_have_required_fields(self):
        for name, profile in INSTRUMENT_PROFILES.items():
            assert profile.freq_min > 0, f"{name} freq_min"
            assert profile.freq_max > profile.freq_min, f"{name} freq range"
            assert 0 <= profile.yin_threshold <= 1.0, f"{name} yin_threshold"
            assert profile.default_tonic in "CDEFGAB", f"{name} tonic"
            assert len(profile.eval_weights) >= 1, f"{name} eval_weights"


class TestGetProfile:
    def test_get_known_instrument(self):
        p = get_profile("erhu")
        assert p.name == "erhu"

    def test_get_case_insensitive(self):
        p = get_profile("ERHU")
        assert p.name == "erhu"

    def test_get_unknown_falls_back_to_erhu(self):
        p = get_profile("unknown_instrument")
        assert p.name == "erhu"

    def test_get_violin(self):
        p = get_profile("violin")
        assert p.name == "violin"


class TestListInstruments:
    def test_lists_all(self):
        instruments = list_instruments()
        assert "erhu" in instruments
        assert "violin" in instruments
        assert "flute" in instruments
        assert "voice" in instruments
        assert "guzheng" in instruments
        assert len(instruments) == 5


class TestInstrumentsEndpoint:
    def test_instruments_api(self):
        import os
        os.environ.setdefault("DATABASE_URL", "sqlite:///./test_instruments.db")

        from backend.models.database import create_tables
        from backend.main import app
        from fastapi.testclient import TestClient

        create_tables()
        client = TestClient(app)

        resp = client.get("/instruments")
        assert resp.status_code == 200
        data = resp.json()
        assert "instruments" in data
        names = [i["name"] for i in data["instruments"]]
        assert "erhu" in names
        assert "violin" in names
        # Each instrument has required fields
        for inst in data["instruments"]:
            assert "display_name" in inst
            assert "family" in inst
            assert "freq_range" in inst
            assert len(inst["freq_range"]) == 2
