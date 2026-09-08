/**
 * Íconos de navegación.
 *
 * Se dibujan a mano en vez de sumar una librería. Son ocho trazos simples y
 * una dependencia nueva obligaría a reconstruir el contenedor cada vez que
 * cambie, a cambio de nada que no esté acá.
 *
 * Todos comparten el mismo trazo y la misma caja para que la columna de
 * íconos de la barra lateral quede pareja.
 */

type Props = { className?: string };

function Base({ children, className = "" }: Props & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-[18px] w-[18px] ${className}`}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const IconDashboard = (p: Props) => (
  <Base {...p}>
    <rect x="3" y="3" width="7" height="9" rx="1.5" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" />
  </Base>
);

export const IconPortfolio = (p: Props) => (
  <Base {...p}>
    <path d="M3 17l5-6 4 4 5-7 4 5" />
    <path d="M3 21h18" />
  </Base>
);

export const IconOperaciones = (p: Props) => (
  <Base {...p}>
    <path d="M4 7h13l-3-3" />
    <path d="M20 17H7l3 3" />
  </Base>
);

export const IconActivos = (p: Props) => (
  <Base {...p}>
    <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
    <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
  </Base>
);

export const IconCuentas = (p: Props) => (
  <Base {...p}>
    <rect x="2.5" y="6" width="19" height="13" rx="2" />
    <path d="M2.5 10h19" />
  </Base>
);

export const IconCaja = (p: Props) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5v9M14.5 9.8c0-1-1.1-1.8-2.5-1.8s-2.5.8-2.5 1.8 1.1 1.6 2.5 1.9 2.5.9 2.5 1.9-1.1 1.8-2.5 1.8-2.5-.8-2.5-1.8" />
  </Base>
);

export const IconRendimiento = (p: Props) => (
  <Base {...p}>
    <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
  </Base>
);

export const IconHistorial = (p: Props) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7v5.2l3.4 2" />
  </Base>
);

export const IconConfiguracion = (p: Props) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2.5v2.2M12 19.3v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" />
  </Base>
);

export const IconEstado = (p: Props) => (
  <Base {...p}>
    <path d="M3 12h4l2.5-6 5 12 2.5-6h4" />
  </Base>
);

export const IconAdmin = (p: Props) => (
  <Base {...p}>
    <path d="M12 3l7.5 3v5.5c0 4.3-3 8.2-7.5 9.5-4.5-1.3-7.5-5.2-7.5-9.5V6z" />
    <path d="M9.5 12l1.8 1.8 3.4-3.6" />
  </Base>
);

export const IconSalir = (p: Props) => (
  <Base {...p}>
    <path d="M15 4h3a2 2 0 012 2v12a2 2 0 01-2 2h-3" />
    <path d="M10 8l-4 4 4 4M6 12h9" />
  </Base>
);
