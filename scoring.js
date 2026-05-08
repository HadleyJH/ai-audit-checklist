export function calculateWeightedScore(score, weighting) {
  return Number(score) * Number(weighting);
}

export function calculateTotalScore(items) {
  return items.reduce((total, item) => {
    return total + calculateWeightedScore(item.score, item.weighting);
  }, 0);
}

export function calculateMaxScore(items) {
  return items.reduce((total, item) => {
    return total + (5 * Number(item.weighting));
  }, 0);
}

export function calculateReadinessPercentage(items) {
  const total = calculateTotalScore(items);
  const max = calculateMaxScore(items);

  return max === 0 ? 0 : Math.round((total / max) * 100);
}
