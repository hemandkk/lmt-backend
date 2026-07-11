from sqlalchemy.orm import Session
from app.db.models.prospect import Prospect
from app.db.models.user import User
import re
from sqlalchemy import desc,func

def generate_id(
    db: Session,
    model,
    field: str,
    prefix: str,
    digits: int = 5,
) -> str:
    """
    Generates IDs like:

    EMP00001
    PRO00001
    PAY00001
    DOC00001
    CRS00001
    """

    max_value = db.query(
        func.max(getattr(model, field))
    ).scalar()

    if not max_value:
        next_number = 1
    else:
        try:
            next_number = int(max_value.replace(prefix, "")) + 1
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
    last_record = (
        db.query(model)
        .filter(getattr(model, field).isnot(None))
        .order_by(desc(model.id))
        .first()
    )

    if not last_record:
        return f"{prefix}{1:0{digits}}"

    last_code = getattr(last_record, field)

    match = re.search(r"(\d+)$", last_code or "")

    next_number = int(match.group(1)) + 1 if match else 1

    return f"{prefix}{next_number:0{digits}}"
