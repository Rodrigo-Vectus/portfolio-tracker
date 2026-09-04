/**
 * Piezas visuales compartidas.
 *
 * Se mantienen pocas y sin variantes de más: cada componente nuevo es una
 * decisión de diseño que hay que sostener en todas las pantallas siguientes.
 */

import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" }) {
  const base =
    "inline-flex items-center justify-center rounded px-4 py-2 text-sm font-medium " +
    "transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const styles =
    variant === "primary"
      ? "bg-brand text-ink-900 hover:bg-brand/90"
      : "text-text-muted hover:bg-ink-700 hover:text-text";
  return (
    <button className={`${base} ${styles} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-text-muted">{label}</span>
      <input
        className="w-full rounded border border-ink-600 bg-ink-800 px-3 py-2 text-base
                   placeholder:text-text-faint focus:border-brand"
        {...props}
      />
      {hint && <span className="mt-1 block text-sm text-text-faint">{hint}</span>}
    </label>
  );
}

/** Mensaje de error. Dice qué pasó, sin disculparse ni dramatizar. */
export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="border-l-2 border-loss py-1 pl-3 text-sm text-loss">
      {children}
    </p>
  );
}

/**
 * Estado vacío.
 *
 * Regla del proyecto: una sección sin datos dice que no tiene datos y en qué
 * fase los va a tener. Nunca muestra números de ejemplo, porque un número
 * inventado en una plataforma financiera es peor que una pantalla en blanco.
 */
export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="max-w-prose border-l-2 border-ink-600 py-2 pl-4">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-text-muted">{detail}</p>
    </div>
  );
}

export function PageHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-8">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {subtitle && <p className="mt-1 max-w-prose text-text-muted">{subtitle}</p>}
    </header>
  );
}

/**
 * Celda numérica.
 *
 * Activa `tabular-nums` y alinea a la derecha: en una tabla de cifras las
 * columnas tienen que alinear, o comparar dos filas obliga a contar dígitos.
 */
export function Num({
  children,
  tono = "neutro",
  className = "",
}: {
  children: ReactNode;
  tono?: "neutro" | "positivo" | "negativo" | "tenue";
  className?: string;
}) {
  const color =
    tono === "positivo"
      ? "text-gain"
      : tono === "negativo"
        ? "text-loss"
        : tono === "tenue"
          ? "text-text-faint"
          : "";
  return <span className={`num tabular-nums ${color} ${className}`}>{children}</span>;
}

export function Select({
  label,
  children,
  hint,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-text-muted">{label}</span>
      <select
        className="w-full rounded border border-ink-600 bg-ink-800 px-3 py-2 text-base
                   focus:border-brand"
        {...props}
      >
        {children}
      </select>
    </label>
  );
}

/**
 * Tabla de datos.
 *
 * Sin bordes por celda ni fondos alternados: en una grilla financiera la
 * decoración compite con las cifras, que son lo único que hay que leer.
 */
export function Tabla({
  columnas,
  children,
}: {
  columnas: { titulo: string; alineacion?: "izquierda" | "derecha" }[];
  children: ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-ink-600 text-text-muted">
            {columnas.map((c) => (
              <th
                key={c.titulo}
                scope="col"
                // El relleno va de los dos lados: una columna alineada a la
                // derecha termina justo en el borde, y si la siguiente empieza
                // ahí mismo los encabezados se tocan.
                className={`whitespace-nowrap px-3 py-2 font-medium first:pl-0 last:pr-0 ${
                  c.alineacion === "derecha" ? "text-right" : "text-left"
                }`}
              >
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/** Aviso que no es un error: explica una limitación conocida del sistema. */
export function Nota({ children }: { children: ReactNode }) {
  return (
    <p className="max-w-prose border-l-2 border-stale py-1 pl-3 text-sm text-text-muted">
      {children}
    </p>
  );
}
