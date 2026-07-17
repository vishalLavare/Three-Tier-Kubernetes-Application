import os
import sys
import time
import logging
from typing import List, Optional
from dotenv import load_dotenv

# Load local environment variables from .env file if it exists
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backend")

# Database Configuration from environment variables (configured via ConfigMap and Secrets in K8s)
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Detect if running within a testing environment
IS_TESTING = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None

# Fallback to pg8000 pure-python driver if psycopg2 is not installed
if not IS_TESTING:
    try:
        import psycopg2
    except ImportError:
        try:
            import pg8000
            DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            logger.info("psycopg2 driver not found. Falling back to pg8000 pure-python driver.")
        except ImportError:
            logger.warning("Neither psycopg2 nor pg8000 drivers are installed. Connection might fail.")

engine = None
SessionLocal = None

if not IS_TESTING:
    logger.info(f"Connecting to database at {DB_HOST}:{DB_PORT}/{DB_NAME} as user {DB_USER}")
    # Create database engine with retry logic for resiliency
    MAX_RETRIES = 5
    RETRY_DELAY = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            engine = create_engine(
                DATABASE_URL,
                pool_size=10,
                max_overflow=20,
                pool_recycle=1800,
                pool_pre_ping=True
            )
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Successfully connected to the database!")
            break
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt == MAX_RETRIES:
                logger.error("Max database retries reached. Database might not be available yet.")
            else:
                time.sleep(RETRY_DELAY)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    logger.info("Testing context detected. Skipping PostgreSQL initialization.")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False)
Base = declarative_base()

# SQLAlchemy Database Model
class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    role = Column(String(50), default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Create tables if they don't exist (fallback - init.sql handles this in K8s but good for local/dev runs)
try:
    if engine:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas verified/created.")
except Exception as e:
    logger.error(f"Error creating schemas: {e}")

# Pydantic Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: Optional[str] = "user"

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None

class User(UserBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

# FastAPI App setup
app = FastAPI(
    title="Three-Tier App API",
    description="FastAPI Backend for Kubernetes deployment demonstration",
    version="1.0.0"
)

# CORS middleware configuration (crucial for local web app testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Metrics Definitions
REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total number of API requests received",
    ["method", "endpoint", "http_status"]
)
REQUEST_LATENCY = Histogram(
    "api_request_duration_seconds",
    "Latency of API requests in seconds",
    ["method", "endpoint"]
)

# Prometheus Middleware
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    response = Response("Internal Server Error", status_code=500)
    
    # Avoid tracking metrics endpoint request to prevent clutter
    path = request.url.path
    if path == "/metrics":
        return await call_next(request)
        
    try:
        response = await call_next(request)
    finally:
        latency = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=path,
            http_status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=path
        ).observe(latency)
        
    return response

# Dependency to get Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Health Endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying application liveness and database readiness.
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "database": "connected"
    }
    
    try:
        # Check database connection viability
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check failed due to database connection issue: {e}")
        health_status["status"] = "unhealthy"
        health_status["database"] = "disconnected"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
        
    return health_status

# Metrics Endpoint
@app.get("/metrics")
def get_metrics():
    """
    Expose Prometheus metrics for scraping.
    """
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

# --- CRUD ENDPOINTS FOR USERS ---

@app.get("/users", response_model=List[User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List users with pagination support.
    """
    users = db.query(UserModel).offset(skip).limit(limit).all()
    return users

@app.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user record.
    """
    # Check if email already exists
    existing_user = db.query(UserModel).filter(UserModel.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )
    
    db_user = UserModel(name=user.name, email=user.email, role=user.role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    """
    Update an existing user record.
    """
    db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Check email uniqueness if email is being updated
    if "email" in update_data and update_data["email"] != db_user.email:
        email_conflict = db.query(UserModel).filter(UserModel.email == update_data["email"]).first()
        if email_conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists"
            )
            
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    db.commit()
    db.refresh(db_user)
    return db_user

@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    Delete a user by ID.
    """
    db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    db.delete(db_user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
