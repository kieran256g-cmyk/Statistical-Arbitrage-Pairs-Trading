export const metadata = { description: 'Trades divergence in normalized-price distance rather than regression residuals.' };

export function signal({ distanceZ, previousPosition, settings }) {
  if (previousPosition === 0) {
    if (distanceZ >= settings.entryZ) return -1;
    if (distanceZ <= -settings.entryZ) return 1;
    return 0;
  }
  return Math.abs(distanceZ) <= settings.exitZ ? 0 : previousPosition;
}
