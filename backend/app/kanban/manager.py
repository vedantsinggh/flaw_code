import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.db.store import tasks_store

logger = logging.getLogger("forgeos.kanban")

class KanbanManager:
    # Strict flow order
    COLUMNS = [
        "Backlog",
        "Planning",
        "In Progress",
        "Review",
        "Testing",
        "Security",
        "Documentation",
        "Done"
    ]

    def get_tasks_by_column(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Groups tasks from the JSON store by their current Kanban column status.
        """
        all_tasks = tasks_store.read_all()
        board = {col: [] for col in self.COLUMNS}
        
        for task_id, task in all_tasks.items():
            status = task.get("status", "Backlog")
            if status in board:
                board[status].append(task)
            else:
                board["Backlog"].append(task)

        return board

    def update_task_status(self, task_id: str, next_status: str, assigned_agent: Optional[str] = None) -> bool:
        """
        Safely transitions a task from one column to another.
        """
        if next_status not in self.COLUMNS:
            logger.error(f"Invalid column status: {next_status}")
            return False

        all_tasks = tasks_store.read_all()
        task = all_tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found.")
            return False

        current_status = task.get("status", "Backlog")
        logger.info(f"Transitioning task '{task['title']}' from '{current_status}' to '{next_status}'")

        task["status"] = next_status
        task["updated_at"] = datetime.utcnow().isoformat()
        
        if assigned_agent:
            task["assigned_agent"] = assigned_agent

        all_tasks[task_id] = task
        tasks_store.write_all(all_tasks)
        return True

kanban_manager = KanbanManager()
