from pydantic import BaseModel, Field, HttpUrl


class DeepSeekConfigInput(BaseModel):
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-chat"
    enabled: bool = True


class CleaningConfirmation(BaseModel):
    accepted_suggestion_ids: list[str] = Field(default_factory=list)
    target_column: str
    feature_columns: list[str] = Field(default_factory=list)

