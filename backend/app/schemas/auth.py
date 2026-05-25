from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(description="행번(직원) 또는 'admin'")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_initial_password: bool


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
