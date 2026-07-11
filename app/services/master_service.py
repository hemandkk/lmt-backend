from sqlalchemy.orm import Session

from app.db.models.course import Course
from app.db.models.incentive_slab import (
    IncentiveSlab,
)
from app.repositories.course_repository import (
    CourseRepository,
)
from app.repositories.incentive_repository import (
    IncentiveRepository,
)
from app.schemas.master import (
    CourseCreate,
    UpdateIncentiveSlabsRequest,
)


class MasterService:

    # -----------------------------
    # Courses
    # -----------------------------

    @staticmethod
    def get_courses(
        db: Session,
    ):
        return CourseRepository.get_all(db)

    @staticmethod
    def create_course(
        db: Session,
        payload: CourseCreate,
    ):

        existing = CourseRepository.get_by_name(
            db,
            payload.name,
        )

        if existing:
            raise ValueError(
                "Course already exists."
            )

        course = Course(
            name=payload.name,
            active=True,
        )

        return CourseRepository.create(
            db,
            course,
        )

    @staticmethod
    def delete_course(
        db: Session,
        course_id: int,
    ):

        course = CourseRepository.get_by_id(
            db,
            course_id,
        )

        if not course:
            raise ValueError(
                "Course not found."
            )

        CourseRepository.delete(
            db,
            course,
        )

    # -----------------------------
    # Incentive
    # -----------------------------

    @staticmethod
    def get_incentive_slabs(
        db: Session,
    ):

        return IncentiveRepository.get_all(
            db,
        )

    @staticmethod
    def update_incentive_slabs(
        db: Session,
        payload: UpdateIncentiveSlabsRequest,
    ):

        IncentiveRepository.delete_all(
            db,
        )

        slabs = []

        for item in payload.slabs:

            slab = IncentiveSlab(
                min_amount=item.min_amount,
                max_amount=item.max_amount,
                rate_percent=item.rate_percent,
            )

            slabs.append(
                IncentiveRepository.create(
                    db,
                    slab,
                )
            )

        return slabs