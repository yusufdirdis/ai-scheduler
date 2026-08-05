from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import AuthDep
from api.schemas import RoleCreate, ShiftTemplateCreate, ShiftTemplateUpdate, SkillCreate
from db.models import Role, ShiftTemplate, ShiftTemplateRequirement, Skill
from db.session import get_db

router = APIRouter(prefix="/coverage", tags=["coverage"])


def _scoped_role(db: Session, business_id: int, role_id: int) -> Role:
    role = db.query(Role).filter(Role.id == role_id, Role.business_id == business_id).first()
    if not role:
        raise HTTPException(404, "Role not found")
    return role


def _scoped_skill(db: Session, business_id: int, skill_id: int) -> Skill:
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.business_id == business_id).first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    return skill


def _scoped_template(db: Session, business_id: int, template_id: int) -> ShiftTemplate:
    template = (
        db.query(ShiftTemplate)
        .filter(ShiftTemplate.id == template_id, ShiftTemplate.business_id == business_id)
        .first()
    )
    if not template:
        raise HTTPException(404, "Shift template not found")
    return template


# ---- Roles ----------------------------------------------------------------

@router.get("/roles")
def list_roles(auth: AuthDep, db: Session = Depends(get_db)):
    roles = db.query(Role).filter(Role.business_id == auth.business_id).order_by(Role.name).all()
    return [{"id": r.id, "name": r.name} for r in roles]


@router.post("/roles")
def create_role(payload: RoleCreate, auth: AuthDep, db: Session = Depends(get_db)):
    role = Role(business_id=auth.business_id, name=payload.name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"id": role.id, "name": role.name}


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    role = _scoped_role(db, auth.business_id, role_id)
    db.delete(role)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This role is still assigned to employees or used in shift templates — remove those first"
        )
    return {"deleted": True}


# ---- Skills -----------------------------------------------------------------

@router.get("/skills")
def list_skills(auth: AuthDep, db: Session = Depends(get_db)):
    skills = db.query(Skill).filter(Skill.business_id == auth.business_id).order_by(Skill.name).all()
    return [{"id": s.id, "name": s.name} for s in skills]


@router.post("/skills")
def create_skill(payload: SkillCreate, auth: AuthDep, db: Session = Depends(get_db)):
    skill = Skill(business_id=auth.business_id, name=payload.name)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return {"id": skill.id, "name": skill.name}


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    skill = _scoped_skill(db, auth.business_id, skill_id)
    db.delete(skill)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This skill still has employee ratings or is used in shift templates — remove those first"
        )
    return {"deleted": True}


# ---- Shift templates ----------------------------------------------------------

def _template_out(t: ShiftTemplate, requirements: list[ShiftTemplateRequirement]) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "day_of_week": t.day_of_week,
        "start_time": t.start_time.isoformat(timespec="minutes"),
        "end_time": t.end_time.isoformat(timespec="minutes"),
        "is_active": t.is_active,
        "requirements": [
            {
                "id": r.id,
                "role_id": r.role_id,
                "count_required": r.count_required,
                "skill_id": r.skill_id,
                "min_skill_rating": r.min_skill_rating,
            }
            for r in requirements
        ],
    }


@router.get("/shift-templates")
def list_shift_templates(auth: AuthDep, db: Session = Depends(get_db)):
    templates = (
        db.query(ShiftTemplate)
        .filter(ShiftTemplate.business_id == auth.business_id)
        .order_by(ShiftTemplate.day_of_week, ShiftTemplate.start_time)
        .all()
    )
    template_ids = [t.id for t in templates]
    reqs_by_template: dict[int, list[ShiftTemplateRequirement]] = {tid: [] for tid in template_ids}
    if template_ids:
        for req in (
            db.query(ShiftTemplateRequirement)
            .filter(ShiftTemplateRequirement.shift_template_id.in_(template_ids))
            .all()
        ):
            reqs_by_template[req.shift_template_id].append(req)
    return [_template_out(t, reqs_by_template[t.id]) for t in templates]


@router.post("/shift-templates")
def create_shift_template(payload: ShiftTemplateCreate, auth: AuthDep, db: Session = Depends(get_db)):
    if payload.end_time <= payload.start_time:
        raise HTTPException(422, "end_time must be after start_time")

    role_ids = {req.role_id for req in payload.requirements}
    if role_ids:
        found = (
            db.query(Role.id)
            .filter(Role.business_id == auth.business_id, Role.id.in_(role_ids))
            .all()
        )
        missing = role_ids - {r.id for r in found}
        if missing:
            raise HTTPException(422, f"Unknown role_id(s): {sorted(missing)}")

    template = ShiftTemplate(
        business_id=auth.business_id,
        name=payload.name,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(template)
    db.flush()

    requirements = []
    for req in payload.requirements:
        row = ShiftTemplateRequirement(
            shift_template_id=template.id,
            role_id=req.role_id,
            count_required=req.count_required,
            skill_id=req.skill_id,
            min_skill_rating=req.min_skill_rating,
        )
        db.add(row)
        requirements.append(row)

    db.commit()
    db.refresh(template)
    for row in requirements:
        db.refresh(row)
    return _template_out(template, requirements)


@router.patch("/shift-templates/{template_id}")
def update_shift_template(
    template_id: int, payload: ShiftTemplateUpdate, auth: AuthDep, db: Session = Depends(get_db)
):
    template = _scoped_template(db, auth.business_id, template_id)
    updates = payload.model_dump(exclude_unset=True)
    new_start = updates.get("start_time", template.start_time)
    new_end = updates.get("end_time", template.end_time)
    if new_end <= new_start:
        raise HTTPException(422, "end_time must be after start_time")
    for field, value in updates.items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    requirements = (
        db.query(ShiftTemplateRequirement)
        .filter(ShiftTemplateRequirement.shift_template_id == template.id)
        .all()
    )
    return _template_out(template, requirements)


@router.delete("/shift-templates/{template_id}")
def delete_shift_template(template_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    template = _scoped_template(db, auth.business_id, template_id)
    db.query(ShiftTemplateRequirement).filter(
        ShiftTemplateRequirement.shift_template_id == template.id
    ).delete(synchronize_session=False)
    db.delete(template)
    db.commit()
    return {"deleted": True}
