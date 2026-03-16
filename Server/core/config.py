from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NPTEL_BASE_URL:str
    class Config:
        env_file=".env"

settings=Settings()