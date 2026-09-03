# Documentacion

- `adr/` — decisiones de arquitectura, una por archivo. Se agregan, no se editan.
- `fases/` — cierre de cada fase: que se implemento, que se probo, que quedo pendiente.

## Flujo del sistema

    OPERACIONES        lo que el usuario registro. Inmutable.
         v
    POSICIONES         derivadas del historial. Nunca se editan a mano.
         v
    COTIZACIONES       obtenidas de proveedores externos, con fuente y timestamp.
         v
    VALUACION          posicion x cotizacion x tipo de cambio.
         v
    RENDIMIENTO        realizado, no realizado, ROI, TWR, XIRR.
         v
    DASHBOARD

Ningun paso escribe hacia atras. Si un numero parece raro, se reconstruye
desde las operaciones y se compara.

## Origen del dato

Todo valor monetario que salga de la API viaja con su procedencia:

    INPUT      lo cargo el usuario
    MARKET     vino de un proveedor externo
    COMPUTED   lo calculo la plataforma

mas `as_of`, `source` y `stale`. El principio de la seccion 3 de la
especificacion deja de ser una intencion y pasa a ser un contrato.
