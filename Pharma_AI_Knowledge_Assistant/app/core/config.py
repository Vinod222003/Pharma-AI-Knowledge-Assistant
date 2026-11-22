from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Pharma AI Knowledge Assistant"
    environment: str = "development"
    database_url: str = "sqlite:///./data/dev.db"
    jwt_secret: str = "development-only-change-this-secret"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    initial_admin_username: str = "admin"
    initial_admin_password: str = ""
    chroma_path: str = "./data/chroma"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 20
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    rag_min_lexical_terms: int = 2
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()
