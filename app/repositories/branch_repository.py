from sqlalchemy.orm import Session, joinedload

from app.db.models.branch import Branch


class BranchRepository:

    @staticmethod
    def get_all(
        db: Session,
        *,
        active_only: bool = False,
        state_id: int | None = None,
    ):
        query = db.query(Branch).options(joinedload(Branch.state))
        if active_only:
            query = query.filter(Branch.is_active.is_(True))
        if state_id is not None:
            query = query.filter(Branch.state_id == state_id)
        return query.order_by(Branch.name).all()

    @staticmethod
    def get_by_id(db: Session, branch_id: int):
        return (
            db.query(Branch)
            .options(joinedload(Branch.state))
            .filter(Branch.id == branch_id)
            .first()
        )

    @staticmethod
    def get_by_name(db: Session, name: str, state_id: int | None = None):
        query = db.query(Branch).filter(Branch.name == name)
        if state_id is not None:
            query = query.filter(Branch.state_id == state_id)
        return query.first()

    @staticmethod
    def get_by_code(db: Session, code: str):
        return (
            db.query(Branch)
            .filter(Branch.branch_code == code)
            .first()
        )

    @staticmethod
    def create(db: Session, branch: Branch):
        db.add(branch)
        db.commit()
        db.refresh(branch)
        return BranchRepository.get_by_id(db, branch.id)

    @staticmethod
    def update(db: Session, branch: Branch):
        db.add(branch)
        db.commit()
        db.refresh(branch)
        return BranchRepository.get_by_id(db, branch.id)

    @staticmethod
    def delete(db: Session, branch: Branch):
        db.delete(branch)
        db.commit()
