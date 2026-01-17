"""
Example 01: Basic Pydantic Integration

This example demonstrates how to use Pydantic models as SQLAlchemy columns
with automatic mutation tracking.
"""

from pydantic import BaseModel, Field
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_engine


# 1. Define your Pydantic Model (Inherit from MutableMixin)
class UserSettings(MutableMixin, BaseModel):
    theme: str = "light"
    notifications: bool = True
    tags: list[str] = Field(default_factory=list)


# 2. Define your SQLAlchemy Entity
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)

    # ModelType automatically handles serialization
    settings: Mapped[UserSettings] = mapped_column(ModelType(UserSettings))


def run_example():
    # Use our helper to get optimized orjson configuration
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Create a user
        user = User(settings=UserSettings(theme="dark", tags=["initial"]))
        session.add(user)
        session.commit()
        print(f"Created user with tags: {user.settings.tags}")

        # --- MUTATION TRACKING IN ACTION ---

        # Deep mutation: append to a nested list
        user.settings.tags.append("pydantic")

        # Simple attribute update
        user.settings.theme = "high-contrast"

        # We don't need flag_modified() or re-assignment!
        session.commit()

        # Verify changes
        session.refresh(user)
        print(f"Updated theme: {user.settings.theme}")
        print(f"Updated tags: {user.settings.tags}")


if __name__ == "__main__":
    run_example()
