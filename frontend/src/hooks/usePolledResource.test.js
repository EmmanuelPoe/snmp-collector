import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { usePolledResource } from './usePolledResource';

function Probe({ id, fetcher, interval = 1000 }) {
  const { data, error } = usePolledResource('probe', fetcher, { intervalMs: interval });
  return (
    <div data-testid={id}>
      {data ?? 'none'}|{error ? 'err' : 'ok'}
    </div>
  );
}

function setHidden(hidden) {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
  document.dispatchEvent(new Event('visibilitychange'));
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => {
  setHidden(false);
  jest.useRealTimers();
});

test('subscribers share one request per interval', async () => {
  const fetcher = jest.fn().mockResolvedValue('v');
  render(
    <>
      <Probe id="a" fetcher={fetcher} />
      <Probe id="b" fetcher={fetcher} />
    </>,
  );
  await act(async () => {});
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId('a')).toHaveTextContent('v|ok');
  expect(screen.getByTestId('b')).toHaveTextContent('v|ok');

  await act(async () => {
    jest.advanceTimersByTime(1000);
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

test('pauses while the tab is hidden and catches up when it returns', async () => {
  const fetcher = jest.fn().mockResolvedValue('v');
  render(<Probe id="a" fetcher={fetcher} />);
  await act(async () => {});
  expect(fetcher).toHaveBeenCalledTimes(1);

  setHidden(true);
  await act(async () => {
    jest.advanceTimersByTime(10000);
  });
  expect(fetcher).toHaveBeenCalledTimes(1);

  await act(async () => {
    setHidden(false);
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

test('backs off exponentially after failures and recovers on success', async () => {
  const fetcher = jest.fn().mockRejectedValue(new Error('boom'));
  render(<Probe id="a" fetcher={fetcher} />);
  await act(async () => {});
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId('a')).toHaveTextContent('none|err');

  // 1 failure -> next attempt after 2x the interval, not 1x.
  await act(async () => {
    jest.advanceTimersByTime(1000);
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
  fetcher.mockResolvedValue('back');
  await act(async () => {
    jest.advanceTimersByTime(1000);
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(screen.getByTestId('a')).toHaveTextContent('back|ok');
});

test('stops polling once the last subscriber unmounts', async () => {
  const fetcher = jest.fn().mockResolvedValue('v');
  const { unmount } = render(<Probe id="a" fetcher={fetcher} />);
  await act(async () => {});
  unmount();
  await act(async () => {
    jest.advanceTimersByTime(60000);
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test('a new key does not keep showing the previous key data', async () => {
  function KeyProbe({ k, fetcher }) {
    const { data } = usePolledResource(k, fetcher);
    return <div data-testid="k">{data ?? 'none'}</div>;
  }
  const slow = new Promise(() => {});
  const { rerender } = render(<KeyProbe k="one" fetcher={() => Promise.resolve('one-data')} />);
  await act(async () => {});
  expect(screen.getByTestId('k')).toHaveTextContent('one-data');

  rerender(<KeyProbe k="two" fetcher={() => slow} />);
  await act(async () => {});
  expect(screen.getByTestId('k')).toHaveTextContent('none');
});
