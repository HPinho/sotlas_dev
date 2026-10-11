const dns = require('node:dns');
const net = require('node:net');
const { setTimeout: delay } = require('node:timers/promises');
const { version: pinnedVersion } = require('./vscode-version.json');

const transientCodes = new Set([
  'ETIMEDOUT', 'ENETUNREACH', 'EHOSTUNREACH', 'ECONNRESET',
  'ECONNREFUSED', 'EAI_AGAIN', 'ENOTFOUND', 'EPIPE',
]);

function isTransientNetworkError(error, visited = new Set()) {
  if (!error || typeof error !== 'object' || visited.has(error)) return false;
  visited.add(error);
  if (Array.isArray(error.errors) && error.errors.length > 0) {
    return error.errors.every(item => isTransientNetworkError(item, new Set(visited)));
  }
  if (transientCodes.has(error.code)) return true;
  if (/^@vscode\/test-electron request timeout/.test(error.message || '')) return true;
  return isTransientNetworkError(error.cause, visited);
}

function downloadOptions(cachePath, version = pinnedVersion) {
  if (!/^\d+\.\d+\.\d+$/.test(version)) {
    throw new Error('VS Code smoke tests require an exact release version');
  }
  return { version, cachePath, timeout: 120000 };
}

function configureDownloadNetwork() {
  // Keep IPv6 available, but prefer reachable IPv4 on hosted CI runners.
  dns.setDefaultResultOrder('ipv4first');
  if (typeof net.setDefaultAutoSelectFamilyAttemptTimeout === 'function') {
    net.setDefaultAutoSelectFamilyAttemptTimeout(1000);
  }
}

async function downloadWithRetry(download, options, {
  sleep = delay,
  report = message => console.warn(message),
} = {}) {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      return await download(options);
    } catch (error) {
      if (attempt === 3 || !isTransientNetworkError(error)) throw error;
      const waitMs = attempt * 2000;
      report(`VS Code ${options.version}: transient download failure; retry ${attempt + 1}/3 in ${waitMs}ms`);
      await sleep(waitMs);
    }
  }
}

module.exports = { downloadOptions, downloadWithRetry, configureDownloadNetwork, isTransientNetworkError };
