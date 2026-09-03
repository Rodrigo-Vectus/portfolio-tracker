# Portfolio Tracker

Plataforma de seguimiento de inversiones. Reemplaza una planilla de Excel por
un sistema donde la fuente de verdad es el **historial de operaciones**, y no
un precio escrito a mano.

```
OPERACIONES -> POSICIONES -> COTIZACIONES -> VALUACION -> RENDIMIENTO -> DASHBOARD
```

**Estado: Fase 1** — autenticacion y layout. Todavia no hay modelo financiero
ni cotizaciones.

---

## Stack

| Capa | Tecnologia | Por que |
|---|---|---|
| API | FastAPI + Python 3.12 | Async nativo, validacion con Pydantic, OpenAPI automatico |
| ORM | SQLAlchemy 2.0 (async) + Alembic | `NUMERIC` exacto, migraciones versionadas |
| Base | PostgreSQL 16 | Decimales exactos y `jsonb`. En finanzas, `float` no es opcion |
| Cache y cola | Redis 7 | Cache de cotizaciones y broker de tareas |
| Worker | ARQ | Async nativo, mucho mas liviano que Celery |
| Frontend | React 18 + TypeScript + Vite | Tipos obligatorios: multi-moneda sin tipos es inmanejable |
| Estilos | Tailwind 3 | Tokens definidos en `frontend/tailwind.config.js` |

---

## Estructura

```
portfolio-tracker/
├── docker-compose.yml
├── .env.example              plantilla; el .env real nunca se commitea
├── backend/
│   ├── app/
│   │   ├── main.py           entrada de la API
│   │   ├── core/             configuracion y logging estructurado
│   │   ├── db/               engine, sesiones, Redis
│   │   ├── api/routes/       health, meta
│   │   ├── domain/           motor financiero en Python puro (vacio en F0)
│   │   └── worker/           tareas en segundo plano
│   ├── alembic/              migraciones
│   ├── scripts/              entrypoints
│   └── tests/
├── frontend/
│   └── src/                  pantalla de estado del sistema
└── docs/
    └── adr/                  decisiones de arquitectura
```

---

## Instalacion en Ubuntu Server 22.04

### 1. Docker

Ubuntu 22.04 no trae Docker Engine ni el plugin `compose` v2 en sus
repositorios oficiales, asi que se agrega el repositorio de Docker:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

Verificar:

```bash
docker --version
docker compose version    # debe ser v2.x
```

### 2. Codigo

```bash
mkdir -p /root/portfolio-tracker
cd /root/portfolio-tracker
# copiar aca el contenido de la fase, o clonar el repositorio
```

### 3. Variables de entorno

```bash
cp .env.example .env
```

Generar los dos secretos y editarlos en el `.env`:

```bash
openssl rand -hex 32      # -> SECRET_KEY
openssl rand -base64 24   # -> POSTGRES_PASSWORD
```

Hay que cambiar como minimo: `SECRET_KEY`, `POSTGRES_PASSWORD` e
`INITIAL_ADMIN_PASSWORD`. El backend se niega a arrancar si `SECRET_KEY` tiene
menos de 32 caracteres.

`BIND_ADDR=0.0.0.0` publica los puertos en la red, que es lo que hace falta
para probar desde otra maquina. Para produccion conviene `127.0.0.1` mas un
tunel SSH o un reverse proxy con TLS (llega en F9).

### 4. Levantar

```bash
cd /root/portfolio-tracker
docker compose build
docker compose up -d
docker compose ps
```

La primera build tarda unos minutos: descarga las imagenes base, instala las
dependencias de Python y corre `npm install`.

### 5. Verificar

```bash
# El proceso responde
curl -s http://localhost:8000/api/health/live | python3 -m json.tool

# Las dependencias estan disponibles
curl -s http://localhost:8000/api/health/ready | python3 -m json.tool

# Configuracion de dominio
curl -s http://localhost:8000/api/meta | python3 -m json.tool
```

`/health/ready` deberia devolver los tres chequeos en `ok`:

```json
{
  "status": "ok",
  "checks": {
    "postgres":   {"status": "ok", "detail": "PostgreSQL 16.x ..."},
    "redis":      {"status": "ok", "detail": "PONG"},
    "migrations": {"status": "ok", "detail": "0001_baseline"}
  }
}
```

Desde el navegador:

```
http://IP-DEL-SERVIDOR:5173     pantalla de estado
http://IP-DEL-SERVIDOR:8000/api/docs    documentacion de la API
```

Confirmar que el worker esta vivo:

```bash
docker compose logs worker | tail -20
docker compose exec redis redis-cli GET worker:last_heartbeat
```

El latido corre cada 5 minutos, asi que la primera vez puede tardar. Para
forzarlo:

```bash
docker compose exec backend python -c "
import asyncio
from app.worker.tasks import heartbeat
print(asyncio.run(heartbeat({})))
"
```

Tests:

```bash
docker compose exec backend pytest -v
```

---

## Operacion diaria

```bash
docker compose ps                    # estado
docker compose logs -f backend       # logs en vivo
docker compose restart backend       # reiniciar un servicio
docker compose down                  # apagar (los datos sobreviven)
docker compose down -v               # apagar Y BORRAR LA BASE
```

`docker compose down -v` destruye el volumen `pt_pgdata`. No se usa salvo que
se quiera empezar de cero a proposito.

### Base de datos

Postgres no publica puertos al host. Para entrar:

```bash
docker compose exec postgres psql -U portfolio -d portfolio_tracker
```

Desde una maquina remota, tunel SSH:

```bash
ssh -L 5432:localhost:5432 root@IP-DEL-SERVIDOR
```

### Migraciones

```bash
docker compose exec backend alembic current
docker compose exec backend alembic history
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
```

El backend aplica `alembic upgrade head` solo al arrancar.

### Backup

Automatizar es parte de F8, pero el comando manual funciona desde hoy:

```bash
docker compose exec -T postgres pg_dump -U portfolio portfolio_tracker \
  | gzip > backup-$(date +%F).sql.gz
```

---

## Problemas frecuentes

**El backend reinicia en loop.** Casi siempre falta una variable en `.env`:

```bash
docker compose logs backend | tail -40
```

**`/health/ready` devuelve 503.** Postgres todavia esta arrancando. Los
healthchecks del compose lo contemplan, pero en un servidor lento la primera
vez puede tardar. Reintentar en 30 segundos.

**El frontend falla con `Failed to resolve import "algo"`.** El volumen
anonimo de `node_modules` quedo desactualizado. Compose lo conserva al recrear
el contenedor, asi que reconstruir la imagen no alcanza. El entrypoint del
frontend lo detecta y reinstala solo; si aun asi persiste:

```bash
docker compose rm -sfv frontend    # -v borra el volumen anonimo
docker compose up -d frontend
```

**El frontend no llega a la API.** Vite proxea `/api` a `http://backend:8000`
por la red interna de Docker. Si el backend no esta levantado, la pantalla lo
va a mostrar como "Sin respuesta", que es el comportamiento correcto.

**Puerto ocupado.** Cambiar `BACKEND_PORT` o `FRONTEND_PORT` en el `.env`.

---

## Plan de fases

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Scaffolding, Docker, Postgres, Redis, migraciones, healthchecks | listo |
| 1 | Autenticacion, roles, layout con sidebar | **actual** |
| 2 | Modelo financiero: activos, cuentas, operaciones, lotes, posiciones, caja | |
| 2.5 | Importador del Excel con dry-run y reconciliacion | |
| 3 | Market data: proveedores, cotizaciones, FX, cache, manejo de errores | |
| 4 | Motor de valuacion y rendimiento (ROI, TWR, XIRR, realizado/no realizado) | |
| 5 | Snapshots y backfill historico | |
| 6 | Dashboard | |
| 7 | Administracion y auditoria | |
| 8 | Robustez, seguridad, backups, observabilidad | |
| 9 | Pulido y produccion | |

Las decisiones que fundamentan este plan estan en
[`docs/adr/0001-decisiones-fase-0.md`](docs/adr/0001-decisiones-fase-0.md) y
[`docs/adr/0002-autenticacion.md`](docs/adr/0002-autenticacion.md).

---

## Primer ingreso

El administrador se crea solo al arrancar, a partir de `INITIAL_ADMIN_EMAIL` e
`INITIAL_ADMIN_PASSWORD`. Nace con la marca de **cambio de contrasena
obligatorio**: la clave del `.env` sirve para entrar una vez.

    http://IP-DEL-SERVIDOR:8211

Tras ingresar, la aplicacion no deja pasar a ninguna seccion hasta elegir una
contrasena nueva de al menos 10 caracteres con letras y numeros.

Si el seed no corrio:

    docker compose logs backend | grep seed_admin
    docker compose exec backend python -m app.cli seed-admin

Es idempotente: si el administrador ya existe, no lo pisa.

### Como funciona la sesion

    login  ->  access token (15 min, en memoria del navegador)
           ->  refresh token (7 dias, cookie httpOnly)
           ->  cookie CSRF (legible, se copia al encabezado X-CSRF-Token)

El access token no se guarda en `localStorage`: ahi lo leeria cualquier script
inyectado. Se renueva solo un minuto antes de vencer. Cada renovacion rota el
refresh; si aparece uno ya usado, se revoca la sesion entera por sospecha de
robo. El detalle esta en el ADR 0002.

---

## Reglas del proyecto

1. **No inventar datos financieros.** Si falta una cotizacion se muestra "no
   disponible" o el ultimo valor valido con su antiguedad.
2. **No ocultar errores de cotizacion.** Toda falla de proveedor queda logueada.
3. **No hardcodear secretos.** Nada de `.env`, claves ni tokens en el repo.
4. **No mezclar usuarios.** Toda consulta de portfolio va atada al usuario autenticado.
5. **No avanzar de fase sin OK explicito.**
6. **Exactitud antes que velocidad.** Un calculo mal es peor que una pantalla incompleta.
7. **Distinguir dato de mercado, dato ingresado y dato calculado.** Siempre.

---

## Nota sobre el nombre del proyecto Compose

El `name: pt` del `docker-compose.yml` no es cosmetico. Docker Compose agrupa
contenedores, redes y volumenes por nombre de proyecto: dos stacks distintos
con el mismo nombre se pisan entre si, y un `docker compose down -v` en uno
puede borrar los volumenes del otro. Si en el servidor ya corre otro proyecto,
verificar antes con:

    docker compose ls
