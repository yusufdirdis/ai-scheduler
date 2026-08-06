from datetime import date as date_type
from datetime import timedelta

from sqlalchemy.orm import Session

from db.models import ShiftSlot, ShiftTemplate, ShiftTemplateRequirement


def generate_slots_for_week(
    db: Session, business_id: int, schedule_id: int, week_start_date: date_type
) -> list[ShiftSlot]:
    """Expand active ShiftTemplates -> individual ShiftSlot rows (one per required seat)
    for the given week. template.day_of_week is an absolute weekday (0=Monday..6=Sunday);
    week_start_date's weekday always equals the business's week_start_day by construction,
    so the offset below places each template on its correct calendar date within the week."""
    templates = (
        db.query(ShiftTemplate)
        .filter(ShiftTemplate.business_id == business_id, ShiftTemplate.is_active.is_(True))
        .all()
    )

    created: list[ShiftSlot] = []
    for template in templates:
        offset = (template.day_of_week - week_start_date.weekday()) % 7
        slot_date = week_start_date + timedelta(days=offset)

        requirements = (
            db.query(ShiftTemplateRequirement)
            .filter(ShiftTemplateRequirement.shift_template_id == template.id)
            .all()
        )
        for req in requirements:
            for _ in range(req.count_required):
                slot = ShiftSlot(
                    schedule_id=schedule_id,
                    business_id=business_id,
                    role_id=req.role_id,
                    skill_id=req.skill_id,
                    min_skill_rating=req.min_skill_rating,
                    date=slot_date,
                    start_time=template.start_time,
                    end_time=template.end_time,
                    source_template_id=template.id,
                )
                db.add(slot)
                created.append(slot)

    db.flush()
    return created
