from sqlalchemy.orm import Session
from sqlalchemy import func


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