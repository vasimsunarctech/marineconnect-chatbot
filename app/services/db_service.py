import json 
from typing import Dict, Any 

from sqlalchemy import select , text 
from sqlalchemy import Table, MetaData 
from app.db.database import engine , get_db 

metadata = MetaData()
metadata.reflect(bind=engine)

Vendor = metadata.tables["vendor"]

ALLOWED_FILTERS = {"services","cities","countries","company","name"}
FORBIDDEN_KEYWORDS = {"insert", "update", "delete", "drop",
    "truncate", "alter", "union", "exec", "declare",
    "sleep", "benchmark", "information_schema"}

def validate_filters(filters: Dict[str, Any])->Dict[str,Any]:
    valid = {}
    rejected = []
    for k,v in filters.items():
        if k in ALLOWED_FILTERS and v:
            valid[k]=v
        else:
            rejected.append(k)
    return valid, rejected

def contains_forbidden(values: Any)->bool:
    if isinstance(values,str):
        check_values = [values]
    elif isinstance(values,list):
        check_values = [str(v) for v in values]
    else:
        return False
    
    for val in check_values:
        lower_val = val.lower()
        for bad in FORBIDDEN_KEYWORDS:
            if bad in lower_val:
                return True
    return False


def fetch_vendor_data(filter : Dict[str,Any])->Dict[str,Any]:
    
    
    valid_filters , rejected = validate_filters(filter)

    if rejected:
        return {
            "error":"invaild_filter",
            "invaild":rejected,
            "allowed":list(ALLOWED_FILTERS)
        }
    
    if not valid_filters:
        return {
            "error":"missing_filters",
            "missing":list(ALLOWED_FILTERS)
        }
    for key,val in valid_filters.items():
        if contains_forbidden(val):
            return {"error": "forbidden keyword", "field":key, "value":val}
    
    db = get_db()
    try:
        query = select(
            Vendor.c.name,
            Vendor.c.company,
            Vendor.c.services,
            Vendor.c.cities,
            Vendor.c.countries,
            Vendor.c.contact,
            Vendor.c.email
        ).limit(5)

        for key , value in valid_filters.items():
            col = Vendor.c.get(key)

            if isinstance(value,list):
                for v in value:
                    query = query.where(text(f"JSON_CONTAINS({key},'\"{v}\"')"))
            else:
                query = query.where(col.like(f"%{value}%"))

        rows = db.execute(query).fetchall()

        results = []
        for row in rows:
            results.append({
                "name":row.name,
                "company":row.company,
                "services":row.services,
                "cities": row.cities,
                "countries": row.countries,
                "contact":row.contact,
                "email":row.email,
            })

        if not results:
            return {"results":[], "note":"No vendors found."}

        return {"results":results}
    except Exception as e :
        return {"error":f"came from fetch {e}"}

