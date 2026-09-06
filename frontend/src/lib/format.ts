/**
 * Formateo de cifras.
 *
 * La API entrega los importes como **string**, y estas funciones los formatean
 * **sin convertirlos a `number` en ningún momento**.
 *
 * El motivo es el mismo por el que la base usa `NUMERIC` y el backend usa
 * `Decimal`: el `number` de JavaScript es un flotante de doble precisión, y un
 * `NUMERIC(38,18)` no entra. `Number("477475.1351871143733252380232")` ya
 * pierde dígitos al leerse, antes de que nadie lo formatee.
 *
 * Sería fácil escribir `parseFloat(x).toLocaleString()` y que el resultado se
 * viera bien en pantalla el 99% de las veces. El 1% restante es un número mal
 * en una plataforma financiera, y es exactamente la clase de error que este
 * proyecto existe para evitar.
 *
 * Así que el redondeo y el agrupado se hacen sobre el texto.
 */

interface PartesDecimal {
  negativo: boolean;
  entero: string;
  fraccion: string;
}

/**
 * Expande la notación científica a posicional.
 *
 * El backend ya entrega los importes en forma posicional, pero esto queda como
 * segunda barrera. `str()` de un Decimal en cero con escala 18 devuelve
 * `"0E-18"`, y esa cadena llegó a mostrarse tal cual en pantalla. Un
 * formateador que no reconoce su entrada no debería devolverla cruda.
 */
function expandirExponente(valor: string): string {
  const m = valor.match(/^(-?)(\d+)(?:\.(\d+))?[eE]([+-]?\d+)$/);
  if (m === null) return valor;

  const [, signoTxt, enteroTxt, fraccionTxt = "", expTxt] = m;
  const digitos = enteroTxt + fraccionTxt;
  const exp = Number(expTxt) - fraccionTxt.length;

  if (exp >= 0) return signoTxt + digitos + "0".repeat(exp);

  const corte = digitos.length + exp;
  if (corte > 0) {
    return `${signoTxt}${digitos.slice(0, corte)}.${digitos.slice(corte)}`;
  }
  return `${signoTxt}0.${"0".repeat(-corte)}${digitos}`;
}

function partir(valor: string): PartesDecimal | null {
  const limpio = expandirExponente(valor.trim());
  if (!/^-?\d+(\.\d+)?$/.test(limpio)) return null;

  const negativo = limpio.startsWith("-");
  const sinSigno = negativo ? limpio.slice(1) : limpio;
  const [entero, fraccion = ""] = sinSigno.split(".");
  return { negativo, entero, fraccion };
}

/** Redondea la parte decimal a `decimales`, propagando el acarreo al entero. */
function redondear(partes: PartesDecimal, decimales: number): PartesDecimal {
  const { negativo, entero, fraccion } = partes;
  if (fraccion.length <= decimales) {
    return { negativo, entero, fraccion: fraccion.padEnd(decimales, "0") };
  }

  const conservada = fraccion.slice(0, decimales);
  const siguiente = Number(fraccion[decimales]);

  if (siguiente < 5) return { negativo, entero, fraccion: conservada };

  // Acarreo dígito por dígito. Con 999,99 → 1.000,00 no alcanza con sumar uno
  // a la última posición.
  const digitos = (entero + conservada).split("");
  let i = digitos.length - 1;
  let llevo = 1;
  while (i >= 0 && llevo === 1) {
    const suma = Number(digitos[i]) + 1;
    digitos[i] = String(suma % 10);
    llevo = suma >= 10 ? 1 : 0;
    i--;
  }
  const resultado = (llevo === 1 ? "1" : "") + digitos.join("");
  const corte = resultado.length - decimales;
  return {
    negativo,
    entero: resultado.slice(0, corte) || "0",
    fraccion: resultado.slice(corte),
  };
}

function agrupar(entero: string): string {
  return entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/**
 * Formatea un importe con separador de miles y coma decimal, al estilo
 * rioplatense.
 */
export function formatearImporte(valor: string, decimales = 2): string {
  const partes = partir(valor);
  if (partes === null) return valor;

  const r = redondear(partes, decimales);
  const cuerpo =
    decimales > 0 ? `${agrupar(r.entero)},${r.fraccion}` : agrupar(r.entero);

  // Un cero negativo es ruido: −0,00 no significa nada distinto de 0,00.
  const esCero = /^0+$/.test(r.entero) && /^0*$/.test(r.fraccion);
  return r.negativo && !esCero ? `−${cuerpo}` : cuerpo;
}

/**
 * Formatea una cantidad de unidades.
 *
 * Los ceros finales se recortan: 11 CEDEARs se leen mejor como "11" que como
 * "11,000000000000000000", pero 0,5 BTC tiene que mostrar sus decimales.
 */
export function formatearCantidad(valor: string, maximo = 8): string {
  const partes = partir(valor);
  if (partes === null) return valor;

  const recortada = partes.fraccion.slice(0, maximo).replace(/0+$/, "");
  const cuerpo = recortada
    ? `${agrupar(partes.entero)},${recortada}`
    : agrupar(partes.entero);
  return partes.negativo ? `−${cuerpo}` : cuerpo;
}

/** Signo de un resultado. Determina el color, que solo significa eso. */
export function signo(valor: string | null): "positivo" | "negativo" | "cero" {
  const partes = partir(valor ?? "0");
  if (partes === null) return "cero";
  const esCero = /^0+$/.test(partes.entero) && /^0*$/.test(partes.fraccion);
  if (esCero) return "cero";
  return partes.negativo ? "negativo" : "positivo";
}

/**
 * Formatea una fecha de rueda (`YYYY-MM-DD`).
 *
 * **No usa `new Date(iso)` y el motivo importa.** El estándar manda
 * interpretar una fecha sin hora como medianoche **UTC**, así que
 * `new Date("2026-09-04").toLocaleDateString("es-AR")` devuelve `03/09/2026`:
 * medianoche UTC menos tres horas cae el día anterior.
 *
 * El backend guarda el día de rueda correcto; era el navegador el que lo
 * corría. Es el mismo error que se corrigió del lado del servidor, en el otro
 * extremo de la cadena.
 *
 * Una fecha de rueda no tiene hora ni zona: es un día calendario. Se parte el
 * texto y se muestra, sin pasar por `Date`.
 */
export function formatearFecha(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m === null) return iso;
  const [, anio, mes, dia] = m;
  return `${dia}/${mes}/${anio}`;
}

/** Formatea un instante con hora. Acá sí corresponde convertir a hora local. */
export function formatearMomento(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}


/**
 * Cuánto hace, en palabras.
 *
 * Se prefiere "hace 3 horas" a una marca de tiempo ISO: la pregunta que se
 * está respondiendo es si el precio sirve, no cuál es su instante exacto.
 */
export function haceCuanto(iso: string, ahora: Date = new Date()): string {
  const momento = new Date(iso);
  if (Number.isNaN(momento.getTime())) return "";

  const minutos = Math.floor((ahora.getTime() - momento.getTime()) / 60000);
  if (minutos < 1) return "recién";
  if (minutos < 60) return `hace ${minutos} min`;

  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;

  const dias = Math.floor(horas / 24);
  return dias === 1 ? "hace 1 día" : `hace ${dias} días`;
}
