/**
 * Formateo de cifras.
 *
 * Es la primera prueba automatizada del frontend, y empieza acá por un motivo
 * concreto: de los bugs encontrados hasta ahora, tres salieron de este archivo
 * — `0E-18` mostrado crudo, las fechas de rueda corridas un día, y un
 * formateador de porcentaje que devolvía `25.%`. Los tres eran lógica pura,
 * probable sin navegador, y ninguno lo detectó nada.
 *
 * No necesita DOM ni servidor: son funciones sobre strings.
 */

import { describe, expect, it } from "vitest";
import {
  formatearCantidad,
  formatearFecha,
  formatearImporte,
  formatearPorcentaje,
  haceCuanto,
  signo,
} from "./format";

describe("formatearImporte", () => {
  it("agrupa miles y usa coma decimal", () => {
    expect(formatearImporte("209600")).toBe("209.600,00");
    expect(formatearImporte("1234567.891", 2)).toBe("1.234.567,89");
  });

  it("acepta notación científica", () => {
    // `str()` de un Decimal en cero con escala 18 devuelve "0E-18", y esa
    // cadena llegó a mostrarse tal cual en pantalla.
    expect(formatearImporte("0E-18")).toBe("0,00");
    expect(formatearImporte("1E+3")).toBe("1.000,00");
  });

  it("propaga el acarreo al redondear", () => {
    // Sumar uno a la última posición no alcanza: 999,995 tiene que dar
    // 1.000,00 y no 999,100.
    expect(formatearImporte("999.995")).toBe("1.000,00");
    expect(formatearImporte("9.999")).toBe("10,00");
  });

  it("no pierde dígitos con decimales largos", () => {
    // El realizado por costo promedio es una división que no cierra. Pasar
    // por `number` degradaría el valor antes de formatearlo.
    expect(formatearImporte("477475.1351871143733252380232", 4)).toBe(
      "477.475,1352",
    );
  });

  it("usa el menos tipográfico y no marca el cero negativo", () => {
    expect(formatearImporte("-54102.8648")).toBe("−54.102,86");
    expect(formatearImporte("-0.001")).toBe("0,00");
  });

  it("devuelve la entrada si no es un número", () => {
    expect(formatearImporte("no soy un número")).toBe("no soy un número");
  });
});

describe("formatearCantidad", () => {
  it("recorta los ceros de relleno", () => {
    // La columna es NUMERIC(38,18): 11 CEDEARs llegan como
    // "11.000000000000000000".
    expect(formatearCantidad("10.000000000000000000")).toBe("10");
  });

  it("conserva los decimales que importan", () => {
    // Recortar ceros no es redondear: media unidad de una cripto sigue
    // siendo 0,5.
    expect(formatearCantidad("0.500000000000000000")).toBe("0,5");
  });
});

describe("formatearFecha", () => {
  it("no corre el día", () => {
    // `new Date("2026-09-04")` se interpreta como medianoche UTC, y en
    // Buenos Aires eso cae el día anterior: toda la tabla mostraba un día
    // menos.
    expect(formatearFecha("2026-09-04")).toBe("04/09/2026");
    expect(formatearFecha("2026-01-01")).toBe("01/01/2026");
  });

  it("acepta una fecha con hora y usa sólo el día", () => {
    expect(formatearFecha("2026-09-04T22:30:00")).toBe("04/09/2026");
  });
});

describe("formatearPorcentaje", () => {
  it("convierte la fracción a porcentaje", () => {
    expect(formatearPorcentaje("0.25")).toBe("25,00%");
    expect(formatearPorcentaje("0.2534")).toBe("25,34%");
    expect(formatearPorcentaje("1")).toBe("100,00%");
  });

  it("maneja el cero y los negativos", () => {
    expect(formatearPorcentaje("0")).toBe("0,00%");
    expect(formatearPorcentaje("-0.2")).toBe("−20,00%");
    expect(formatearPorcentaje("-1.5")).toBe("−150,00%");
  });

  it("maneja fracciones muy chicas y valores mayores a uno", () => {
    expect(formatearPorcentaje("0.0007")).toBe("0,07%");
    expect(formatearPorcentaje("12.345678")).toBe("1.234,57%");
  });

  it("formatea el porcentaje inflado de la planilla anterior", () => {
    // 29,07% era lo que mostraba el Excel; 17,65% era el número correcto.
    expect(formatearPorcentaje("0.2907")).toBe("29,07%");
    expect(formatearPorcentaje("0.1765")).toBe("17,65%");
  });
});

describe("signo", () => {
  it("distingue positivo, negativo y cero", () => {
    expect(signo("100")).toBe("positivo");
    expect(signo("-100")).toBe("negativo");
    expect(signo("0")).toBe("cero");
  });

  it("trata como cero un decimal de puros ceros", () => {
    // Es lo que llega de la base cuando el realizado es cero.
    expect(signo("0.000000000000000000")).toBe("cero");
    expect(signo("0E-18")).toBe("cero");
  });

  it("trata el nulo como cero", () => {
    expect(signo(null)).toBe("cero");
  });
});

describe("haceCuanto", () => {
  const ahora = new Date("2026-09-06T20:00:00Z");

  it("describe la antigüedad en palabras", () => {
    expect(haceCuanto("2026-09-06T19:58:00Z", ahora)).toBe("hace 2 min");
    expect(haceCuanto("2026-09-06T17:00:00Z", ahora)).toBe("hace 3 h");
    expect(haceCuanto("2026-09-04T20:00:00Z", ahora)).toBe("hace 2 días");
  });

  it("dice 'recién' cuando es de este minuto", () => {
    expect(haceCuanto("2026-09-06T19:59:40Z", ahora)).toBe("recién");
  });
});
