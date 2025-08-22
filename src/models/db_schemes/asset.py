from pydantic import BaseModel, Field, field_validator
from typing import Optional
from bson import ObjectId
from datetime import datetime

class Asset(BaseModel):
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    asset_project_id: ObjectId
    asset_type: str = Field(..., min_length=1)
    asset_name: str = Field(..., min_length=1)
    asset_size: Optional[int] = Field(default=None, ge=0)
    asset_config: Optional[dict] = Field(default=None)
    asset_pushed_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("asset_type", "asset_name")
    @classmethod
    def validate_non_empty(cls, value):
        if not value or not value.strip():
            raise ValueError("Field must not be empty")
        return value

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("asset_project_id", 1), ("asset_name", 1)],
                "name": "asset_project_id_name_index_1",
                "unique": True,
            },
        ]
