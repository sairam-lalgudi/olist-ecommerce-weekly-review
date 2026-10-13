"""Tests for configuration and input file validation."""
import pytest
from pathlib import Path
from src.config import Config, MissingFileError, REQUIRED_TABLES

def test_config_paths_resolution(tmp_path):
    """Test that Config initializes directories properly."""
    cfg = Config(base_dir=tmp_path)
    assert cfg.outputs_dir.exists()
    assert cfg.reports_dir.exists()
    assert cfg.charts_dir.exists()
    assert cfg.payment_tolerance == 0.05

def test_validate_inputs_missing_files(tmp_path):
    """Test that validate_inputs raises MissingFileError when files are absent."""
    empty_dir = tmp_path / "empty_raw"
    empty_dir.mkdir()
    cfg = Config(base_dir=tmp_path)
    cfg.data_dir = empty_dir
    
    with pytest.raises(MissingFileError) as exc_info:
        cfg.validate_inputs()
    assert "Missing required CSV dataset files" in str(exc_info.value)

def test_validate_inputs_with_real_data():
    """Test that validate_inputs succeeds when real files are present in data/raw."""
    cfg = Config()
    if (cfg.data_dir / "olist_orders_dataset.csv").exists():
        resolved = cfg.validate_inputs()
        for tbl in REQUIRED_TABLES:
            assert tbl in resolved
            assert resolved[tbl].exists()
