"""Proteccion CSRF por doble envio de cookie.

El refresh token vive en una cookie httpOnly, asi que el navegador la manda
sola en cada pedido: un sitio de terceros podria disparar un POST a /refresh
y obtener un access token valido.

La defensa: junto al refresh se emite una cookie `pt_csrf` **legible por
JavaScript**. El cliente tiene que copiar su valor al encabezado
`X-CSRF-Token`. Un sitio ajeno puede provocar el envio de la cookie, pero no
puede leerla (lo impide la politica de mismo origen), asi que no puede armar
el encabezado.

Solo se exige en los metodos que cambian estado.
"""

import secrets

from fastapi import Request

from app.core.security import constant_time_equals

CSRF_COOKIE_NAME = "pt_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(request: Request) -> bool:
    cookie = request.cookies.get(CSRF_COOKIE_NAME)
    header = request.headers.get(CSRF_HEADER_NAME)
    if not cookie or not header:
        return False
    return constant_time_equals(cookie, header)
