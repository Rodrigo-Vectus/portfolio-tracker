# Fase 0 — Scaffolding, arquitectura, Docker y Git

## Que se implemento

Infraestructura completa y verificable. **Ninguna logica de negocio.**

- **Docker Compose** con cinco servicios: `postgres`, `redis`, `backend`,
  `worker`, `frontend`. Postgres y Redis con healthcheck; los servicios de
  aplicacion esperan a que esten sanos antes de arrancar.
- **PostgreSQL 16** sobre volumen persistente `pt_pgdata`. Sin puertos
  publicados al host.
- **Redis 7** con AOF habilitado, volumen `pt_redisdata`, sin puertos al host.
- **FastAPI** con configuracion por variables de entorno (Pydantic Settings) y
  logging estructurado (JSON en produccion, legible en desarrollo).
- **Alembic** sobre el engine async, con la migracion `0001_baseline`. El
  backend aplica `upgrade head` al arrancar.
- **Healthchecks separados**: `/api/health/live` (proceso) y
  `/api/health/ready` (Postgres + Redis + estado de migraciones).
- **Worker ARQ** con un latido cada 5 minutos que escribe en Redis.
- **Frontend React + TypeScript + Vite** con una pantalla de estado que
  consume datos reales de la API. Vite proxea `/api` al backend.
- **Tokens visuales** definidos en `tailwind.config.js`: verde y rojo quedan
  reservados exclusivamente para signo de resultado, cifras en variante
  tabular.
- `.gitignore`, `.env.example`, README y ADR con las 17 decisiones cerradas.

## Que se probo

| Prueba | Resultado |
|---|---|
| Sintaxis de todos los `.py` | compilan |
| `docker-compose.yml` | YAML valido, 5 servicios, 2 volumenes |
| `GET /api/health/live` | 200, devuelve nombre, version y entorno |
| `GET /api/meta` | 200, expone los defaults de D1 y D4 |
| `GET /api/health/ready` sin dependencias | **503** con detalle por servicio y error logueado |
| `GET /api/openapi.json` | 200, las tres rutas registradas |
| `pytest` | 3 pruebas, todas pasan |

El 503 es el resultado buscado: con Postgres y Redis caidos el sistema no
finge estar sano, informa cual dependencia fallo y deja el error en el log.
Es la regla I.2 del proyecto funcionando desde la primera fase.

## Que quedo deliberadamente afuera

Autenticacion, usuarios, modelo financiero, cotizaciones, dashboard. Y
`app/domain/` esta vacio a proposito: es donde vive el motor de calculo y se
escribe en F2, con su suite de casos verificados a mano.

## Verificacion en el servidor

```bash
cd /root/portfolio-tracker
docker compose up -d && docker compose ps
curl -s http://localhost:8000/api/health/ready | python3 -m json.tool
docker compose exec backend pytest -v
```

Los tres chequeos de `ready` tienen que dar `ok`, con la migracion en
`0001_baseline`.
