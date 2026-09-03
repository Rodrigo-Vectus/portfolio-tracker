/**
 * Tokens visuales de Portfolio Tracker.
 *
 * Criterio: fondo frio de baja luminosidad (no negro puro, que en pantallas
 * OLED produce halos alrededor de los numeros), un unico acento de marca en
 * laton, y dos colores semanticos reservados EXCLUSIVAMENTE para signo de
 * resultado. Ningun otro elemento de la interfaz puede usar verde o rojo:
 * asi el color siempre significa "gane" o "perdi" y nunca decora.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#0E1319", // fondo de la aplicacion
          800: "#151B22", // superficie
          700: "#1C242D", // superficie elevada
          600: "#232C36", // bordes
        },
        text: {
          DEFAULT: "#E8EDF2",
          muted: "#8695A3",
          faint: "#5C6975",
        },
        gain: "#4FB286",
        loss: "#CF5C55",
        stale: "#C6A15B", // dato viejo o estimado: ni exito ni error
        brand: "#C6A15B",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "-apple-system", "sans-serif"],
      },
      fontSize: {
        // Escala modular 1.25 sobre una base de 15px
        micro: ["0.75rem", { lineHeight: "1.4" }],
        sm: ["0.8125rem", { lineHeight: "1.5" }],
        base: ["0.9375rem", { lineHeight: "1.6" }],
        lg: ["1.1719rem", { lineHeight: "1.4" }],
        xl: ["1.4648rem", { lineHeight: "1.3" }],
        "2xl": ["1.8311rem", { lineHeight: "1.2" }],
      },
    },
  },
  plugins: [],
};
