from app.db.models.user import User
from app.db.models.incentive_slab import IncentiveSlab
from app.db.models.payment import Payment
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import ProspectDocument
from app.db.models.course import Course
from app.db.models.specialization import Specialization
from app.db.models.notification import Notification
from app.db.models.activity_log import ActivityLog
from app.db.models.app_setting import AppSetting

__all__ = [
    "User",
    "IncentiveSlab",
    "Payment",
    "Prospect",
    "ProspectDocument",
    "Course",
    "Specialization",
    "Notification",
    "ActivityLog",
    "AppSetting",
]
