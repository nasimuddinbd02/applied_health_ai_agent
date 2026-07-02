"""Auth data access: users (login identities) keyed by email."""

from sqlmodel import select

from app.dbacces.repository import BaseRepository
from app.models.entities import User


class UserRepository(BaseRepository):
    def create_user(self, **fields) -> User:
        with self._session() as s:
            user = User(**fields)
            s.add(user)
            s.commit()
            s.refresh(user)
            return user

    def get_by_email(self, email: str) -> User | None:
        with self._session() as s:
            return s.exec(select(User).where(User.email == email)).first()

    def get_by_id(self, user_id: int) -> User | None:
        with self._session() as s:
            return s.get(User, user_id)

    def list_users(self) -> list[User]:
        with self._session() as s:
            return list(s.exec(select(User).order_by(User.id)).all())
