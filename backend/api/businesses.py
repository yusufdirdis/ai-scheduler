from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import AuthDep
from api.schemas import BusinessUpdate, LaborRuleUpdate
from db.models import Business, LaborRule
from db.session import get_db

router = APIRouter(prefix="/businesses", tags=["businesses"])


def _business_out(b: Business) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "business_type": b.business_type,
        "timezone": b.timezone,
        "location_name": b.location_name,
        "address": b.address,
        "week_start_day": b.week_start_day,
        "availability_request_day_of_week": b.availability_request_day_of_week,
        "availability_request_time": b.availability_request_time,
    }


def _labor_rule_out(r: LaborRule) -> dict:
    return {
        "weekly_overtime_threshold_hours": r.weekly_overtime_threshold_hours,
        "min_rest_hours_between_shifts": r.min_rest_hours_between_shifts,
    }


@router.get("/me")
def get_my_business(auth: AuthDep, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == auth.business_id).first()
    return _business_out(business)


@router.patch("/me")
def update_my_business(payload: BusinessUpdate, auth: AuthDep, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == auth.business_id).first()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(business, field, value)
    db.commit()
    db.refresh(business)
    return _business_out(business)


@router.get("/me/labor-rules")
def get_labor_rules(auth: AuthDep, db: Session = Depends(get_db)):
    rule = db.query(LaborRule).filter(LaborRule.business_id == auth.business_id).first()
    if not rule:
        raise HTTPException(404, "Labor rules not found for this business")
    return _labor_rule_out(rule)


@router.patch("/me/labor-rules")
def update_labor_rules(payload: LaborRuleUpdate, auth: AuthDep, db: Session = Depends(get_db)):
    rule = db.query(LaborRule).filter(LaborRule.business_id == auth.business_id).first()
    if not rule:
        raise HTTPException(404, "Labor rules not found for this business")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return _labor_rule_out(rule)
