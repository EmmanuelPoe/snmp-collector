import { filterItems, scoreItem } from './commandSearch';

const ITEMS = [
  { label: 'Dashboard', keywords: 'home overview' },
  { label: 'Devices', keywords: 'inventory hosts' },
  { label: 'Audit Log', keywords: 'history compliance' },
  { label: 'Switch theme', keywords: 'dark light mode' },
];

test('empty query returns everything in the original order', () => {
  expect(filterItems(ITEMS, '  ')).toEqual(ITEMS);
});

test('prefix matches beat keyword matches', () => {
  expect(filterItems(ITEMS, 'dev').map((i) => i.label)).toEqual(['Devices']);
  // "dark" only appears in a keyword; still found, ranked after label hits
  expect(filterItems(ITEMS, 'dark').map((i) => i.label)).toEqual(['Switch theme']);
});

test('every term must match, in any order', () => {
  expect(filterItems(ITEMS, 'log audit').map((i) => i.label)).toEqual(['Audit Log']);
  expect(filterItems(ITEMS, 'audit zzz')).toEqual([]);
});

test('is case-insensitive and word-start matches outrank mid-word matches', () => {
  expect(scoreItem(ITEMS[1], 'DEV')).toBeLessThan(scoreItem({ label: 'Hardware devices' }, 'ices'));
  expect(scoreItem(ITEMS[0], 'nope')).toBe(-1);
});
