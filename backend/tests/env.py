import os

# Import this before anything from app. `unittest discover -s tests` doesn't run
# tests/__init__.py, so every test module does it explicitly. Real values in
# .env are overridden on purpose: tests can't reach a real database or API key.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@localhost:5432/test"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only"
os.environ["LLM_PROVIDER"] = "ollama"
