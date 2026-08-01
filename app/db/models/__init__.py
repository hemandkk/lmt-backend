from app.db.models.user import User
from app.db.models.incentive_slab import IncentiveSlab
from app.db.models.payment import Payment
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import ProspectDocument
from app.db.models.course import Course
from app.db.models.specialization import Specialization
from app.db.models.state import State
from app.db.models.branch import Branch
from app.db.models.notification import Notification
from app.db.models.activity_log import ActivityLog
from app.db.models.app_setting import AppSetting
from app.db.models.expense import Expense
from app.db.models.payment_request import PaymentRequest
from app.db.models.designation import Designation
from app.db.models.department import Department

__all__ = [
    "User",
    "IncentiveSlab",
    "Payment",
    "Prospect",
    "ProspectDocument",
    "Course",
    "Specialization",
    "State",
    "Branch",
    "Notification",
    "ActivityLog",
    "AppSetting",
    "Expense",
    "PaymentRequest",
    "Designation",
    "Department",
]
