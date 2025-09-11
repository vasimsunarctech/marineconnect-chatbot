from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from app.db.database import get_db , engine
from pydantic import BaseModel
from typing import List
import json

Base = declarative_base()
class Vendor(Base):
    __tablename__ = "vendor"
    id = Column(Integer,primary_key = True, index=True)
    name = Column(String(50),nullable=True)
    company = Column(String(50),nullable=True)
    services = Column(JSON)
    discription = Column(String(150))
    contact=Column(JSON)
    email=Column(JSON)
    addresses = Column(JSON)
    cities = Column(JSON)
    countries = Column(JSON)


class CreateVendor(BaseModel):
    name : str
    company : str
    services : List[str]
    discription : str
    contact : List[str]
    email : List[str]
    addresses : List[str]
    cities : List[str]
    countries : List[str]

def create_vendor(vendor : CreateVendor):
    db = next(get_db())
    vendor_data = vendor.dict()
    db_vendor = Vendor(**vendor_data)
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)

    return json.dumps({'status':200,'message':"Vendor Inserted"})


def create_vendor_table():
    try:
        Base.metadata.create_all(bind=engine)
        return json.dumps({"message":"Vendor Table is created"})
    except Exception as e:
        return json.dumps({"message": e})
