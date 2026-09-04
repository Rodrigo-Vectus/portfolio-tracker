/**
 * Secciones todavía sin implementar.
 *
 * Portfolio, Operaciones y Activos salieron de acá en la fase 2: ya tienen
 * pantalla propia. Las que quedan siguen la misma regla.
 *
 * Cada una dice qué va a mostrar y en qué fase. No hay datos de ejemplo: en
 * una plataforma financiera, un número inventado en pantalla es peor que una
 * pantalla vacía, porque se parece demasiado a un número real.
 */

import { EmptyState, PageHeading } from "../components/ui";

function Seccion({
  title,
  subtitle,
  pendiente,
  fase,
}: {
  title: string;
  subtitle: string;
  pendiente: string;
  fase: string;
}) {
  return (
    <>
      <PageHeading title={title} subtitle={subtitle} />
      <EmptyState title={pendiente} detail={fase} />
    </>
  );
}

export const Dashboard = () => (
  <Seccion
    title="Dashboard"
    subtitle="Cuánto tenés, dónde está, cuánto ganaste o perdiste."
    pendiente="Todavía no hay nada que resumir."
    fase="Los indicadores necesitan operaciones cargadas (fase 2) y cotizaciones en vivo (fase 3). El dashboard se arma en la fase 6."
  />
);

export const Rendimiento = () => (
  <Seccion
    title="Rendimiento"
    subtitle="Resultado realizado y no realizado, en pesos y en dólares."
    pendiente="Todavía no hay rendimiento que calcular."
    fase="El motor de cálculo (ROI, TWR, XIRR) se construye en la fase 4."
  />
);

export const Historial = () => (
  <Seccion
    title="Historial"
    subtitle="Cómo evolucionó tu cartera en el tiempo."
    pendiente="No hay historial."
    fase="Los snapshots diarios y la reconstrucción histórica llegan en la fase 5."
  />
);
