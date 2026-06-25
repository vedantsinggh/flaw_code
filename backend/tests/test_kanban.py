import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.kanban.manager import kanban_manager
from app.db.store import tasks_store

def test_kanban_columns():
    assert "Backlog" in kanban_manager.COLUMNS
    assert "Done" in kanban_manager.COLUMNS
    assert len(kanban_manager.COLUMNS) == 8

def test_kanban_task_update():
    # Setup test task
    task_id = "test_task_123"
    tasks_store.set(task_id, {
        "id": task_id,
        "title": "Test Task",
        "description": "Integration test task",
        "status": "Backlog",
        "assigned_agent": "None"
    })
    
    # Transition task
    success = kanban_manager.update_task_status(task_id, "In Progress", "Developer Agent")
    assert success is True
    
    # Fetch and check
    tasks = tasks_store.read_all()
    task = tasks.get(task_id)
    assert task is not None
    assert task["status"] == "In Progress"
    assert task["assigned_agent"] == "Developer Agent"
    
    # Cleanup
    tasks_store.delete(task_id)

def test_kanban_invalid_column():
    success = kanban_manager.update_task_status("non_existent", "InvalidColumn")
    assert success is False
