/**
 * Tokens visuales de Portfolio Tracker.
 *
 * La dirección visual sigue la de indicadores.ar, que el usuario eligió como
 * referencia: fondo negro, un acento celeste único, tipografía de titular
 * pesada en mayúsculas y datos en monoespaciada.
 *
 * **Lo que no se toma de la referencia:** verde y rojo siguen reservados
 * EXCLUSIVAMENTE para el signo de un resultado financiero. Ningún otro
 * elemento puede usarlos, para que el color siempre signifique "gané" o
 * "perdí" y nunca decore. Esa regla es del proyecto y no se negocia por
 * estética.
 *
 * Cambio respecto de la versión anterior: el fondo pasa de un gris frío a
 * negro. Se pierde el argumento de los halos en OLED, y se gana el contraste
 * de la referencia, que es lo que se pidió.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#000000", // fondo de la página
          900: "#08090B", // barra lateral
          800: "#101215", // tarjetas y superficies
          700: "#181B20", // superficie elevada, hover
          600: "#242830", // bordes
          500: "#333944", // bordes de énfasis
        },
        text: {
          DEFAULT: "#F2F4F7",
          muted: "#98A2B3",
          faint: "#667085",
        },
        // Semánticos de resultado. Intocables.
        gain: "#4FB286",
        loss: "#CF5C55",
        // Dato viejo o estimado: ni éxito ni error.
        stale: "#E0A93B",
        brand: {
          DEFAULT: "#2D9CF0",
          hover: "#4EACF5",
          dim: "#1B6BA8",
          // Fondo tenue para pastillas y estados activos.
          soft: "rgba(45, 156, 240, 0.12)",
        },
      },
      fontFamily: {
        // Titulares: pesada y algo condensada, en mayúsculas.
        display: ['"Archivo"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "-apple-system", "sans-serif"],
        // Cifras, códigos y etiquetas: ancho fijo.
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        micro: ["0.6875rem", { lineHeight: "1.45" }],
        sm: ["0.8125rem", { lineHeight: "1.5" }],
        base: ["0.9375rem", { lineHeight: "1.6" }],
        lg: ["1.125rem", { lineHeight: "1.4" }],
        xl: ["1.5rem", { lineHeight: "1.25" }],
        "2xl": ["2rem", { lineHeight: "1.15" }],
        "3xl": ["2.75rem", { lineHeight: "1.05" }],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        lg: "0.75rem",
        xl: "1rem",
      },
    },
  },
  plugins: [],
};
