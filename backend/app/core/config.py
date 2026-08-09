from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ansible_webgui"
    POSTGRES_USER: str = "ansible"
    POSTGRES_PASSWORD: str = "ansible_secret"
    REDIS_URL: str = "redis://redis:6379/0"
    JWT_SECRET: str = "super-secret-jwt-key-change-in-production-32bytes!"
    FERNET_KEY: str = "vX3Y_d-S9g4lE2X5R8zP1qW3vY7zA9bC1dE3fG5hI7k="
    BOOTSTRAP_ADMIN_USER: str = "admin"
    BOOTSTRAP_ADMIN_PASSWORD: str = "adminpassword123"
    COOKIE_SECURE: bool = False
    CONTENT_ROOT: str = "/data/content"
    ARTIFACT_ROOT: str = "/data/artifacts"
    INVENTORY_REPO_NAME: str = "_inventory"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
