from app.db.models.user import User
from app.db.models.course import Course
from app.db.models.specialization import Specialization
from app.db.models.prospect import Prospect
from app.db.models.payment import Payment
from app.db.models.prospect_document import ProspectDocument

__all__ = [
    "User",
    "Course",
    "Specialization",
    "Prospect",
    "Payment",
    "ProspectDocument",
]