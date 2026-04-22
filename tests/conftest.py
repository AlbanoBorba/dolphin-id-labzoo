import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.database import get_engine, get_session

# Banco de dados em memória para testes isolados
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session
    
    def get_engine_override():
        return session.get_bind()

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_engine] = get_engine_override
    
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
