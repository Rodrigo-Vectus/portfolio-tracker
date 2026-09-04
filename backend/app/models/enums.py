"""Enumeraciones del dominio.

Se declaran como enums nativos de PostgreSQL: la base valida el valor, no
solo la aplicacion. Agregar un valor requiere una migracion explicita, que es
exactamente lo que se quiere en un sistema donde el rol define que puede ver
cada persona.
"""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class AuditAction(StrEnum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    TOKEN_REUSE_DETECTED = "TOKEN_REUSE_DETECTED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    USER_ACTIVATED = "USER_ACTIVATED"
    # Fase 2: el libro de operaciones es inmutable, asi que su rastro tambien
    # tiene que serlo. Una anulacion sin registro de quien y por que es un
    # borrado con otro nombre.
    TRANSACTION_CREATED = "TRANSACTION_CREATED"
    TRANSACTION_VOIDED = "TRANSACTION_VOIDED"
    POSITIONS_REBUILT = "POSITIONS_REBUILT"
