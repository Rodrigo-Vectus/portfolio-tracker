"""Piezas reutilizables de los modelos."""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """created_at / updated_at gestionados por la base, no por Python.

    Se usa `now()` del servidor a proposito: si el reloj del contenedor de la
    aplicacion se corre, las marcas de tiempo siguen siendo coherentes entre
    si. En un sistema donde el orden de las operaciones define el resultado
    financiero, esto importa.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
