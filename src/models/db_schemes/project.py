from pydantic import BaseModel, Field, field_validator
from typing import Optional
from bson import ObjectId

class Project(BaseModel):
    id: Optional[ObjectId] = Field(default=None, alias="_id")  # i can remove alias="_id" because populate_by_name=True in Pydantic simplifies field mapping by automatically removing or adding an underscore when names match between Python (e.g., id) and MongoDB (e.g., _id). It eliminates the need for explicit Field(alias="_id")
    project_id: str = Field(..., min_length=1)

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, value):
        if not value.isalnum():
            raise ValueError('project_id must be alphanumeric')
        return value

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True  #  helps if using both 'id' and '_id' so pydantic can handle the mapping automatically and know that id is _id in mongodb
    }

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("project_id", 1)],
                "name": "project_id_index_1",
                "unique": True
            }
        ]
