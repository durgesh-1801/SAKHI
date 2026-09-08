import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.user_service import user_service
from app.schemas.user import UserCreate
from app.core.security import create_access_token

# Test In-Memory SQLite Engine
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user_a(db_session):
    user_in = UserCreate(
        name="Aarya Sharma",
        email="aarya@sakhi.safe",
        phone="+919876543210",
        password="SecurePassword123!"
    )
    return user_service.create(db_session, user_in)


@pytest.fixture
def user_b(db_session):
    user_in = UserCreate(
        name="Bhavna Patel",
        email="bhavna@sakhi.safe",
        phone="+919876543211",
        password="AnotherSecurePassword456!"
    )
    return user_service.create(db_session, user_in)


@pytest.fixture
def user_a_headers(user_a):
    token = create_access_token(subject=user_a.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_b_headers(user_b):
    token = create_access_token(subject=user_b.id)
    return {"Authorization": f"Bearer {token}"}
