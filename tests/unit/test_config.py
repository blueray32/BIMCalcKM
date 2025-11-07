"""Unit tests for BIMCalc configuration management.

Tests AppConfig loading from environment variables, validation, and defaults.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from bimcalc.config import AppConfig, DBConfig, EUConfig, MatchingConfig


class TestAppConfig:
    """Test AppConfig creation and validation."""

    def test_from_env_requires_database_url(self, monkeypatch):
        """Test DATABASE_URL is required."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(KeyError) as exc_info:
            AppConfig.from_env()

        assert "DATABASE_URL" in str(exc_info.value)

    def test_from_env_with_minimal_config(self, monkeypatch):
        """Test loading with only required env vars."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

        config = AppConfig.from_env()

        assert config.db.url == "sqlite:///./test.db"
        assert config.org_id == "default"
        assert config.log_level == "INFO"

    def test_from_env_with_custom_org_id(self, monkeypatch):
        """Test custom organization ID."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setenv("DEFAULT_ORG_ID", "acme-construction")

        config = AppConfig.from_env()

        assert config.org_id == "acme-construction"

    def test_from_env_with_custom_log_level(self, monkeypatch):
        """Test custom log level."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        config = AppConfig.from_env()

        assert config.log_level == "DEBUG"

    def test_from_env_db_config_with_pool_settings(self, monkeypatch):
        """Test database pool configuration."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/bimcalc")
        monkeypatch.setenv("DB_POOL_SIZE", "20")
        monkeypatch.setenv("DB_POOL_MAX_OVERFLOW", "30")
        monkeypatch.setenv("DB_POOL_TIMEOUT", "60")
        monkeypatch.setenv("DB_ECHO", "true")

        config = AppConfig.from_env()

        assert config.db.pool_size == 20
        assert config.db.pool_max_overflow == 30
        assert config.db.pool_timeout == 60
        assert config.db.echo is True


class TestMatchingConfig:
    """Test matching algorithm configuration."""

    def test_default_matching_config(self, monkeypatch):
        """Test default matching thresholds."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

        config = AppConfig.from_env()

        assert config.matching.fuzzy_min_score == 70
        assert config.matching.auto_accept_min_confidence == 85
        assert config.matching.size_tolerance_mm == 10
        assert config.matching.angle_tolerance_deg == 5
        assert config.matching.class_blocking_enabled is True

    def test_custom_matching_thresholds(self, monkeypatch):
        """Test custom matching thresholds from environment."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setenv("FUZZY_MIN_SCORE", "80")
        monkeypatch.setenv("AUTO_ACCEPT_MIN_CONFIDENCE", "90")
        monkeypatch.setenv("SIZE_TOLERANCE_MM", "5")
        monkeypatch.setenv("ANGLE_TOLERANCE_DEG", "3")
        monkeypatch.setenv("CLASS_BLOCKING_ENABLED", "false")

        config = AppConfig.from_env()

        assert config.matching.fuzzy_min_score == 80
        assert config.matching.auto_accept_min_confidence == 90
        assert config.matching.size_tolerance_mm == 5
        assert config.matching.angle_tolerance_deg == 3
        assert config.matching.class_blocking_enabled is False


class TestEUConfig:
    """Test EU locale configuration."""

    def test_default_eu_config(self, monkeypatch):
        """Test default EU settings (Irish/EU standard)."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

        config = AppConfig.from_env()

        assert config.eu.currency == "EUR"
        assert config.eu.vat_included is True
        assert config.eu.vat_rate == Decimal("0.23")  # 23% Irish standard
        assert config.eu.decimal_separator == ","
        assert config.eu.thousands_separator == "."
        assert config.eu.date_format == "%d/%m/%Y"

    def test_custom_vat_settings(self, monkeypatch):
        """Test custom VAT configuration."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setenv("DEFAULT_CURRENCY", "USD")
        monkeypatch.setenv("VAT_INCLUDED", "false")
        monkeypatch.setenv("VAT_RATE", "0.20")

        config = AppConfig.from_env()

        assert config.eu.currency == "USD"
        assert config.eu.vat_included is False
        assert config.eu.vat_rate == Decimal("0.20")


class TestLLMConfig:
    """Test LLM and embeddings configuration."""

    def test_default_llm_config(self, monkeypatch):
        """Test default LLM settings."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

        config = AppConfig.from_env()

        assert config.llm.provider == "openai"
        assert config.llm.api_key is None
        assert config.llm.embeddings_model == "text-embedding-3-large"
        assert config.llm.llm_model == "gpt-4-1106-preview"

    def test_custom_llm_provider(self, monkeypatch):
        """Test custom LLM provider configuration."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setenv("LLM_PROVIDER", "azure")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")

        config = AppConfig.from_env()

        assert config.llm.provider == "azure"
        assert config.llm.api_key == "sk-test-key"
        assert config.llm.azure_endpoint == "https://test.openai.azure.com"


class TestGraphConfig:
    """Test graph database configuration."""

    def test_graph_disabled_by_default(self, monkeypatch):
        """Test graph features disabled when NEO4J_URI not set."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.delenv("NEO4J_URI", raising=False)

        config = AppConfig.from_env()

        assert config.graph.enabled is False

    def test_graph_enabled_with_uri(self, monkeypatch):
        """Test graph features enabled when NEO4J_URI set."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "admin")
        monkeypatch.setenv("NEO4J_PASSWORD", "secret")

        config = AppConfig.from_env()

        assert config.graph.enabled is True
        assert config.graph.uri == "bolt://localhost:7687"
        assert config.graph.user == "admin"
        assert config.graph.password == "secret"


class TestConfigPaths:
    """Test configuration file path helpers."""

    def test_config_root_path(self, monkeypatch):
        """Test config_root returns correct path."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

        config = AppConfig.from_env()

        assert config.config_root.name == "config"
        assert config.config_root.exists()

    def test_classification_config_path(self, monkeypatch):
        """Test classification_config_path returns correct file."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

        config = AppConfig.from_env()

        assert config.classification_config_path.name == "classification_hierarchy.yaml"
        assert config.classification_config_path.parent.name == "config"

    def test_flags_config_path(self, monkeypatch):
        """Test flags_config_path returns correct file."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

        config = AppConfig.from_env()

        assert config.flags_config_path.name == "flags.yaml"
        assert config.flags_config_path.parent.name == "config"


class TestDBConfig:
    """Test database configuration dataclass."""

    def test_db_config_defaults(self):
        """Test DBConfig default values."""
        db_config = DBConfig(url="sqlite:///./test.db")

        assert db_config.url == "sqlite:///./test.db"
        assert db_config.pool_size == 10
        assert db_config.pool_max_overflow == 20
        assert db_config.pool_timeout == 30
        assert db_config.echo is False

    def test_db_config_custom_values(self):
        """Test DBConfig with custom values."""
        db_config = DBConfig(
            url="postgresql://localhost/bimcalc",
            pool_size=25,
            pool_max_overflow=50,
            pool_timeout=60,
            echo=True
        )

        assert db_config.url == "postgresql://localhost/bimcalc"
        assert db_config.pool_size == 25
        assert db_config.pool_max_overflow == 50
        assert db_config.pool_timeout == 60
        assert db_config.echo is True
