from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import AuthDep
from db.models import Business
from db.session import get_db

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("/me")
def get_my_business(auth: AuthDep, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == auth.business_id).first()
    return {
        "id": business.id,
        "name": business.name,
        "business_type": business.business_type,
        "timezone": business.timezone,
    }
