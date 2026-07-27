from app.db.models.payment_request import ExpenseCategory
EMPLOYEE_PAYMENT_TYPES = {
                ExpenseCategory.salary,
                ExpenseCategory.incentive,
            }