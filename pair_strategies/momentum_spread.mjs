export const metadata = {
  description: 'Follows a spread moving away from normal and exits as the move fades.'
};

export function signal({ z, previousPosition, settings }) {
  if (previousPosition === 0) {
    if (z >= settings.entryZ) return 1;
    if (z <= -settings.entryZ) return -1;
    return 0;
  }
  return Math.abs(z) <= settings.exitZ ? 0 : previousPosition;
}
