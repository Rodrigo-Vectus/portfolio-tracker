import { describe, expect, it } from "vitest";
import { compararDecimal } from "./format";
import { MINIMO_PARA_PODIO, rankear, type Rankeable } from "./ranking";

const p = (symbol: string, roi: string | null): Rankeable => ({ symbol, roi });

describe("compararDecimal", () => {
  it("ordena por parte entera sin mirar el largo del texto", () => {
    expect(compararDecimal("9", "10")).toBeLessThan(0);
    expect(compararDecimal("10", "9")).toBeGreaterThan(0);
  });

  it("no se deja engañar por el largo de la fracción", () => {
    // Lexicográfico a secas diría que "0.45" es mayor que "0.5".
    expect(compararDecimal("0.5", "0.45")).toBeGreaterThan(0);
    expect(compararDecimal("0.45", "0.5")).toBeLessThan(0);
  });

  it("trata los ceros de relleno como iguales", () => {
    expect(compararDecimal("0.50", "0.5")).toBe(0);
    expect(compararDecimal("007", "7")).toBe(0);
  });

  it("un negativo siempre es menor que un positivo", () => {
    expect(compararDecimal("-0.01", "0")).toBeLessThan(0);
    expect(compararDecimal("-100", "-99")).toBeLessThan(0);
  });

  it("distingue decimales que number confundiría", () => {
    // Number() colapsa los dos a 0.1 y los daría iguales.
    const a = "0.10000000000000000001";
    const b = "0.10000000000000000002";
    expect(Number(a) === Number(b)).toBe(true);
    expect(compararDecimal(a, b)).toBeLessThan(0);
  });

  it("acepta notación científica", () => {
    expect(compararDecimal("1E-2", "0.01")).toBe(0);
  });

  it("manda al final lo que no es un número, no al medio", () => {
    expect(compararDecimal(null, "-999")).toBeLessThan(0);
    expect(compararDecimal("hola", "-999")).toBeLessThan(0);
  });
});

describe("rankear", () => {
  const cinco = [
    p("AAPL", "0.10"),
    p("MSFT", "-0.05"),
    p("QQQ", "0.35"),
    p("SPY", "-0.20"),
    p("MELI", "0.02"),
  ];

  it("ordena de mayor a menor rendimiento", () => {
    const r = rankear(cinco);
    expect(r.ordenadas.map((x) => x.symbol)).toEqual([
      "QQQ",
      "AAPL",
      "MELI",
      "MSFT",
      "SPY",
    ]);
  });

  it("los mejores arrancan por el mejor y los peores por el peor", () => {
    const r = rankear(cinco);
    expect(r.mejores.map((x) => x.symbol)).toEqual(["QQQ", "AAPL", "MELI"]);
    expect(r.peores.map((x) => x.symbol)).toEqual(["SPY", "MSFT", "MELI"]);
  });

  it("no arma podio con pocas posiciones", () => {
    const r = rankear(cinco.slice(0, MINIMO_PARA_PODIO - 1));
    expect(r.hayPodio).toBe(false);
    expect(r.mejores).toEqual([]);
    expect(r.peores).toEqual([]);
    // La lista ordenada sigue estando: lo que no se muestra es el podio.
    expect(r.ordenadas).toHaveLength(3);
  });

  it("una posición sin ROI no se ordena como cero", () => {
    const r = rankear([p("AAPL", "0.10"), p("SPY", null), p("MSFT", "-0.10")]);
    expect(r.ordenadas.map((x) => x.symbol)).toEqual(["AAPL", "MSFT"]);
    expect(r.sinDato.map((x) => x.symbol)).toEqual(["SPY"]);
  });

  it("con todas sin ROI no inventa un ranking", () => {
    const r = rankear([p("AAPL", null), p("SPY", null)]);
    expect(r.ordenadas).toEqual([]);
    expect(r.hayPodio).toBe(false);
    expect(r.sinDato).toHaveLength(2);
  });

  it("no modifica el arreglo que recibe", () => {
    const original = [...cinco];
    rankear(cinco);
    expect(cinco).toEqual(original);
  });

  it("una lista vacía no explota", () => {
    const r = rankear([]);
    expect(r.ordenadas).toEqual([]);
    expect(r.sinDato).toEqual([]);
    expect(r.hayPodio).toBe(false);
  });
});
