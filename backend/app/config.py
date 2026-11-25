from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    mysql_host: str = 'localhost'
    mysql_port: int = 3306
    mysql_user: str = 'root'
    mysql_password: str = ''
    mysql_database: str = 'agri_assistant'
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-2.5-flash'
    whisper_model: str = 'small'
    chroma_path: str = 'data/chroma_db'
    upload_dir: str = 'data/uploads'
    tts_audio_dir: str = 'data/generated_audio'
    retrieval_distance_threshold: float = 1.15

    @property
    def chroma_dir(self) -> Path: return ROOT / self.chroma_path
    @property
    def uploads_dir(self) -> Path: return ROOT / self.upload_dir
    @property
    def audio_dir(self) -> Path: return ROOT / self.tts_audio_dir
    @property
    def database_url(self) -> str:
        return f'mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}'

settings = Settings()
