from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    frontend_origin: str
    app_env: str = "development"
    internal_msg_api_url: str = ""
    internal_msg_api_timeout: int = 5
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50
    admin_reset_token: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    login_max_attempts: int = 5
    login_lock_minutes: int = 30
    sync_cron: str = "0 2 * * *"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
