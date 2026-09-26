const test = require('node:test');
const assert = require('node:assert/strict');
const { parseCompilerDiagnostics } = require('../out/compilerDiagnostics');

test('parses canonical compiler errors with Windows paths and source positions', () => {
  const parsed = parseCompilerDiagnostics(
    'sotlas: erro: C:\\work tree\\main.sotlas:12:4: unknown name: value\n  value\n  ^'
  );
  assert.deepEqual(parsed, [{
    file: 'C:\\work tree\\main.sotlas',
    line: 12,
    column: 4,
    message: 'unknown name: value',
    severity: 'error'
  }]);
});

test('skips compiler output without a source location', () => {
  assert.deepEqual(parseCompilerDiagnostics('sotlas: erro: file not found'), []);
});

test('parses more than one diagnostic from mixed output', () => {
  const parsed = parseCompilerDiagnostics([
    'noise from compiler',
    'sotlas: erro: /tmp/main.sotlas:2:1: invalid type',
    'sotlas: warning: /tmp/main.sotlas:5:9: unused value'
  ].join('\n'));
  assert.equal(parsed.length, 2);
  assert.equal(parsed[0].severity, 'error');
  assert.equal(parsed[1].severity, 'warning');
  assert.equal(parsed[1].line, 5);
});
