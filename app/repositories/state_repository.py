from sqlalchemy.orm import Session

from app.db.models.state import State


class StateRepository:

    @staticmethod
    def get_all(db: Session, *, active_only: bool = False):
        query = db.query(State)
        if active_only:
            query = query.filter(State.is_active.is_(True))
        return query.order_by(State.name).all()

    @staticmethod
    def get_by_id(db: Session, state_id: int):
        return db.query(State).filter(State.id == state_id).first()

    @staticmethod
    def get_by_name(db: Session, name: str):
        return db.query(State).filter(State.name == name).first()

    @staticmethod
    def get_by_code(db: Session, code: str):
        return (
            db.query(State)
            .filter(State.state_code == code)
            .first()
        )

    @staticmethod
    def create(db: Session, state: State):
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    @staticmethod
    def update(db: Session, state: State):
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    @staticmethod
    def delete(db: Session, state: State):
        db.delete(state)
        db.commit()
