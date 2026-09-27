export const metadata = { description: 'Trades a constituent stock against its sector ETF when their residual spread diverges.' };

export function signal({ z, previousPosition, settings }) {
  if (previousPosition === 0) return z >= settings.entryZ ? -1 : z <= -settings.entryZ ? 1 : 0;
  return Math.abs(z) <= settings.exitZ ? 0 : previousPosition;
}
