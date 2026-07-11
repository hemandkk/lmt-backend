import re

from sqlalchemy import desc, func
from sqlalchemy.orm import Session


def generate_id(
    db: Session,
    model,
    field: str,
    prefix: str,
    digits: int = 5,
) -> str:
    """
    Generates IDs like:
    EMP00001, PRO00001, PAY00001, DOC00001, CRS00001
    """
    column = getattr(model, field)
    max_value = db.query(func.max(column)).scalar()

    if not max_value:
        next_number = 1
    else:
        try:
            # Strip any non-digit prefix (PRO / PSP / etc.)
            match = re.search(r"(\d+)$", str(max_value))
            next_number = int(match.group(1)) + 1 if match else 1
        except Exception:
            next_number = 1

    return f"{prefix}{next_number:0{digits}}"


def generate_next_code(
    db: Session,
    model,
    field: str,
    prefix: str,
    digits: int = 4,
) -> str:
    """
    Preview the next code without loading the full ORM row
    (avoids 500s when mapped columns are missing from DB).
    """
    column = getattr(model, field)

    last_code = (
        db.query(column)
        .filter(column.isnot(None))
        .order_by(desc(model.id))
        .limit(1)
        .scalar()
    )

    if not last_code:
        return f"{prefix}{1:0{digits}}"

    match = re.search(r"(\d+)$", str(last_code))
    next_number = int(match.group(1)) + 1 if match else 1
    return f"{prefix}{next_number:0{digits}}"
