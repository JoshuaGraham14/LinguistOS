from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./linguistos.db"
    cors_origins: str = "http://localhost:3000"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    # Deepgram is used for streaming speech-to-text (Nova-3). TTS still uses
    # OpenAI's tts-1 model, so both keys are needed when voice mode is in use.
    deepgram_api_key: str = ""


settings = Settings()
