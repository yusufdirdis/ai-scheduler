from sqlalchemy.orm import Session

from db.models import LaborRule, Role

DEFAULT_RESTAURANT_ROLES = ["Cook", "Server", "Host", "Bartender"]


def seed_default_roles(db: Session, business_id: int) -> None:
    """Restaurant is the only v1 business_type — future verticals get different (or empty) seeds."""
    for name in DEFAULT_RESTAURANT_ROLES:
        db.add(Role(business_id=business_id, name=name))
    db.add(LaborRule(business_id=business_id))
    db.commit()
