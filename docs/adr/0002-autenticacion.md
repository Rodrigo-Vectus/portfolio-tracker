# ADR 0002 — Arquitectura de autenticacion

Fecha: 2026-09-03 · Estado: aceptado · Fase 1

## Donde vive el access token

**En memoria del navegador, nunca en `localStorage`.**

`localStorage` es legible por cualquier script que corra en la pagina. Un XSS
—una dependencia npm comprometida alcanza— se lleva el token y con el, la
cartera. Una variable de modulo muere al recargar, que es exactamente lo que
se quiere.

El costo es que cada recarga necesita renovar. Para eso esta el refresh.

## Donde vive el refresh token

**Cookie `httpOnly`, `SameSite=Lax`, `path=/api/auth`.**

`httpOnly` la hace invisible para JavaScript, asi que un XSS no puede robarla.
`path` restringido: ningun endpoint fuera de `/api/auth` la necesita.

A cambio queda expuesta a CSRF, porque el navegador la envia sola. De ahi la
proteccion por doble envio.

## CSRF por doble envio

Junto al refresh se emite `pt_csrf`, **legible** por JavaScript. El cliente
copia su valor al encabezado `X-CSRF-Token`. Un sitio de terceros puede
provocar que el navegador mande la cookie, pero no puede leerla —lo impide la
politica de mismo origen— asi que no puede construir el encabezado.

Se exige en `POST /refresh`, `/logout` y `/change-password`. No en `/login`,
que todavia no tiene sesion que proteger.

**El CSRF no rota; el refresh si.** Son dos secretos con propiedades
distintas. El refresh es de un solo uso y su rotacion es justamente lo que
permite detectar un robo. El CSRF no se consume: lo que lo protege es la
politica de mismo origen, no su rareza, asi que rotarlo no agrega nada.

Rotarlo si tiene un costo: cualquier cliente que lo lea una vez y lo guarde
queda enviando un valor viejo, y un pedido legitimo termina en 403. Peor aun,
como la validacion CSRF corre antes que la logica de sesion, ese 403 tapa
cualquier otra respuesta —incluido el 401 por reuso de refresh—, y el
diagnostico se vuelve enganoso.

Se emite uno nuevo al iniciar sesion y se conserva durante toda la sesion,
renovando solo su vencimiento.

## Rotacion y deteccion de reuso

Cada refresco emite un token nuevo y marca el anterior como reemplazado. Los
tokens nacidos de un mismo login comparten un `family_id`.

Si aparece un token **ya rotado**, la unica explicacion razonable es que
alguien lo copio. La respuesta es revocar la familia completa: el atacante
queda afuera y el usuario legitimo tambien, obligado a reingresar su clave.
Preferimos la molestia a la sesion secuestrada.

El refresh se guarda **hasheado** con SHA-256. Un volcado de la base no
permite reconstruir sesiones activas. Es opaco y no un JWT a proposito: un JWT
revocado sigue siendo criptograficamente valido, mientras que este solo vale
si la fila existe y no esta revocada.

## Argon2id, no bcrypt

Ganador del Password Hashing Competition, mucho mas resistente a ataques con
GPU, y sin el limite de 72 bytes de bcrypt, que trunca contrasenas largas en
silencio. Parametros: `time_cost=3`, `memory_cost=64 MiB`, `parallelism=4`.

`check_needs_rehash` permite endurecer el costo con el tiempo: en el proximo
login valido el hash se regenera sin que el usuario note nada.

## `tokens_valid_from`

Marca de tiempo en el usuario. Todo access token emitido antes queda invalido,
aunque no haya expirado. Se actualiza al cambiar la contrasena.

Sin esto, un token robado seguiria funcionando hasta 15 minutos despues de que
el usuario, alarmado, cambiara su clave.

## El rol es un enum, no una tabla

La especificacion propone una tabla `Role`. Para dos roles fijos, una tabla
mas una de permisos es maquinaria sin uso: cada consulta paga un join para
leer un valor que nunca cambia.

Se usa un enum nativo de PostgreSQL: la base valida el valor y agregar uno
exige una migracion explicita, que es la friccion correcta cuando lo que esta
en juego es quien ve que. Si aparece un tercer rol con permisos granulares,
se migra entonces.

## Mensajes de error deliberadamente vagos

Email inexistente, contrasena incorrecta y cuenta desactivada devuelven **el
mismo** mensaje y el mismo codigo. Distinguirlos convertiria el login en un
detector de cuentas registradas.

Cuando el email no existe igual se calcula un hash, para que el tiempo de
respuesta tampoco lo delate.

## Cambio obligatorio de contrasena

El administrador sembrado nace con `must_change_password=true`. Su clave esta
escrita en el `.env` del servidor: sirve para entrar una vez.

Mientras la bandera este activa, `get_active_user` rechaza todo con 403. El
unico endpoint accesible es el de cambio de clave.

## Limite de intentos

Contador en Redis por email **y** por IP: por email para que nadie martille
una cuenta, por IP para que nadie recorra muchas cuentas desde el mismo lugar.
Ocho intentos, quince minutos de espera.

Si Redis no responde, el freno se desactiva en lugar de bloquear el ingreso.
Quedarse afuera de la propia plataforma por una caida del cache es peor que
perder temporalmente el limite. La falla queda logueada.

## Auditoria desde el primer dia

Se registran ingresos exitosos y fallidos, cierres de sesion, renovaciones,
reusos detectados y cambios de contrasena. Con el motivo del rechazo, la IP y
el user agent. Nunca contrasenas ni tokens.

Los intentos fallidos son justamente los que interesan. Los registros no se
editan ni se borran desde la aplicacion.
