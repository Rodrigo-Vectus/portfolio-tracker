"""Preferencias de visualizacion por usuario.

El sistema ya tenia el concepto de preferencia, pero solo a nivel de
instalacion: `DEFAULT_DISPLAY_CURRENCY` y companeros viven en el `.env` y valen
para todos. Esta tabla es la capa de arriba: lo que **este** usuario eligio.

**Una columna nula no es un valor.** Significa "no elegi nada", y entonces vale
el default del `.env`. Guardar el default copiado en la fila lo congelaria: si
manana cambia la configuracion de la instalacion, el usuario que nunca toco
nada seguiria con el valor viejo sin haberlo pedido.

Se crea con una sola preferencia a proposito. El metodo de costo y la fuente de
tipo de cambio estan previstos pero no aprobados, y agregarlos ahora seria
implementar una funcionalidad futura porque aparece en la especificacion.
Sumar una columna nullable despues es una migracion trivial.
"""

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    # El usuario es la clave: una fila por persona, no una coleccion.
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("user_account.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Nullable a proposito: null = "la moneda original de cada activo".
    # No se guarda "" ni "ORIGINAL": un texto vacio y un valor ausente serian
    # dos formas de decir lo mismo y alguna consulta terminaria mirando solo
    # una de las dos.
    display_currency: Mapped[str | None] = mapped_column(String(3))

    def __repr__(self) -> str:
        return f"<UserSettings {self.user_id} {self.display_currency}>"
