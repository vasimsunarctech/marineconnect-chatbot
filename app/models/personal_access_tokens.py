from sqlalchemy import Column, BigInteger, String, Text, DateTime, TIMESTAMP
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class PersonalAccessToken(Base):
    __tablename__ = "personal_access_tokens"
    id = Column(BigInteger, primary_key=True)
    token = Column(String(64), index=True)
    name = Column(String(255))
    tokenable_type = Column(String(255))
    tokenable_id = Column(BigInteger)
    abilities = Column(Text)
    last_used_at = Column(DateTime)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(),
                        onupdate=func.now(), nullable=True)
