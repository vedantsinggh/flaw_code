import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.skills.engine import skill_engine

def test_skill_classification_fastapi():
    loaded = skill_engine.classify_and_load("Build a FastAPI CRUD microservice.")
    assert "fastapi" in loaded
    assert "backend" in loaded

def test_skill_classification_react():
    loaded = skill_engine.classify_and_load("Design a dashboard using React and TailwindCSS.")
    assert "react" in loaded
    assert "frontend" in loaded

def test_skill_classification_security():
    loaded = skill_engine.classify_and_load("Perform a security audit scan for injection vulnerability.")
    assert "security" in loaded

def test_skill_classification_fallback():
    loaded = skill_engine.classify_and_load("Do something extremely vague and unrelated.")
    assert "architecture" in loaded
    assert "backend" in loaded
