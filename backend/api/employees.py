from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import AuthDep
from api.schemas import (
    AttendanceRecordCreate,
    EmployeeCreate,
    EmployeeRoleIn,
    EmployeeUpdate,
    ManagerNoteCreate,
    SkillRatingIn,
)
from db.models import (
    AttendanceRecord,
    Employee,
    EmployeeRole,
    EmployeeSkillRating,
    ManagerNote,
    Role,
    Skill,
)
from db.session import get_db
from services.phone import normalize_phone_number

router = APIRouter(prefix="/employees", tags=["employees"])


def _scoped_employee(db: Session, business_id: int, employee_id: int) -> Employee:
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.business_id == business_id)
        .first()
    )
    if not employee:
        raise HTTPException(404, "Employee not found")
    return employee


def _employee_summary(db: Session, employee: Employee) -> dict:
    role_names = (
        db.query(Role.name)
        .join(EmployeeRole, EmployeeRole.role_id == Role.id)
        .filter(EmployeeRole.employee_id == employee.id)
        .all()
    )
    return {
        "id": employee.id,
        "full_name": employee.full_name,
        "phone_number": employee.phone_number,
        "is_active": employee.is_active,
        "reliability_score": employee.reliability_score,
        "roles": [r.name for r in role_names],
    }


def _employee_detail(db: Session, employee: Employee) -> dict:
    roles = (
        db.query(EmployeeRole, Role.name)
        .join(Role, Role.id == EmployeeRole.role_id)
        .filter(EmployeeRole.employee_id == employee.id)
        .all()
    )
    skill_ratings = (
        db.query(EmployeeSkillRating, Skill.name)
        .join(Skill, Skill.id == EmployeeSkillRating.skill_id)
        .filter(EmployeeSkillRating.employee_id == employee.id)
        .all()
    )
    notes = (
        db.query(ManagerNote)
        .filter(ManagerNote.employee_id == employee.id, ManagerNote.is_active.is_(True))
        .order_by(ManagerNote.created_at.desc())
        .all()
    )
    attendance = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.employee_id == employee.id)
        .order_by(AttendanceRecord.recorded_at.desc())
        .limit(50)
        .all()
    )

    return {
        "id": employee.id,
        "full_name": employee.full_name,
        "phone_number": employee.phone_number,
        "is_active": employee.is_active,
        "reliability_score": employee.reliability_score,
        "roles": [
            {"role_id": er.role_id, "role_name": name, "is_primary": er.is_primary}
            for er, name in roles
        ],
        "skill_ratings": [
            {
                "skill_id": rating.skill_id,
                "skill_name": name,
                "rating": rating.rating,
                "notes": rating.notes,
            }
            for rating, name in skill_ratings
        ],
        "notes": [
            {
                "id": n.id,
                "note_text": n.note_text,
                "author_user_id": n.author_user_id,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notes
        ],
        "attendance": [
            {
                "id": a.id,
                "status": a.status,
                "minutes_late": a.minutes_late,
                "notes": a.notes,
                "recorded_at": a.recorded_at.isoformat() if a.recorded_at else None,
            }
            for a in attendance
        ],
    }


# ---- Employee CRUD ----------------------------------------------------------

@router.get("")
def list_employees(auth: AuthDep, db: Session = Depends(get_db)):
    employees = (
        db.query(Employee)
        .filter(Employee.business_id == auth.business_id)
        .order_by(Employee.full_name)
        .all()
    )
    return [_employee_summary(db, e) for e in employees]


@router.post("")
def create_employee(payload: EmployeeCreate, auth: AuthDep, db: Session = Depends(get_db)):
    try:
        phone_number = normalize_phone_number(payload.phone_number)
    except ValueError as e:
        raise HTTPException(422, str(e))

    employee = Employee(
        business_id=auth.business_id,
        full_name=payload.full_name,
        phone_number=phone_number,
    )
    db.add(employee)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An employee with this phone number already exists")
    db.refresh(employee)
    return _employee_detail(db, employee)


@router.get("/{employee_id}")
def get_employee(employee_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    return _employee_detail(db, employee)


@router.patch("/{employee_id}")
def update_employee(
    employee_id: int, payload: EmployeeUpdate, auth: AuthDep, db: Session = Depends(get_db)
):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    updates = payload.model_dump(exclude_unset=True)
    if "phone_number" in updates:
        try:
            updates["phone_number"] = normalize_phone_number(updates["phone_number"])
        except ValueError as e:
            raise HTTPException(422, str(e))
    for field, value in updates.items():
        setattr(employee, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An employee with this phone number already exists")
    db.refresh(employee)
    return _employee_detail(db, employee)


@router.delete("/{employee_id}")
def deactivate_employee(employee_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    """Soft delete: employees stay referenced by historical attendance/notes/assignments,
    so we deactivate rather than remove the row."""
    employee = _scoped_employee(db, auth.business_id, employee_id)
    employee.is_active = False
    db.commit()
    return {"deactivated": True}


# ---- Roles ----------------------------------------------------------------

@router.post("/{employee_id}/roles")
def assign_role(
    employee_id: int, payload: EmployeeRoleIn, auth: AuthDep, db: Session = Depends(get_db)
):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    role = db.query(Role).filter(Role.id == payload.role_id, Role.business_id == auth.business_id).first()
    if not role:
        raise HTTPException(422, "Unknown role_id")

    existing = (
        db.query(EmployeeRole)
        .filter(EmployeeRole.employee_id == employee.id, EmployeeRole.role_id == role.id)
        .first()
    )
    if existing:
        existing.is_primary = payload.is_primary
    else:
        db.add(EmployeeRole(employee_id=employee.id, role_id=role.id, is_primary=payload.is_primary))
    db.commit()
    return _employee_detail(db, employee)


@router.delete("/{employee_id}/roles/{role_id}")
def unassign_role(employee_id: int, role_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    db.query(EmployeeRole).filter(
        EmployeeRole.employee_id == employee.id, EmployeeRole.role_id == role_id
    ).delete(synchronize_session=False)
    db.commit()
    return _employee_detail(db, employee)


# ---- Skill ratings ------------------------------------------------------------

@router.put("/{employee_id}/skills/{skill_id}")
def upsert_skill_rating(
    employee_id: int, skill_id: int, payload: SkillRatingIn, auth: AuthDep, db: Session = Depends(get_db)
):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.business_id == auth.business_id).first()
    if not skill:
        raise HTTPException(422, "Unknown skill_id")

    rating = (
        db.query(EmployeeSkillRating)
        .filter(EmployeeSkillRating.employee_id == employee.id, EmployeeSkillRating.skill_id == skill.id)
        .first()
    )
    if rating:
        rating.rating = payload.rating
        rating.notes = payload.notes
        rating.rated_by_user_id = auth.user_id
    else:
        db.add(
            EmployeeSkillRating(
                employee_id=employee.id,
                skill_id=skill.id,
                rating=payload.rating,
                notes=payload.notes,
                rated_by_user_id=auth.user_id,
            )
        )
    db.commit()
    return _employee_detail(db, employee)


@router.delete("/{employee_id}/skills/{skill_id}")
def remove_skill_rating(employee_id: int, skill_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    db.query(EmployeeSkillRating).filter(
        EmployeeSkillRating.employee_id == employee.id, EmployeeSkillRating.skill_id == skill_id
    ).delete(synchronize_session=False)
    db.commit()
    return _employee_detail(db, employee)


# ---- Manager notes -------------------------------------------------------------

@router.post("/{employee_id}/notes")
def add_note(
    employee_id: int, payload: ManagerNoteCreate, auth: AuthDep, db: Session = Depends(get_db)
):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    db.add(
        ManagerNote(
            business_id=auth.business_id,
            employee_id=employee.id,
            author_user_id=auth.user_id,
            note_text=payload.note_text,
        )
    )
    db.commit()
    return _employee_detail(db, employee)


@router.delete("/{employee_id}/notes/{note_id}")
def remove_note(employee_id: int, note_id: int, auth: AuthDep, db: Session = Depends(get_db)):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    note = (
        db.query(ManagerNote)
        .filter(ManagerNote.id == note_id, ManagerNote.employee_id == employee.id)
        .first()
    )
    if not note:
        raise HTTPException(404, "Note not found")
    note.is_active = False
    db.commit()
    return _employee_detail(db, employee)


# ---- Attendance ----------------------------------------------------------------

@router.post("/{employee_id}/attendance")
def add_attendance_record(
    employee_id: int, payload: AttendanceRecordCreate, auth: AuthDep, db: Session = Depends(get_db)
):
    employee = _scoped_employee(db, auth.business_id, employee_id)
    db.add(
        AttendanceRecord(
            business_id=auth.business_id,
            employee_id=employee.id,
            status=payload.status,
            minutes_late=payload.minutes_late,
            notes=payload.notes,
            recorded_by_user_id=auth.user_id,
        )
    )
    db.commit()
    return _employee_detail(db, employee)
