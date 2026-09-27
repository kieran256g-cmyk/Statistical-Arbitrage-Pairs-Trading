export const metadata = { description: 'Trades an OLS hedge-ratio residual after the engine validates mean reversion.' };

export function signal({ z, previousPosition, settings }) {
  if (previousPosition === 0) return z >= settings.entryZ ? -1 : z <= -settings.entryZ ? 1 : 0;
  return Math.abs(z) <= settings.exitZ ? 0 : previousPosition;
}
