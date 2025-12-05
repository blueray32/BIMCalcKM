"""BIMCalc configuration management.

Loads configuration from environment variables with sensible defaults.
Follows EU locale standards (EUR currency, metric units, explicit VAT).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


@dataclass
class DBConfig:
    """Database connection configuration."""

    url: str
    pool_size: int = 10
    pool_max_overflow: int = 20
    pool_timeout: int = 30
    echo: bool = False  # SQL logging


@dataclass
class MatchingConfig:
    """Matching algorithm thresholds and tolerances."""

    fuzzy_min_score: int = 70
    auto_accept_min_confidence: int = 85
    size_tolerance_mm: int = 10
    angle_tolerance_deg: int = 5
    dn_tolerance_mm: int = 5
    max_candidates_per_item: int = 50
    class_blocking_enabled: bool = True


@dataclass
class EUConfig:
    """European locale and currency defaults (Irish/EU standards)."""

    currency: str = "EUR"
    vat_included: bool = True
    vat_rate: Decimal = Decimal("0.23")  # 23% Irish/EU standard rate
    decimal_separator: str = ","
    thousands_separator: str = "."
    date_format: str = "%d/%m/%Y"


@dataclass
class LLMConfig:
    """LLM and embeddings configuration for optional RAG agent."""

    provider: str = "openai"  # openai, azure, ollama
    api_key: str | None = None
    embeddings_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4-1106-preview"
    temperature: float = 0.1
    max_tokens: int = 4000

    # Azure-specific
    azure_endpoint: str | None = None
    azure_api_version: str = "2024-02-15-preview"


@dataclass
class VectorConfig:
    """Vector search configuration for pgvector."""

    index_type: str = "ivfflat"  # ivfflat or hnsw
    lists: int = 100  # ivfflat parameter (tune for dataset size)
    similarity_threshold: float = 0.7
    max_results: int = 10


@dataclass
class GraphConfig:
    """Graph database configuration (optional Neo4j)."""

    enabled: bool = False
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "changeme"
    database: str = "neo4j"


@dataclass
class PriceScoutConfig:
    """Price Scout web scraping configuration."""

    # Compliance
    respect_robots_txt: bool = True
    user_agent: str = "BIMCalc PriceScout/1.0 (Contact: support@bimcalc.com)"

    # Rate Limiting
    default_rate_limit_seconds: float = 2.0
    max_parallel_sources: int = 5

    # Retry Logic
    retry_attempts: int = 3
    retry_backoff_base: int = 2

    # Browser Settings
    browser_cdp_url: str | None = None
    browser_timeout_ms: int = 60000

    # Price Validation
    min_price_threshold: Decimal = Decimal("0.01")
    max_price_threshold: Decimal = Decimal("100000.00")

    # Caching (future)
    cache_enabled: bool = False
    cache_ttl_seconds: int = 86400  # 24 hours
    
    
@dataclass
class NotificationsConfig:
    """Notification settings (Slack, Email)."""
    
    slack_webhook_url: str | None = None
    enabled: bool = False


@dataclass
class AppConfig:
    """Root application configuration.

    Loads from environment variables with fail-fast on missing required values.
    """

    org_id: str
    db: DBConfig  # Required, moved before defaults
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    # Feature Flags
    enable_rag: bool = False
    enable_risk_scoring: bool = False

    # Sub-configurations with defaults
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    eu: EUConfig = field(default_factory=EUConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    vector: VectorConfig = field(default_factory=VectorConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    price_scout: PriceScoutConfig = field(default_factory=PriceScoutConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)

    @classmethod
    def from_env(cls) -> AppConfig:
        """Load configuration from environment variables.

        Required environment variables:
        - DATABASE_URL: PostgreSQL connection string

        Optional (with defaults):
        - DEFAULT_ORG_ID: Organization identifier (default: "default")
        - LOG_LEVEL: Logging verbosity (default: "INFO")
        - All other settings have sensible defaults per BIMCalc specifications

        Raises:
            KeyError: If required environment variables are missing
        """
        # Required: DATABASE_URL
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise KeyError(
                "DATABASE_URL environment variable is required. "
                "Example: postgresql+asyncpg://user:pass@localhost:5432/bimcalc"
            )

        # Production Validation
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            secret_key = os.getenv("SECRET_KEY")
            if not secret_key:
                raise KeyError("SECRET_KEY environment variable is required in production.")


        return cls(
            org_id=os.getenv("DEFAULT_ORG_ID", "default"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "json"),
            enable_rag=os.getenv("ENABLE_RAG", "false").lower() == "true",
            enable_risk_scoring=os.getenv("ENABLE_RISK_SCORING", "false").lower()
            == "true",
            db=DBConfig(
                url=database_url,
                pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
                pool_max_overflow=int(os.getenv("DB_POOL_MAX_OVERFLOW", "20")),
                pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
                echo=os.getenv("DB_ECHO", "false").lower() == "true",
            ),
            matching=MatchingConfig(
                fuzzy_min_score=int(os.getenv("FUZZY_MIN_SCORE", "70")),
                auto_accept_min_confidence=int(
                    os.getenv("AUTO_ACCEPT_MIN_CONFIDENCE", "85")
                ),
                size_tolerance_mm=int(os.getenv("SIZE_TOLERANCE_MM", "10")),
                angle_tolerance_deg=int(os.getenv("ANGLE_TOLERANCE_DEG", "5")),
                dn_tolerance_mm=int(os.getenv("DN_TOLERANCE_MM", "5")),
                max_candidates_per_item=int(os.getenv("MAX_CANDIDATES_PER_ITEM", "50")),
                class_blocking_enabled=os.getenv(
                    "CLASS_BLOCKING_ENABLED", "true"
                ).lower()
                == "true",
            ),
            eu=EUConfig(
                currency=os.getenv("DEFAULT_CURRENCY", "EUR"),
                vat_included=os.getenv("VAT_INCLUDED", "true").lower() == "true",
                vat_rate=Decimal(os.getenv("VAT_RATE", "0.23")),
            ),
            llm=LLMConfig(
                provider=os.getenv("LLM_PROVIDER", "openai"),
                api_key=os.getenv("OPENAI_API_KEY"),
                embeddings_model=os.getenv(
                    "EMBEDDINGS_MODEL", "text-embedding-3-large"
                ),
                llm_model=os.getenv("LLM_MODEL", "gpt-4-1106-preview"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                azure_api_version=os.getenv(
                    "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"
                ),
            ),
            vector=VectorConfig(
                index_type=os.getenv("VECTOR_INDEX_TYPE", "ivfflat"),
                lists=int(os.getenv("VECTOR_LISTS", "100")),
            ),
            graph=GraphConfig(
                enabled=os.getenv("NEO4J_URI") is not None,
                uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                user=os.getenv("NEO4J_USER", "neo4j"),
                password=os.getenv("NEO4J_PASSWORD", "changeme"),
                database=os.getenv("NEO4J_DATABASE", "neo4j"),
            ),
            price_scout=PriceScoutConfig(
                respect_robots_txt=os.getenv(
                    "PRICE_SCOUT_RESPECT_ROBOTS", "true"
                ).lower()
                == "true",
                user_agent=os.getenv(
                    "PRICE_SCOUT_USER_AGENT",
                    "BIMCalc PriceScout/1.0 (Contact: support@bimcalc.com)",
                ),
                default_rate_limit_seconds=float(
                    os.getenv("PRICE_SCOUT_RATE_LIMIT", "2.0")
                ),
                max_parallel_sources=int(os.getenv("PRICE_SCOUT_MAX_SOURCES", "5")),
                retry_attempts=int(os.getenv("PRICE_SCOUT_RETRY_ATTEMPTS", "3")),
                browser_cdp_url=os.getenv("PLAYWRIGHT_CDP_URL"),
                browser_timeout_ms=int(os.getenv("PRICE_SCOUT_TIMEOUT_MS", "60000")),
                min_price_threshold=Decimal(os.getenv("PRICE_SCOUT_MIN_PRICE", "0.01")),
                max_price_threshold=Decimal(
                    os.getenv("PRICE_SCOUT_MAX_PRICE", "100000.00")
                ),
                cache_enabled=os.getenv("PRICE_SCOUT_CACHE_ENABLED", "false").lower()
                == "true",
                cache_ttl_seconds=int(os.getenv("PRICE_SCOUT_CACHE_TTL", "86400")),
            ),
            notifications=NotificationsConfig(
                slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
                enabled=os.getenv("SLACK_NOTIFICATIONS_ENABLED", "false").lower()
                == "true",
            ),
        )

    @property
    def config_root(self) -> Path:
        """Root directory for configuration files (classification, flags YAML)."""
        return Path(__file__).parent.parent / "config"

    @property
    def classification_config_path(self) -> Path:
        """Path to classification_hierarchy.yaml."""
        return self.config_root / "classification_hierarchy.yaml"

    @property
    def flags_config_path(self) -> Path:
        """Path to flags.yaml."""
        return self.config_root / "flags.yaml"


# Singleton instance (lazy-loaded)
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get or create singleton AppConfig instance from environment.

    Returns:
        AppConfig: Application configuration

    Raises:
        KeyError: If required environment variables are missing
    """
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config
