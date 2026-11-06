from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YHDP_", env_file=ROOT / ".env", extra="ignore")

    root: Path = ROOT
    sources_dir: Path = ROOT / "sources"
    data_dir: Path = ROOT / "data"
    derived_dir: Path = ROOT / "data" / "derived"

    ollama_url: str = "http://127.0.0.1:11434"
    # qwen3.5 is multimodal, so one model serves text and vision roles (OCR, figures).
    llm_model: str = "qwen3.5:9b-q4_K_M"
    vlm_model: str = "qwen3.5:9b-q4_K_M"
    embed_model: str = "bge-m3"
    # Ollama defaults to a 4,096-token window and silently truncates longer prompts
    # (tagging prompts are ~6k, answers with 6 sources up to ~8k).
    llm_num_ctx: int = 16384
    db_path: Path = ROOT / "data" / "yhdp.db"
    serve_frontends: bool = True
    cors_origins: list[str] = Field(default_factory=list)

    # Routing thresholds (design §4.3, P0 plan T9/T15)
    tag_conf_min: float = 0.7
    ocr_disagreement_max: float = 0.08

    @property
    def blueprint_path(self) -> Path:
        return self.data_dir / "blueprint" / "qd51.yaml"

    @property
    def sources_path(self) -> Path:
        return self.data_dir / "sources.yaml"


settings = Settings()
