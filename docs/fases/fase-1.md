# Fase 1 — Autenticacion, roles y layout

## Que se implemento

**Backend**

- Modelos `user_account`, `refresh_token` y `audit_log`, con enums nativos de
  PostgreSQL. Migracion `0002_auth`.
- Argon2id para contrasenas; JWT HS256 para access tokens.
- Endpoints: `login`, `refresh`, `logout`, `me`, `change-password`,
  y `GET /api/users` (solo administradores).
- Rotacion de refresh con deteccion de reuso y revocacion por familia.
- Proteccion CSRF por doble envio de cookie.
- Freno de fuerza bruta en Redis, por email y por IP.
- Bitacora de auditoria en cada evento de sesion.
- `python -m app.cli seed-admin`, idempotente, ejecutado al arrancar.

**Frontend**

- Contexto de sesion con renovacion silenciosa antes del vencimiento.
- Login, cambio de contrasena obligatorio, rutas protegidas por sesion y rol.
- Layout con barra lateral, responsive, con `Administracion` visible solo
  para administradores.
- Ocho secciones. Las no implementadas dicen que estan vacias y en que fase
  van a tener datos. **Cero datos de ejemplo.**
- Acentos corregidos en toda la interfaz.

## Que se probo

| Prueba | Resultado |
|---|---|
| `pytest` completo | 27 pruebas, todas pasan |
| Rutas registradas en OpenAPI | 9 endpoints |
| `GET /api/auth/me` sin token | 401 |
| `GET /api/users` sin token | 401 |
| `POST /api/auth/refresh` sin CSRF | 403 |
| Email mal formado en login | 422 |
| SQL de las migraciones | 3 tablas, 2 enums, 6 indices, sin errores |
| `tsc --noEmit` | sin errores de tipos |
| `vite build` | 46 modulos, compila |

Las pruebas de `test_auth_api.py` necesitan base y Redis: corren dentro del
contenedor y verifican login, cookies, rotacion y deteccion de reuso.

## Correcciones posteriores a la primera entrega

Dos fallas que encontraron las pruebas de integracion, ambas explotables desde
afuera y ninguna detectable sin base de datos real.

**`ip_address` acepta cualquier cosa.** La columna es de tipo `INET`.
PostgreSQL rechaza lo que no sea una direccion y ese rechazo aborta la
transaccion completa, asi que un `X-Forwarded-For: basura` convertia un login
valido en un error 500. El encabezado lo controla quien hace el pedido.
Ahora todo pasa por `_valid_ip`: ante la duda se guarda NULL, porque perder la
IP de una entrada de auditoria es mucho menos grave que perder la operacion.

**El user agent es opcional.** `request.headers.get("user-agent")[:255]` lanza
`TypeError` cuando el cliente no envia el encabezado. Se centralizo en
`client_user_agent`, que ademas trunca a los 255 caracteres de la columna.

Las dos tienen prueba de regresion en `test_security.py`, sin base de datos.

**El CSRF rotaba en cada refresco.** La prueba de deteccion de reuso devolvia
403 en lugar de 401. La prueba estaba mal escrita —reusaba un CSRF capturado
antes del refresco— pero dejo a la vista que rotar el token en cada refresco no
aporta seguridad y rompe a cualquier cliente que lo cachee. Ahora el CSRF es
estable durante la sesion; lo que rota es el refresh. Se agregaron dos pruebas:
una verifica que el CSRF se conserva entre refrescos, otra que tras detectar un
reuso queda revocada la familia entera, incluido el token bueno.

**Pruebas con un unico cliente compartido.** `TestClient` levanta su propio
bucle de eventos y el pool de asyncpg ata cada conexion al bucle donde nacio.
Un cliente por prueba hacia que la segunda tomara una conexion del bucle
anterior. El cliente pasa a ser de alcance `session` en `conftest.py`, con las
cookies limpiadas entre pruebas para que el orden no altere los resultados.

## Que quedo afuera

Crear y desactivar usuarios, permisos granulares y consulta de la bitacora:
son la Fase 7. La bitacora ya se escribe; falta la pantalla para leerla.

## Verificacion

```bash
docker compose exec backend pytest -v
curl -s -X POST http://localhost:8210/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"rgonzalez@vectus.la","password":"Vectus2026"}' | python3 -m json.tool
```

En el navegador, `http://IP:8211` debe redirigir al login. Tras ingresar,
exige elegir una contrasena nueva antes de mostrar el menu.
