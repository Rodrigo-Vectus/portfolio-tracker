"""Esquemas de las preferencias del usuario."""

from pydantic import BaseModel, Field


class SettingsIn(BaseModel):
    """Cambio de preferencias.

    `display_currency` en `null` significa **la moneda original de cada
    activo**: no se convierte nada. Es la unica forma de volver atras, y no
    existe un valor "ninguna" porque un texto vacio y un valor ausente serian
    dos maneras de decir lo mismo.
    """

    display_currency: str | None = Field(
        default=None,
        max_length=3,
        description="USD para ver la cartera en dolares. null no convierte.",
    )


class SettingsOut(BaseModel):
    """Preferencias vigentes.

    **No se informa el `DEFAULT_DISPLAY_CURRENCY` del sistema y eso es
    deliberado.** D55 dice que la conversion a moneda dura se pide de forma
    explicita y no viene por defecto; devolver el default al lado sugeriria
    que una preferencia sin elegir hereda de el, que es justo lo contrario.

    `null` no es un error ni un cero: es "mostrame cada activo en su propia
    moneda".
    """

    display_currency: str | None
