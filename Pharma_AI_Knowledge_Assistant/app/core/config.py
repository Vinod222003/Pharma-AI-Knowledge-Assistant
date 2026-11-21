from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Pharma AI Knowledge Assistant"
    environment: str = "development"
    database_url: str = "sqlite:///./data/dev.db"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    jwt_secret: str = "development-only-change-this-secret"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    initial_admin_username: str = "admin"
    initial_admin_password: str = "ChangeThisPassword123!"
    chroma_path: str = "./data/chroma"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 20
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
