import '@testing-library/jest-dom';

// recharts' ResponsiveContainer measures the DOM; jsdom has no layout, so give
// it a harmless ResizeObserver stub.
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
