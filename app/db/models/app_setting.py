from sqlalchemy import Column, String, Text

from app.db.base import Base
from app.db.mixins import TimestampMixin


class AppSetting(TimestampMixin, Base):
    """Key/value app configuration (e.g. default monthly sales target)."""

    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)


# Well-known keys
DEFAULT_MONTHLY_SALES_TARGET = "default_monthly_sales_target"
