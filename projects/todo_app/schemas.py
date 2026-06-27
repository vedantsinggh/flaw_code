from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Base Schema with shared attributes
class TodoBase(BaseModel):
    title: str = Field(..., example="Buy groceries")
    description: Optional[str] = Field(None, example="Milk, Eggs, Bread")
    completed: bool = Field(False, example=False)

# Schema for creating a new Todo
class TodoCreate(TodoBase):
    pass

# Schema for updating a Todo (all fields optional)
class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, example="Buy groceries")
    description: Optional[str] = Field(None, example="Milk, Eggs, Bread")
    completed: Optional[bool] = Field(None, example=True)

# Schema for API responses (includes database generated fields)
class TodoResponse(TodoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True