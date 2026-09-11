/**
 * Tendencia reciente de un activo, en miniatura.
 *
 * SVG a mano y no una librería: son dos docenas de puntos sin ejes, sin
 * leyenda y sin tooltip, y traer un gráfico completo para eso pesa más de lo
 * que resuelve.
 *
 * **No dice cuánto, dice para dónde.** No lleva escala ni números, porque un
 * eje de 20 píxeles de alto no se puede leer y fingir que sí sería peor que no
 * ponerlo. El número exacto está en la misma fila, dos columnas más allá.
 *
 * **Con menos de dos cierres no dibuja nada.** Un punto solo no es una
 * tendencia, y una línea horizontal inventada diría que el precio estuvo
 * quieto.
 */

interface Props {
  /** Cierres en orden cronológico. */
  valores: number[];
  /** Determina el color: el mismo criterio que el signo de un resultado. */
  ancho?: number;
  alto?: number;
}

export function Sparkline({ valores, ancho = 72, alto = 22 }: Props) {
  if (valores.length < 2) {
    return (
      <span className="text-micro text-text-faint" title="Faltan cierres">
        —
      </span>
    );
  }

  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const rango = max - min;

  // Una serie plana se dibuja en el medio y no dividida por cero.
  const y = (v: number) =>
    rango === 0 ? alto / 2 : alto - 1 - ((v - min) / rango) * (alto - 2);
  const x = (i: number) => (i / (valores.length - 1)) * (ancho - 1);

  const puntos = valores.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const linea = `M ${puntos.join(" L ")}`;

  // Verde y rojo sólo significan el signo de un resultado, y acá eso es
  // exactamente lo que significan: si el último cierre está por encima del
  // primero, el tramo dio ganancia.
  const sube = valores[valores.length - 1] >= valores[0];
  const color = sube ? "#4FB286" : "#CF5C55";

  return (
    <svg
      width={ancho}
      height={alto}
      viewBox={`0 0 ${ancho} ${alto}`}
      role="img"
      aria-label={sube ? "Tendencia en alza" : "Tendencia en baja"}
      className="inline-block align-middle"
    >
      <path
        d={`${linea} L ${(ancho - 1).toFixed(1)},${alto} L 0,${alto} Z`}
        fill={color}
        fillOpacity={0.12}
        stroke="none"
      />
      <path
        d={linea}
        fill="none"
        stroke={color}
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
