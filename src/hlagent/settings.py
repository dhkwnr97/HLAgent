from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HLAGENT_", extra="ignore")
    home: Path = Field(default_factory=lambda: Path.home() / ".local/share/hlagent")
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    ui_port: int = 8501
    plink2: str = "plink2"
    plink: str = "plink1.9"
    bcftools: str = "bcftools"
    java: str = "java"
    beagle_jar: Path | None = None
    cookhla_image: str = "dhkwnr97/cookhla@sha256:0b374cef9cc352cfaa7aa5e89ad49d5b6c64274a6eb8100acbb7f6f452f0c5d6"
    hatk_root: Path | None = None
    allow_web: bool = False
    embedding_model: str | None = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    inbox: Path | None = None

    def initialize(self):
        self.home = self.home.expanduser().resolve()
        for sub in ("projects", "knowledge/inbox", "tools", "logs"):
            (self.home / sub).mkdir(parents=True, exist_ok=True)
        self.home.chmod(0o700)
        if self.beagle_jar is None:
            candidate = self.home / "tools/beagle.27Feb25.75f.jar"
            if candidate.exists():
                self.beagle_jar = candidate
        return self

    @property
    def db_path(self) -> Path:
        return self.home / "state.sqlite3"

    @property
    def knowledge_inbox(self) -> Path:
        return self.inbox or self.home / "knowledge/inbox"
