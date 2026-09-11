/**
 * El orden de la tabla de posiciones.
 *
 * Se prueba el criterio, no el componente: lo que puede salir mal es que dos
 * filas queden al revés cuando se parecen, o que una fila sin dato aparezca
 * como la mejor o la peor de todas.
 */

import { describe, expect, it } from "vitest";
import { compararDecimal } from "./format";

/** Copia del criterio de `ordenar`, sobre lo mínimo que necesita. */
function ordenarPor(
  filas: { symbol: string; v: string | null }[],
  desc: boolean,
): string[] {
  return [...filas]
    .sort((a, b) => {
      if (a.v === null && b.v === null) return a.symbol.localeCompare(b.symbol);
      if (a.v === null) return 1;
      if (b.v === null) return -1;
      const cmp = compararDecimal(a.v, b.v);
      return desc ? -cmp : cmp;
    })
    .map((f) => f.symbol);
}

describe("orden de posiciones", () => {
  const filas = [
    { symbol: "AAPL", v: "239040" },
    { symbol: "MELI", v: "126600" },
    { symbol: "SPY", v: null },
    { symbol: "QQQ", v: "500000" },
  ];

  it("descendente pone lo más grande primero", () => {
    expect(ordenarPor(filas, true)).toEqual(["QQQ", "AAPL", "MELI", "SPY"]);
  });

  it("ascendente invierte, pero lo que no se sabe sigue al final", () => {
    expect(ordenarPor(filas, false)).toEqual(["MELI", "AAPL", "QQQ", "SPY"]);
  });

  it("una fila sin dato nunca queda primera", () => {
    // No es la mejor ni la peor: es una que no se sabe. En las dos
    // direcciones tiene que caer al final.
    expect(ordenarPor(filas, true).at(-1)).toBe("SPY");
    expect(ordenarPor(filas, false).at(-1)).toBe("SPY");
  });

  it("dos valores que difieren en el decimal dieciocho no se empatan", () => {
    const casi = [
      { symbol: "A", v: "0.10000000000000000001" },
      { symbol: "B", v: "0.10000000000000000002" },
    ];
    expect(ordenarPor(casi, true)).toEqual(["B", "A"]);
  });

  it("varias sin dato conservan un orden estable por símbolo", () => {
    const nulos = [
      { symbol: "ZZZ", v: null },
      { symbol: "AAA", v: null },
    ];
    expect(ordenarPor(nulos, true)).toEqual(["AAA", "ZZZ"]);
  });
});
