from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column

"""------------------------------------------------------------------------------------------------
DEPARTURE from atlas: atlas's base is `pass`, and no atlas model records when a
row appeared or last changed.

Declared here rather than on each model so that a model added later cannot
forget them -- which is the failure this shape prevents, and the reason it is
worth being on the base at all.

`server_default` rather than a Python default, because a Python default does not
apply to rows written by anything that is not this application: a migration, a
bulk load, a fixture inserted by hand. `onupdate` covers the ORM path for
`updated_at`; a bulk `UPDATE` issued as a statement will not fire it, which is a
limit worth knowing rather than discovering.
"""
class BaseDatabaseModel(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now())
