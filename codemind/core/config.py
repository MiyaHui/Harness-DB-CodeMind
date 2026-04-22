from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()


class Config:
    _instance = None

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._load()

    def _load(self) -> None:
        self.neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
        self.neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")

        self.llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4")
        self.openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

        self.token_budget_default: int = int(os.getenv("TOKEN_BUDGET_DEFAULT", "8000"))
        self.token_budget_max: int = int(os.getenv("TOKEN_BUDGET_MAX", "16000"))

        self.impact_confidence_threshold: float = float(os.getenv("IMPACT_CONFIDENCE_THRESHOLD", "0.1"))
        self.impact_max_depth: int = int(os.getenv("IMPACT_MAX_DEPTH", "5"))

        self.risk_weight_blast_radius: float = float(os.getenv("RISK_WEIGHT_BLAST_RADIUS", "0.25"))
        self.risk_weight_critical_path: float = float(os.getenv("RISK_WEIGHT_CRITICAL_PATH", "0.20"))
        self.risk_weight_data_sensitivity: float = float(os.getenv("RISK_WEIGHT_DATA_SENSITIVITY", "0.20"))
        self.risk_weight_change_frequency: float = float(os.getenv("RISK_WEIGHT_CHANGE_FREQUENCY", "0.15"))
        self.risk_weight_coupling: float = float(os.getenv("RISK_WEIGHT_COUPLING", "0.10"))
        self.risk_weight_test_coverage: float = float(os.getenv("RISK_WEIGHT_TEST_COVERAGE", "0.10"))

        self.data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_risk_weights(self) -> dict[str, float]:
        return {
            "blast_radius": self.risk_weight_blast_radius,
            "critical_path": self.risk_weight_critical_path,
            "data_sensitivity": self.risk_weight_data_sensitivity,
            "change_frequency": self.risk_weight_change_frequency,
            "coupling": self.risk_weight_coupling,
            "test_coverage": self.risk_weight_test_coverage,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "llm_provider": self.llm_provider,
            "embedding_model": self.embedding_model,
            "token_budget_default": self.token_budget_default,
            "impact_max_depth": self.impact_max_depth,
            "impact_confidence_threshold": self.impact_confidence_threshold,
        }


def get_config() -> Config:
    return Config()
