// Ranks palette entries against a query. Deliberately simple and predictable:
// every whitespace-separated term must match; earlier/prefix matches rank first.
export function scoreItem(item, query) {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return 0;
  const label = item.label.toLowerCase();
  const hay = `${label} ${(item.keywords || '').toLowerCase()}`;
  let score = 0;
  for (const term of terms) {
    const at = hay.indexOf(term);
    if (at < 0) return -1;
    // label hit beats keyword hit; word-start beats mid-word
    const inLabel = label.indexOf(term);
    const wordStart = at === 0 || hay[at - 1] === ' ';
    score += (inLabel === 0 ? 0 : inLabel > 0 ? 2 : 6) + (wordStart ? 0 : 3);
  }
  return score;
}

export function filterItems(items, query) {
  if (!query.trim()) return items;
  return items
    .map((item, i) => ({ item, i, score: scoreItem(item, query) }))
    .filter((r) => r.score >= 0)
    .sort((a, b) => a.score - b.score || a.i - b.i)
    .map((r) => r.item);
}
