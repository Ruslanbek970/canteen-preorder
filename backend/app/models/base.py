import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "%(table_name)s_%(column_0_N_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)


def int_pk():
    return mapped_column(sa.Integer, sa.Identity(always=True), primary_key=True)


def bigint_pk():
    return mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)


def smallint_pk():
    return mapped_column(sa.SmallInteger, sa.Identity(always=True), primary_key=True)


def created_at_col():
    return mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


TimestampTZ = sa.DateTime(timezone=True)
