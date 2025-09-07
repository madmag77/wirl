export function startPolling(callback, interval) {
  return setInterval(callback, interval);
}
