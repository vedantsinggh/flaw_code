from typing import List
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Import models, schemas, crud, and database utilities
import models
import schemas
import crud
from database import engine, get_db

# Create the database tables
models.Base.metadata.create_all(bind=engine)

# Initialize the FastAPI app
app = FastAPI(
    title="Todo API",
    description="A simple REST API for managing Todos using FastAPI and SQLAlchemy",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---

@app.get("/todos", response_model=List[schemas.TodoResponse], tags=["Todos"])
def read_todos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve all todos.
    """
    todos = crud.get_todos(db, skip=skip, limit=limit)
    return todos

@app.post("/todos", response_model=schemas.TodoResponse, status_code=status.HTTP_201_CREATED, tags=["Todos"])
def create_todo(todo: schemas.TodoCreate, db: Session = Depends(get_db)):
    """
    Create a new todo.
    """
    return crud.create_todo(db=db, todo=todo)

@app.put("/todos/{todo_id}", response_model=schemas.TodoResponse, tags=["Todos"])
def update_todo(todo_id: int, todo: schemas.TodoUpdate, db: Session = Depends(get_db)):
    """
    Update a todo (Title, Description, or Completed status).
    """
    db_todo = crud.update_todo(db=db, todo_id=todo_id, todo=todo)
    if db_todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return db_todo

@app.patch("/todos/{todo_id}/toggle", response_model=schemas.TodoResponse, tags=["Todos"])
def toggle_todo(todo_id: int, db: Session = Depends(get_db)):
    """
    Toggle the 'completed' status of a todo.
    """
    db_todo = crud.toggle_todo_status(db=db, todo_id=todo_id)
    if db_todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return db_todo

@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Todos"])
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    """
    Delete a todo.
    """
    db_todo = crud.delete_todo(db=db, todo_id=todo_id)
    if db_todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return None