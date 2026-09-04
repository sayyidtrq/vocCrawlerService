from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.company_service import CompanyService


def test_create_and_list_company():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    service = CompanyService(sessionmaker(bind=engine, expire_on_commit=False))

    company = service.create("Acme")

    assert company.id is not None
    assert company.id in {item.id for item in service.list_companies()}
