from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    username: str = Field(default="", alias="username")
    password: str

    @model_validator(mode="before")
    @classmethod
    def accept_email_or_employee_id(cls, data):
        """Frontend may send email / employeeId instead of username."""
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if not payload.get("username"):
            payload["username"] = (
                payload.get("email")
                or payload.get("employeeId")
                or payload.get("employee_id")
                or ""
            )
        return payload


class RefreshRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken")
    model_config = ConfigDict(populate_by_name=True)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str | None = None
    employee_id: str | None = None
    role: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse
