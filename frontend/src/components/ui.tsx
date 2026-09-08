/**
 * Piezas visuales compartidas.
 *
 * Se mantienen pocas y sin variantes de más: cada componente nuevo es una
 * decisión de diseño que hay que sostener en todas las pantallas siguientes.
 *
 * Dirección visual: fondo negro, acento celeste único, botones en pastilla,
 * titulares pesados en mayúsculas y datos en monoespaciada.
 */

import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 " +
    "text-sm font-medium transition-colors disabled:cursor-not-allowed " +
    "disabled:opacity-40";

  const estilos = {
    primary: "bg-brand text-ink-950 hover:bg-brand-hover",
    secondary:
      "border border-ink-500 text-text hover:border-brand hover:text-brand",
    ghost: "px-2 text-text-muted hover:text-brand",
  }[variant];

  return <button className={`${base} ${estilos} ${className}`} {...props} />;
}

export function Field({
  label,
  hint,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-text-muted">{label}</span>
      <input
        className={`w-full rounded-lg border border-ink-600 bg-ink-900 px-3.5 py-2.5
                    text-base placeholder:text-text-faint transition-colors
                    focus:border-brand ${className}`}
        {...props}
      />
      {hint && <p className="mt-1.5 text-micro text-text-faint">{hint}</p>}
    </label>
  );
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
        className="w-full rounded-lg border border-ink-600 bg-ink-900 px-3.5 py-2.5
                   text-base transition-colors focus:border-brand"
        {...props}
      >
        {children}
      </select>
      {hint && <p className="mt-1.5 text-micro text-text-faint">{hint}</p>}
    </label>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-loss/40 bg-loss/10 px-3.5 py-2.5 text-sm text-loss">
      {children}
    </p>
  );
}

/**
 * Estado vacío.
 *
 * Dice qué falta y en qué fase llega. Una pantalla vacía sin explicación se
 * confunde con una rota.
 */
export function EmptyState({
  title,
  detail,
}: {
  title: string;
  detail?: string;
}) {
  return (
    <div className="rounded-xl border border-ink-600 bg-ink-800/60 px-6 py-10 text-center">
      <p className="font-medium">{title}</p>
      {detail && (
        <p className="mx-auto mt-2 max-w-prose text-sm text-text-muted">{detail}</p>
      )}
    </div>
  );
}

export function PageHeading({
  title,
  subtitle,
  eyebrow,
  actions,
}: {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="display text-2xl">{title}</h1>
        {subtitle && (
          <p className="mt-2 max-w-prose text-sm text-text-muted">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </header>
  );
}

/** Superficie estándar: tarjetas, formularios, bloques de datos. */
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-ink-600 bg-ink-800 p-5 ${className}`}>
      {children}
    </div>
  );
}

/**
 * Pastilla de etiqueta.
 *
 * `tono` nunca usa verde ni rojo: esos dos siguen reservados para el signo de
 * un resultado. Una etiqueta que los usara haría que el color dejara de
 * significar sólo "gané" o "perdí".
 */
export function Pill({
  children,
  tono = "neutro",
}: {
  children: ReactNode;
  tono?: "neutro" | "marca" | "aviso";
}) {
  const estilos = {
    neutro: "border-ink-500 text-text-muted",
    marca: "border-brand/40 bg-brand-soft text-brand",
    aviso: "border-stale/40 bg-stale/10 text-stale",
  }[tono];

  return (
    <span
      className={`code inline-flex items-center rounded-full border px-2.5
                  py-0.5 text-micro uppercase tracking-wider ${estilos}`}
    >
      {children}
    </span>
  );
}

/**
 * Celda numérica.
 *
 * Monoespaciada y alineada a la derecha: en una tabla de cifras las columnas
 * tienen que alinear, o comparar dos filas obliga a contar dígitos.
 */
export function Num({
  children,
  tono = "neutro",
  className = "",
  title,
}: {
  children: ReactNode;
  tono?: "neutro" | "positivo" | "negativo" | "tenue";
  className?: string;
  title?: string;
}) {
  const color = {
    neutro: "",
    positivo: "text-gain",
    negativo: "text-loss",
    tenue: "text-text-faint",
  }[tono];

  return (
    <span className={`num tabular-nums ${color} ${className}`} title={title}>
      {children}
    </span>
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
    <div className="overflow-x-auto rounded-xl border border-ink-600 bg-ink-800">
      <table className="w-full min-w-[40rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-ink-600">
            {columnas.map((c) => (
              <th
                key={c.titulo}
                scope="col"
                className={`whitespace-nowrap px-4 py-3 text-micro font-medium
                            uppercase tracking-wider text-text-faint ${
                              c.alineacion === "derecha"
                                ? "text-right"
                                : "text-left"
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
    <p className="max-w-prose border-l-2 border-ink-500 py-1 pl-4 text-sm text-text-muted">
      {children}
    </p>
  );
}
