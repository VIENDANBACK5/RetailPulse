import logging

from fastapi_sqlalchemy import db
from google.auth.exceptions import GoogleAuthError
from keycloak.exceptions import KeycloakError
from pydantic import ValidationError

from app.models import User
from app.services.srv_base import BaseService
from app.core.config import settings
from app.core.security import decode_jwt, get_password_hash
from app.schemas.sche_auth import TokenRequest
from app.schemas.sche_user import UserCreateRequest
from app.utils.exception_handler import CustomException, ExceptionType
from app.core.config import keycloak_openid
from google.oauth2 import id_token
from google.auth.transport import requests

logger = logging.getLogger(__name__)


class UserService(BaseService[User]):

    def __init__(self):
        super().__init__(User)

    @staticmethod
    def get_me(access_token: str) -> User:
        try:
            user_info = keycloak_openid.userinfo(access_token)
        except KeycloakError as exc:
            logger.info("Keycloak auth failed, falling back to Google: %s", exc)
            user_info = None
        if user_info:
            return User(
                username=user_info["preferred_username"],
                email=user_info.get("email"),
                full_name=user_info.get("name"),
            )

        try:
            user_info = id_token.verify_oauth2_token(
                access_token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except (GoogleAuthError, ValueError) as exc:
            logger.info("Google auth failed, falling back to JWT: %s", exc)
            user_info = None
        if user_info:
            return User(
                username=user_info["sub"],
                email=user_info.get("email"),
                full_name=user_info.get("name"),
            )

        payload = decode_jwt(access_token)
        if not payload:
            raise CustomException(exception=ExceptionType.UNAUTHORIZED)
        try:
            token_data = TokenRequest(**payload)
        except ValidationError as exc:
            logger.warning("JWT payload invalid: %s", exc)
            raise CustomException(exception=ExceptionType.UNAUTHORIZED)
        user = db.session.query(User).get(token_data.sub)
        if not user:
            raise CustomException(exception=ExceptionType.UNAUTHORIZED)
        return user

    def create(self, data: UserCreateRequest) -> User:
        try:
            origin_password = data.password
            hashed_password = get_password_hash(origin_password)
            processed_data = data.model_dump(exclude_unset=True)
            del processed_data["password"]
            processed_data["hashed_password"] = hashed_password
            return super().create(processed_data)
        except Exception as e:
            raise CustomException(exception=ExceptionType.INTERNAL_SERVER_ERROR)
