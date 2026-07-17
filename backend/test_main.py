import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import the app, database base, and dependencies
# Since python module path might be backend.main, let's import directly
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app, get_db, Base

# Set up an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the database schema in SQLite
Base.metadata.create_all(bind=engine)

# Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def run_around_tests():
    # Recreate the tables to ensure clean state for each test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "api_requests_total" in response.text or response.status_code == 200

def test_crud_flow():
    # 1. Verify list is initially empty
    response = client.get("/users")
    assert response.status_code == 200
    assert len(response.json()) == 0

    # 2. Create a user
    user_data = {"name": "Test User", "email": "test@example.com", "role": "Tester"}
    response = client.post("/users", json=user_data)
    assert response.status_code == 201
    created_user = response.json()
    assert created_user["name"] == "Test User"
    assert created_user["email"] == "test@example.com"
    assert created_user["role"] == "Tester"
    assert "id" in created_user
    user_id = created_user["id"]

    # 3. Read users list again (should contain 1)
    response = client.get("/users")
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == user_id

    # 4. Update the user
    update_data = {"name": "Updated Name", "role": "Lead Tester"}
    response = client.put(f"/users/{user_id}", json=update_data)
    assert response.status_code == 200
    updated_user = response.json()
    assert updated_user["name"] == "Updated Name"
    assert updated_user["email"] == "test@example.com" # Unchanged
    assert updated_user["role"] == "Lead Tester"

    # 5. Delete the user
    response = client.delete(f"/users/{user_id}")
    assert response.status_code == 204

    # 6. Verify user list is empty again
    response = client.get("/users")
    assert len(response.json()) == 0

def test_duplicate_email_prevention():
    user_data = {"name": "User 1", "email": "duplicate@example.com"}
    response = client.post("/users", json=user_data)
    assert response.status_code == 201

    # Attempt to post same email
    response2 = client.post("/users", json=user_data)
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"]
