export const metadata = { description: 'Trades a near-equivalent share class or dual-listed pair using a tight residual threshold.' };

export function signal({ z, previousPosition, settings }) {
  if (previousPosition === 0) return z >= settings.entryZ ? -1 : z <= -settings.entryZ ? 1 : 0;
  return Math.abs(z) <= settings.exitZ ? 0 : previousPosition;
}
