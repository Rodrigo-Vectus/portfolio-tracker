/**
 * Ranking de mejores y peores posiciones.
 *
 * **No calcula el rendimiento: lo ordena.** El ROI viene de `/performance`,
 * donde lo produce `app/domain/performance.roi_de_posicion`. Recalcularlo acá
 * sería una segunda copia de una fórmula financiera, y cuando dos copias
 * divergen los números siguen pareciendo razonables (Regla 27).
 *
 * Vive en un módulo propio y no dentro del componente para poder probarlo:
 * los componentes React no tienen pruebas, y esta es la parte donde un error
 * cambia qué se muestra como mejor y qué como peor.
 */

import { compararDecimal } from "./format";

/** Lo mínimo que el ranking le pide a una posición. */
export interface Rankeable {
  symbol: string;
  roi: string | null;
}

export interface Ranking<T extends Rankeable> {
  /** De mayor a menor rendimiento. */
  mejores: T[];
  /** De menor a mayor rendimiento. */
  peores: T[];
  /** Todas las calculables ordenadas de mayor a menor. */
  ordenadas: T[];
  /** Las que no tienen ROI. Se listan aparte, nunca como cero. */
  sinDato: T[];
  /**
   * `true` cuando hay suficientes posiciones para que dos columnas signifiquen
   * algo. Con pocas, mejores y peores serían casi las mismas y el podio
   * sugeriría una comparación que no existe.
   */
  hayPodio: boolean;
}

/** Debajo de esto no se parte en dos columnas: se muestra una lista sola. */
export const MINIMO_PARA_PODIO = 4;

export function rankear<T extends Rankeable>(
  posiciones: T[],
  cuantas = 3,
  minimoParaPodio = MINIMO_PARA_PODIO,
): Ranking<T> {
  // Una posición sin ROI no es una posición con ROI cero. Un cero la ubicaría
  // en el medio de la tabla como si hubiera rendido nada, y "no se pudo
  // calcular" es una afirmación distinta (Regla 29).
  const sinDato = posiciones.filter((p) => p.roi === null);
  const conDato = posiciones.filter((p) => p.roi !== null);

  const ordenadas = [...conDato].sort((a, b) => compararDecimal(b.roi, a.roi));

  const hayPodio = conDato.length >= minimoParaPodio;

  return {
    ordenadas,
    // Los peores se toman del final y se dan vuelta, así el primero de la
    // lista es el peor de todos.
    mejores: hayPodio ? ordenadas.slice(0, cuantas) : [],
    peores: hayPodio ? ordenadas.slice(-cuantas).reverse() : [],
    sinDato,
    hayPodio,
  };
}
