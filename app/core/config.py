from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    SECRET_KEY: str = Field(
        validation_alias="JWT_SECRET_KEY"
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        validation_alias="JWT_EXPIRE_MINUTES"
    )

    DATABASE_URL: str
    UPLOAD_DIR: str = "app/uploads"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )
settings = Settings()