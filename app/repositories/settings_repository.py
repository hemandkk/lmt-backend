from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models.app_setting import (
    DEFAULT_MONTHLY_SALES_TARGET,
    AppSetting,
)

FALLBACK_DEFAULT_TARGET = Decimal("100000")


class SettingsRepository:

    @staticmethod
    def get(db: Session, key: str) -> AppSetting | None:
        return db.query(AppSetting).filter(AppSetting.key == key).first()

    @staticmethod
    def get_value(db: Session, key: str, default: str | None = None) -> str | None:
        row = SettingsRepository.get(db, key)
        if row is None:
            return default
        return row.value

    @staticmethod
    def set_value(db: Session, key: str, value: str) -> AppSetting:
        row = SettingsRepository.get(db, key)
        if row is None:
            row = AppSetting(key=key, value=value)
            db.add(row)
        else:
            row.value = value
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def get_default_monthly_sales_target(db: Session) -> Decimal:
        raw = SettingsRepository.get_value(
            db,
            DEFAULT_MONTHLY_SALES_TARGET,
            default=str(FALLBACK_DEFAULT_TARGET),
        )
        try:
            return Decimal(str(raw))
        except Exception:
            return FALLBACK_DEFAULT_TARGET

    @staticmethod
    def set_default_monthly_sales_target(
        db: Session, amount: Decimal
    ) -> Decimal:
        SettingsRepository.set_value(
            db,
            DEFAULT_MONTHLY_SALES_TARGET,
            str(amount),
        )
        return Decimal(str(amount))
