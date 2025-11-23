from os import environ
from typing import Optional, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API settings
    port: int = 5001
    host: str = "0.0.0.0"

    # Database settings
    db_uri: str

    # WhatsApp settings
    whatsapp_host: str
    whatsapp_basic_auth_password: Optional[str] = None
    whatsapp_basic_auth_user: Optional[str] = None

    # AWS Bedrock settings
    aws_region: str = "eu-central-1"

    # Optional settings
    debug: bool = False
    log_level: str = "INFO"
    logfire_token: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        arbitrary_types_allowed=True,
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def apply_env(self) -> Self:
        if self.logfire_token:
            environ["LOGFIRE_TOKEN"] = self.logfire_token

        # Set AWS region for boto3
        if self.aws_region:
            environ["AWS_DEFAULT_REGION"] = self.aws_region

        return self
