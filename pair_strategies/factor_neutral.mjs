export const metadata = { description: 'Trades a pair after removing its configured market or sector ETF factor.' };

export function signal({ factorZ, previousPosition, settings }) {
  if (previousPosition === 0) return factorZ >= settings.entryZ ? -1 : factorZ <= -settings.entryZ ? 1 : 0;
  return Math.abs(factorZ) <= settings.exitZ ? 0 : previousPosition;
}
