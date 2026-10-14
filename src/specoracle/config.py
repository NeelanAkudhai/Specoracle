import os
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class ModelsConfig(BaseModel):
    writer: str = "llama-3.3-70b-versatile"
    reference: str = "mixtral-8x7b-32768"
    same: str = "llama-3.3-70b-versatile"

class SandboxConfig(BaseModel):
    run_timeout_s: int = 15
    case_timeout_s: int = 5
    memory_mb: int = 512
    python: str = ""

    @property
    def run_timeout(self) -> int:
        return self.run_timeout_s

    @property
    def case_timeout(self) -> int:
        return self.case_timeout_s

    @property
    def python_bin(self) -> str:
        return self.python if self.python else sys.executable

class PathsConfig(BaseModel):
    data_dir: str = "data"
    cache_db: str = "cache/llm_cache.sqlite"
    results_dir: str = "results"
    problems_file: str = "data/problems.jsonl"
    manifest_file: str = "data/sample_manifest.json"
    raw_results_dir: str = "results/raw"
    tables_dir: str = "results/tables"
    figures_dir: str = "results/figures"
    error_analysis: str = "results/error_analysis.md"

class Config(BaseModel):
    n_problems: int = 60
    seed: int = 42
    n_cases: int = 10
    min_trusted: int = 4
    max_rounds: int = 2
    temperature: float = 0.0
    max_tokens: int = 4096
    rpm: int = 25
    base_url: str = "https://api.groq.com/openai/v1"
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    # Convenience aliases for dual-style property access
    @property
    def models_writer(self) -> str:
        return self.models.writer

    @property
    def models_reference(self) -> str:
        return self.models.reference

    @property
    def models_same(self) -> str:
        return self.models.same

    @property
    def cache_db(self) -> str:
        return self.paths.cache_db

    @property
    def data_dir(self) -> str:
        return self.paths.data_dir

    @property
    def results_dir(self) -> str:
        return self.paths.results_dir

AppConfig = Config

def load_config(config_path: str = "configs/config.yaml") -> Config:
    p = Path(config_path)
    if not p.is_file():
        # Search relative to repo root
        root = Path(__file__).resolve().parents[2]
        alt = root / config_path
        if alt.is_file():
            p = alt
    if not p.is_file():
        return Config()
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Config(**data)
