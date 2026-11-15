from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from .models import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: Session, model_type: type[ModelT]) -> None:
        self.session = session
        self.model_type = model_type

    def get(self, identifier: UUID) -> ModelT | None:
        return self.session.get(self.model_type, identifier)

    def add(self, model: ModelT) -> ModelT:
        self.session.add(model)
        return model
