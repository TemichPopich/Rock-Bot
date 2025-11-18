from typing import Annotated

from sqlalchemy import ForeignKey, String, Text, CheckConstraint, BigInteger
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
)
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

from config import settings
from utils import MusicEducation


DATABASE_URL = settings.get_db_url()


engine = create_async_engine(url=DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


int_pk = Annotated[int, mapped_column(BigInteger, primary_key=True)]
str_uniq = Annotated[str, mapped_column(unique=True, nullable=False)]
str_nullable = Annotated[str, mapped_column(nullable=True)]


class Base(DeclarativeBase):
    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return f"{cls.__name__.lower()}s"


class ProfileLike(Base):
    liker_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    liked_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )


class Profile(Base):
    id: Mapped[int_pk]
    username: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    faculty: Mapped[str] = mapped_column(String(100))
    course: Mapped[int]
    education: Mapped[MusicEducation] = mapped_column(default=MusicEducation.SELF)
    desc: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(200))
    likes: Mapped[list["Profile"]] = relationship(
        "Profile",
        secondary="profilelikes",
        primaryjoin="Profile.id == ProfileLike.liker_id",
        secondaryjoin="Profile.id == ProfileLike.liked_id",
        back_populates="liked_by",
    )
    liked_by: Mapped[list["Profile"]] = relationship(
        "Profile",
        secondary="profilelikes",
        primaryjoin="Profile.id == ProfileLike.liked_id",
        secondaryjoin="Profile.id == ProfileLike.liker_id",
        back_populates="likes",
    )

    def __repr__(self) -> str:
        return (
            f"{self.name}\nфакультет - '{self.faculty}', "
            f"курс - {self.course}, музыкальное образование - {self.education.value}"
            f"\n{self.desc}\n<ссылка:{self.link}>"
        )
