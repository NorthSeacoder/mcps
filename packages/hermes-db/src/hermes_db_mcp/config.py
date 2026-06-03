from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    pg_dsn: str = "postgresql://hermes:password@localhost:5432/hermes"
    redis_url: str = "redis://localhost:6379/0"
    embedding_base_url: str = "http://new-api:3000/v1"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 0
    transport: str = "stdio"
    api_token: str = ""
    bucket_hard_threshold: float = 0.95
    bucket_soft_threshold: float = 0.80
    bucket_revisit_days: int = 90
    version: str = "0.2.9"


settings = Settings()
