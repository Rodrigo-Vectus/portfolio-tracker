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
 *
 * **Revisión 2026-09-11.** Se toman tres principios del sistema de Linear, que
 * es el que menos nos obligaba a cambiar porque su canvas ya era casi el
 * nuestro:
 *
 * 1. **La elevación se construye con bordes, no con sombras.** Una sombra
 *    sobre negro es una mancha gris; un borde de un píxel define el mismo
 *    límite sin ensuciar el fondo.
 * 2. **Tres radios y ninguno más.** 6px en controles, 12px en tarjetas, pill
 *    en botones y pastillas. Cada radio extra es una decisión que hay que
 *    sostener en todas las pantallas siguientes.
 * 3. **Escala de superficies progresiva.** Cuatro niveles con saltos parejos,
 *    para que "más elevado" se lea sin tener que compararlos lado a lado.
 *
 * **Lo que NO se toma de Linear:** su sistema usa verde y rojo como acentos
 * decorativos y dice explícitamente que no son colores de estado. Acá es al
 * revés y no se negocia.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Escala de superficies. Los saltos son parejos a propósito: el ojo
        // tiene que distinguir un nivel del siguiente sin compararlos.
        ink: {
          950: "#000000", // canvas de la página
          900: "#08090B", // barra lateral, superficie contenida
          800: "#101215", // tarjetas
          700: "#181B20", // superficie elevada, hover, panel modal
          600: "#242830", // borde hairline
          500: "#333944", // borde de énfasis, separador de sección
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
        // `InterVariable` (rsms.me) primero: es la unica que trae el cero
        // barrado y los pesos intermedios. `Inter` de Google queda de
        // respaldo, y `system-ui` si no hay red.
        sans: [
          '"InterVariable"',
          '"Inter"',
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
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
      // Tres radios y nada más: controles, tarjetas y pastillas.
      borderRadius: {
        DEFAULT: "0.375rem", // 6px  — inputs, selects, botones cuadrados
        lg: "0.375rem", // alias del anterior: evita un cuarto radio por descuido
        xl: "0.75rem", // 12px — tarjetas y paneles
      },
      // Escala de espaciado de la referencia. No reemplaza la de Tailwind:
      // agrega los pasos que faltaban para no caer en valores arbitrarios.
      spacing: {
        section: "6rem", // 96px — separación entre bloques de una pantalla
        card: "1.5rem", // 24px — padding interno de una tarjeta
      },
      letterSpacing: {
        display: "-0.022em",
      },
    },
  },
  plugins: [],
};
