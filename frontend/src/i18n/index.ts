// Texts of the interface: one JSON file per feature in ./fr/, loaded as an i18next namespace.
// Only French ships in v1; English will add ./en/ without touching the components.
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const files = import.meta.glob<{ default: Record<string, unknown> }>('./fr/*.json', {
  eager: true,
});

const fr = Object.fromEntries(
  Object.entries(files).map(([path, module]) => [
    path.replace(/^.*\/(.+)\.json$/, '$1'),
    module.default,
  ]),
);

export const LOCALE = 'fr-FR';
export const TIME_ZONE = 'Europe/Paris';

void i18n.use(initReactI18next).init({
  lng: 'fr',
  fallbackLng: 'fr',
  resources: { fr },
  ns: Object.keys(fr),
  defaultNS: 'common',
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;

const formats = new Map<string, Intl.DateTimeFormat>();

/** Dates and times are always shown in Paris time. */
export function formatDate(value: string | Date, options: Intl.DateTimeFormatOptions): string {
  const key = JSON.stringify(options);
  let format = formats.get(key);
  if (!format) {
    format = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, ...options });
    formats.set(key, format);
  }
  return format.format(typeof value === 'string' ? new Date(value) : value);
}

const numbers = new Intl.NumberFormat(LOCALE);

export function formatNumber(value: number): string {
  return numbers.format(value);
}

const parisParts = new Intl.DateTimeFormat('en-CA', {
  timeZone: TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

/** An instant as a datetime-local value ("2026-11-05T18:00"), in Paris time. */
export function toParisInput(value: Date): string {
  const p = Object.fromEntries(parisParts.formatToParts(value).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

/** The instant of a datetime-local value read in Paris time, whatever the device's zone. */
export function fromParisInput(value: string): Date {
  const guess = new Date(`${value}:00Z`);
  const offsetAt = (instant: Date) =>
    new Date(`${toParisInput(instant)}:00Z`).getTime() - instant.getTime();
  // The offset of the result may differ from the guess's around a change of time.
  const first = new Date(guess.getTime() - offsetAt(guess));
  return new Date(guess.getTime() - offsetAt(first));
}

/** The day of an instant in Paris ("2026-11-05"). */
export function parisDay(value: Date): string {
  return toParisInput(value).slice(0, 10);
}

/** A datetime-local value for `days` days from now at `hour`:00, Paris time. */
export function parisDayAt(days: number, hour: number): string {
  const day = parisDay(new Date(Date.now() + days * 86_400_000));
  return `${day}T${String(hour).padStart(2, '0')}:00`;
}

/** "12,5", "12.5" or "1 200" → "12.5"; empty when the text is not a number. */
export function parseDecimal(text: string): string {
  const value = text.trim().replace(/\s/g, '').replace(',', '.');
  return /^-?\d+(\.\d+)?$/.test(value) ? value : '';
}
