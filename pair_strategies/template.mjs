// Copy this file, rename it (for example: my_strategy.mjs), then add its name
// to pairs.config.json as the "plugin" value for a strategy.
export const metadata = {
  description: 'Replace this text with a short description of your strategy.'
};

// Return 1 to be long the left ticker and short the right ticker.
// Return -1 to short the left ticker and long the right ticker.
// Return 0 to hold no position.
export function signal({ z, spread, hedgeRatio, previousPosition, leftPrice, rightPrice, settings }) {
  // `settings` is the complete strategy object from pairs.config.json.
  // Add your own settings there, then use them here.
  if (previousPosition === 0 && z <= -settings.entryZ) return 1;
  if (previousPosition === 0 && z >= settings.entryZ) return -1;
  if (previousPosition !== 0 && Math.abs(z) <= settings.exitZ) return 0;
  return previousPosition;
}
