import os
from fastapi import APIRouter, HTTPException, Depends
from ..schemas.auth import LoginRequest
from ..auth import create_access_token, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(req: LoginRequest):
    admin_password = os.environ.get("ADMIN_PASSWORD", "leadengine123")
    if req.password == admin_password:
        token = create_access_token({"sub": "admin"})
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid password")
