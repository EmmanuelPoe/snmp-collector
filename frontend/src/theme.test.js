import fs from 'fs';
import path from 'path';

// The dark palette is declared twice (OS preference vs explicit choice) because
// plain CSS can't share one rule between a media query and an attribute
// selector. These checks keep the copies from drifting apart or going stale
// relative to the light palette.
const css = fs.readFileSync(path.join(__dirname, 'index.css'), 'utf8');

function block(text, marker) {
  const start = text.indexOf(marker);
  if (start < 0) throw new Error(`missing: ${marker}`);
  const open = text.indexOf('{', start);
  let depth = 0;
  for (let i = open; i < text.length; i++) {
    if (text[i] === '{') depth++;
    if (text[i] === '}' && --depth === 0) return text.slice(open + 1, i);
  }
  throw new Error(`unterminated: ${marker}`);
}

const decls = (body) =>
  [...body.matchAll(/(--[\w-]+|color-scheme)\s*:\s*([^;]+);/g)].map(
    (m) => `${m[1]}: ${m[2].trim()}`,
  );
const names = (list) => list.map((d) => d.split(':')[0]);

const light = decls(block(css, ':root {'));
const systemDark = decls(
  block(block(css, '@media (prefers-color-scheme: dark)'), ":root:not([data-theme='light'])"),
);
const explicitDark = decls(block(css, ":root[data-theme='dark']"));

test('system-dark and explicit-dark palettes are identical', () => {
  expect([...systemDark].sort()).toEqual([...explicitDark].sort());
});

test('dark palette overrides every colour and chart token the light palette defines', () => {
  const themed = names(light).filter((n) => /^--(color|chart|shadow)-/.test(n));
  const dark = new Set(names(explicitDark));
  expect(themed.filter((n) => !dark.has(n))).toEqual([]);
});

test('every var(--token) used in the app is defined', () => {
  const defined = new Set([...css.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
  const app = fs.readFileSync(path.join(__dirname, 'App.css'), 'utf8');
  [...app.matchAll(/(--[\w-]+)\s*:/g)].forEach((m) => defined.add(m[1]));

  const missing = new Set();
  const walk = (dir) =>
    fs.readdirSync(dir, { withFileTypes: true }).forEach((e) => {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) return walk(p);
      if (!/\.(js|css)$/.test(e.name) || /\.test\.js$/.test(e.name)) return;
      [...fs.readFileSync(p, 'utf8').matchAll(/var\((--[\w-]+)/g)].forEach(
        (m) => defined.has(m[1]) || missing.add(`${m[1]} (${path.relative(__dirname, p)})`),
      );
    });
  walk(__dirname);
  // utils/cssVar.js and its callers use names via cssVar('--x'), not var().
  expect([...missing].filter((m) => !m.startsWith('--x '))).toEqual([]);
});
