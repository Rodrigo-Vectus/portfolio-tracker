"""Pruebas de las primitivas de seguridad.

No necesitan base de datos: son funciones puras. Es justamente el tipo de
codigo que conviene verificar de forma aislada.
"""

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.schemas.auth import ChangePasswordRequest
from uuid import uuid4


def test_el_hash_no_contiene_la_contrasena() -> None:
    h = hash_password("miClaveSegura2026")
    assert "miClaveSegura2026" not in h
    assert h.startswith("$argon2")


def test_dos_hashes_de_la_misma_clave_son_distintos() -> None:
    """Cada hash lleva su propia sal: dos iguales delatarian su ausencia."""
    assert hash_password("miClaveSegura2026") != hash_password("miClaveSegura2026")


def test_verificacion_acepta_la_correcta_y_rechaza_la_incorrecta() -> None:
    h = hash_password("miClaveSegura2026")
    assert verify_password("miClaveSegura2026", h)
    assert not verify_password("miClaveSegura2027", h)
    assert not verify_password("", h)


def test_el_access_token_lleva_usuario_y_rol() -> None:
    uid = uuid4()
    payload = decode_access_token(create_access_token(uid, "ADMIN"))
    assert payload["sub"] == str(uid)
    assert payload["role"] == "ADMIN"
    assert payload["type"] == "access"


def test_un_token_manipulado_se_rechaza() -> None:
    import jwt

    token = create_access_token(uuid4(), "USER")
    cuerpo = token.split(".")
    manipulado = f"{cuerpo[0]}.{cuerpo[1]}x.{cuerpo[2]}"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(manipulado)


def test_el_refresh_se_guarda_hasheado() -> None:
    raw, stored = generate_refresh_token()
    assert raw != stored
    assert stored == hash_refresh_token(raw)
    assert len(stored) == 64  # sha256 en hexadecimal


@pytest.mark.parametrize(
    "clave",
    ["corta1", "sinnumeros", "1234567890", " conEspacios2026 "],
)
def test_se_rechazan_contrasenas_debiles(clave: str) -> None:
    with pytest.raises(ValueError):
        ChangePasswordRequest(current_password="x", new_password=clave)


def test_se_acepta_una_contrasena_razonable() -> None:
    req = ChangePasswordRequest(current_password="x", new_password="cartera2026segura")
    assert req.new_password == "cartera2026segura"


# --------------------------------------------------------------------------
# Validacion de IP
#
# Regresion: `ip_address` es una columna INET. Un `X-Forwarded-For` con basura
# hacia que PostgreSQL rechazara el INSERT y abortara la transaccion, con lo
# que un login valido terminaba en error 500. La cabecera la controla quien
# hace el pedido, asi que esto era explotable desde afuera.
# --------------------------------------------------------------------------

def test_se_descarta_lo_que_no_es_una_ip() -> None:
    from app.services.audit import _valid_ip

    for basura in ["testclient", "no-soy-una-ip", "999.999.999.999", "", None, "'; DROP"]:
        assert _valid_ip(basura) is None


def test_se_aceptan_ipv4_e_ipv6() -> None:
    from app.services.audit import _valid_ip

    assert _valid_ip("192.168.11.125") == "192.168.11.125"
    assert _valid_ip(" 10.0.0.1 ") == "10.0.0.1"
    assert _valid_ip("2001:db8::1") == "2001:db8::1"


def test_el_user_agent_ausente_no_rompe() -> None:
    """Regresion: el encabezado es opcional y recortar None lanzaba TypeError."""
    from app.services.audit import client_user_agent

    class SinEncabezados:
        headers: dict[str, str] = {}

    assert client_user_agent(None) is None
    assert client_user_agent(SinEncabezados()) is None  # type: ignore[arg-type]


def test_el_user_agent_largo_se_recorta_al_limite_de_la_columna() -> None:
    from app.services.audit import client_user_agent

    class ConUA:
        headers = {"user-agent": "x" * 400}

    assert len(client_user_agent(ConUA())) == 255  # type: ignore[arg-type]
