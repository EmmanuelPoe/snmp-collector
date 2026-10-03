import React from 'react';
import { render, screen } from '@testing-library/react';
import HealthBar from './HealthBar';

const SEGMENTS = [
  { label: 'Up', count: 1895, color: 'green' },
  { label: 'Degraded', count: 41, color: 'orange' },
  { label: 'Down', count: 24, color: 'red' },
  { label: 'Disabled', count: 0, color: 'grey' },
];

test('lists exact counts and percentages and describes itself for screen readers', () => {
  render(<HealthBar segments={SEGMENTS} />);
  expect(screen.getByRole('img')).toHaveAccessibleName(
    '1,895 up, 41 degraded, 24 down, 0 disabled',
  );
  expect(screen.getByText('1,895')).toBeInTheDocument();
  expect(screen.getByText('96.7%')).toBeInTheDocument();
});

test('small non-zero segments stay visible and zero segments are omitted', () => {
  const { container } = render(<HealthBar segments={SEGMENTS} />);
  const widths = [...container.querySelectorAll('.health-bar-segment')].map((el) =>
    parseFloat(el.style.flexBasis),
  );
  expect(widths).toHaveLength(3);
  expect(Math.min(...widths)).toBeGreaterThanOrEqual(1.4);
  // Bases sum to 100% so no segment overflows (and gets clipped) in the flex row.
  expect(widths.reduce((n, w) => n + w, 0)).toBeCloseTo(100, 5);
});

test('renders an empty state without dividing by zero', () => {
  render(<HealthBar segments={SEGMENTS.map((s) => ({ ...s, count: 0 }))} />);
  expect(screen.getByRole('img')).toHaveAccessibleName('No devices');
  expect(screen.getAllByText('—')).toHaveLength(4);
});
