from sqlalchemy.orm import Session
from models import Todo
from schemas import TodoCreate, TodoUpdate

def get_todos(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve a list of todos."""
    return db.query(Todo).offset(skip).limit(limit).all()

def get_todo_by_id(db: Session, todo_id: int):
    """Retrieve a single todo by ID."""
    return db.query(Todo).filter(Todo.id == todo_id).first()

def create_todo(db: Session, todo: TodoCreate):
    """Create a new todo."""
    db_todo = Todo(**todo.model_dump())
    db.add(db_todo)
    db.commit()
    db.refresh(db_todo)
    return db_todo

def update_todo(db: Session, todo_id: int, todo: TodoUpdate):
    """Update an existing todo."""
    db_todo = get_todo_by_id(db, todo_id)
    if db_todo:
        todo_data = todo.model_dump(exclude_unset=True)
        for key, value in todo_data.items():
            setattr(db_todo, key, value)
        db.commit()
        db.refresh(db_todo)
    return db_todo

def toggle_todo_status(db: Session, todo_id: int):
    """Toggle the completed status of a todo."""
    db_todo = get_todo_by_id(db, todo_id)
    if db_todo:
        db_todo.completed = not db_todo.completed
        db.commit()
        db.refresh(db_todo)
    return db_todo

def delete_todo(db: Session, todo_id: int):
    """Delete a todo."""
    db_todo = get_todo_by_id(db, todo_id)
    if db_todo:
        db.delete(db_todo)
        db.commit()
    return db_todo