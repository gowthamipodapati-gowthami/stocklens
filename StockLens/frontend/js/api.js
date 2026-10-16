/** HTTP-only frontend boundary: database credentials and ORM stay on the server. */
async function request(path) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(path, { headers: { 'Accept': 'application/json' }, signal: controller.signal });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
    return payload;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request timed out. Try again or use DEMO.');
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
export const fetchSymbols = () => request('/api/symbols');
export const fetchDashboard = (symbol, period, refresh = false) => request(`/api/stocks/${encodeURIComponent(symbol)}/dashboard?period=${encodeURIComponent(period)}${refresh ? '&refresh=true' : ''}`);
export const fetchForecast = (symbol, days) => request(`/api/stocks/${encodeURIComponent(symbol)}/forecast?days=${encodeURIComponent(days)}`);
