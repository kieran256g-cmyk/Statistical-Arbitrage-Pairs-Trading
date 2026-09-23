export const metadata = {
  description: 'Fades an extreme spread and exits once it moves back toward normal.'
};

export function signal({ z, previousPosition, settings }) {
  if (previousPosition === 0) {
    if (z >= settings.entryZ) return -1;
    if (z <= -settings.entryZ) return 1;
    return 0;
  }
  return Math.abs(z) <= settings.exitZ ? 0 : previousPosition;
}
