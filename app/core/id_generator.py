import re

from sqlalchemy.orm import Session


def _next_sequential_code(
    db: Session,
    model,
    field: str,
    prefix: str,
    digits: int,
) -> str:
    """
    Next code like PREFIX00001.

    Uses the max *numeric* suffix among rows matching PREFIX+digits only.
    Avoids func.max() on mixed codes (e.g. DOC00002 vs DOC5F3DB), which
    is lexicographic and can collide with existing sequential IDs.
    """
    column = getattr(model, field)
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$", re.IGNORECASE)
    max_number = 0

    for (code,) in db.query(column).filter(column.isnot(None)).all():
        match = pattern.match(str(code))
        if match:
            max_number = max(max_number, int(match.group(1)))

    return f"{prefix}{max_number + 1:0{digits}}"


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
    return _next_sequential_code(db, model, field, prefix, digits)


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
    return _next_sequential_code(db, model, field, prefix, digits)
