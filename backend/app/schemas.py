from pydantic import BaseModel, Field


class ApiConfigInput(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True


class CleaningConfirmation(BaseModel):
    accepted_suggestion_ids: list[str] = Field(default_factory=list)
    target_column: str
    feature_columns: list[str] = Field(default_factory=list)
