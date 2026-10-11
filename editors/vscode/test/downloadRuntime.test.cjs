const assert = require('node:assert/strict');
const test = require('node:test');
const { downloadOptions, downloadWithRetry, isTransientNetworkError } = require('./downloadRuntime.cjs');

function networkError(code) { return Object.assign(new Error(code), { code }); }

test('uses an exact release and a bounded request timeout', () => {
  assert.deepEqual(downloadOptions('/cache'), { version: '1.141.0', cachePath: '/cache', timeout: 120000 });
  for (const moving of ['stable', 'insiders', '', '1.141', '../cache']) {
    assert.throws(() => downloadOptions('/cache', moving), /exact release/);
  }
});

test('recognizes the failed CI aggregate and rejects mixed permanent errors', () => {
  assert.equal(isTransientNetworkError(new AggregateError([
    networkError('ETIMEDOUT'), networkError('ENETUNREACH'),
  ])), true);
  const mixed = new AggregateError([
    networkError('ETIMEDOUT'), new Error('checksum mismatch'),
  ]);
  mixed.code = 'ETIMEDOUT';
  assert.equal(isTransientNetworkError(mixed), false);
  assert.equal(isTransientNetworkError(Object.assign(new Error('wrapped'), { cause: networkError('EAI_AGAIN') })), true);
  const cycle = new Error('cycle');
  cycle.cause = cycle;
  assert.equal(isTransientNetworkError(cycle), false);
});

test('recovers from metadata connection failures with bounded backoff', async () => {
  const options = downloadOptions('/cache');
  const waits = [];
  let calls = 0;
  const executable = await downloadWithRetry(async actual => {
    assert.equal(actual, options);
    calls += 1;
    if (calls < 3) throw new AggregateError([networkError('ETIMEDOUT'), networkError('ENETUNREACH')]);
    return '/cache/Code';
  }, options, { sleep: async ms => waits.push(ms), report: () => {} });
  assert.equal(executable, '/cache/Code');
  assert.equal(calls, 3);
  assert.deepEqual(waits, [2000, 4000]);
});

test('preserves the failure after exhausting retries', async () => {
  const error = networkError('ECONNRESET');
  let calls = 0;
  await assert.rejects(downloadWithRetry(async () => {
    calls += 1;
    throw error;
  }, downloadOptions('/cache'), { sleep: async () => {}, report: () => {} }), actual => actual === error);
  assert.equal(calls, 3);
});

test('does not retry archive integrity, install or activation failures', async () => {
  for (const message of ['checksum mismatch', 'VSIX installation failed', 'diagnostic assertion failed']) {
    const error = new Error(message);
    let calls = 0;
    await assert.rejects(downloadWithRetry(async () => {
      calls += 1;
      throw error;
    }, downloadOptions('/cache'), { sleep: async () => assert.fail('unexpected retry'), report: () => {} }), actual => actual === error);
    assert.equal(calls, 1);
  }
});

test('a cached runtime succeeds without backoff', async () => {
  let calls = 0;
  await downloadWithRetry(async () => { calls += 1; return '/cache/Code'; }, downloadOptions('/cache'), {
    sleep: async () => assert.fail('unexpected retry'), report: () => assert.fail('unexpected retry'),
  });
  assert.equal(calls, 1);
});
