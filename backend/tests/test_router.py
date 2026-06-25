import sys
import os
# Ensure backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.router.router import intelligent_router

def test_router_easy_task():
    result = intelligent_router.route_task("Create a simple README file for a python package.")
    assert result["selected_model"] == "qwen2.5-coder:7b"
    assert result["difficulty"] == "Easy"
    assert result["estimated_tokens"] == 2500
    assert result["estimated_cost"] == 0.0
    assert result["confidence"] == 0.95

def test_router_medium_task():
    result = intelligent_router.route_task("Build a FastAPI CRUD API with Pydantic request verification and unit tests.")
    assert result["selected_model"] == "deepseek-r1:1.5b"
    assert result["difficulty"] == "Medium"
    assert result["estimated_tokens"] == 6000

def test_router_complex_task():
    result = intelligent_router.route_task("Design a full system architecture and orchestrate a multi-agent deployment pipeline.")
    assert result["selected_model"] == "groq/deepseek-r1-distill-70b"
    assert result["difficulty"] == "Complex"
    assert result["estimated_tokens"] == 15000
