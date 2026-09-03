/**
 * Secciones todavía sin implementar.
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

export const Portfolio = () => (
  <Seccion
    title="Portfolio"
    subtitle="Tus posiciones abiertas, con costo, valor actual y resultado."
    pendiente="No hay posiciones."
    fase="Las posiciones se derivan del historial de operaciones. Se calculan en la fase 2."
  />
);

export const Operaciones = () => (
  <Seccion
    title="Operaciones"
    subtitle="El registro de compras y ventas. Es la fuente de verdad del sistema."
    pendiente="No hay operaciones registradas."
    fase="El libro de operaciones se implementa en la fase 2, junto con la importación de tu planilla anterior."
  />
);

export const Activos = () => (
  <Seccion
    title="Activos"
    subtitle="Catálogo de CEDEARs y criptomonedas con los que operás."
    pendiente="El catálogo está vacío."
    fase="Se carga en la fase 2 y se enriquece con cotizaciones en la fase 3."
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
