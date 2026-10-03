import axios from 'axios';

jest.mock('axios', () => {
  const instance = {
    get: jest.fn(),
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
  };
  return { create: () => instance, __instance: instance };
});

const { getDevices, getAlertsPage } = require('./api');
const http = axios.__instance;

const page = (n, total, start = 0) => ({
  data: Array.from({ length: n }, (_, i) => ({ id: start + i })),
  headers: { 'x-total-count': String(total) },
});

beforeEach(() => http.get.mockReset());

test('getDevices walks every page so fleets above one page are not truncated', async () => {
  http.get
    .mockResolvedValueOnce(page(1000, 2300))
    .mockResolvedValueOnce(page(1000, 2300, 1000))
    .mockResolvedValueOnce(page(300, 2300, 2000));

  const devices = await getDevices();

  expect(devices).toHaveLength(2300);
  expect(http.get.mock.calls.map((c) => c[1].params.skip)).toEqual([0, 1000, 2000]);
});

test('getDevices stops after one request when everything fits', async () => {
  http.get.mockResolvedValueOnce(page(12, 12));
  expect(await getDevices(true)).toHaveLength(12);
  expect(http.get).toHaveBeenCalledTimes(1);
  expect(http.get.mock.calls[0][1].params.enabled_only).toBe(true);
});

test('getDevices stops on an exact page boundary', async () => {
  http.get.mockResolvedValueOnce(page(1000, 1000));
  expect(await getDevices()).toHaveLength(1000);
  expect(http.get).toHaveBeenCalledTimes(1);
});

test('getAlertsPage returns the items and the total', async () => {
  http.get.mockResolvedValueOnce(page(2, 57));
  expect(await getAlertsPage({ limit: 2 })).toEqual({ items: [{ id: 0 }, { id: 1 }], total: 57 });
});
