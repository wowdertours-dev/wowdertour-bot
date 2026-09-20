from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    admin_ids: str = ""
    admin_id: str = ""

    # CRM web authorization. Keep these values only in environment variables.
    crm_username: str = ""
    crm_password: str = ""
    crm_secret_key: str = ""
    crm_session_hours: int = 12
    crm_cookie_secure: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def admins(self) -> list[int]:
        raw_values = []

        if self.admin_ids:
            raw_values.extend(
                self.admin_ids.split(",")
            )

        # Backward compatibility with the old single-admin env name.
        if self.admin_id:
            raw_values.extend(
                self.admin_id.split(",")
            )

        result: list[int] = []

        for raw_value in raw_values:
            value = raw_value.strip()
            if not value:
                continue

            admin_id = int(value)
            if admin_id not in result:
                result.append(admin_id)

        return result

    @property
    def async_database_url(self) -> str:
        url = self.database_url

        if url.startswith("postgres://"):
            return url.replace(
                "postgres://",
                "postgresql+asyncpg://",
                1,
            )

        if url.startswith("postgresql://"):
            return url.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )

        return url


settings = Settings()