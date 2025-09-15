from app.Http.Middleware.authenticate import authenticate
from fastapi import APIRouter, Depends
from app.models.user import User

router = APIRouter()

@router.get("/me")
def me(user: User = Depends(authenticate)):
    return {"id": user.id, "name": user.name, "email": user.email}
