/**
 * Secure HTTP Client for FBR Invoice Cloud Desktop Application
 * Supports dynamic hosted API base URL, automatic token attachment,
 * and token rotation recovery.
 */

export function getApiBaseUrl(): string {
  // 1. Check user/admin configured API endpoint
  const customUrl = localStorage.getItem('fbr_api_endpoint');
  if (customUrl && customUrl.trim().length > 0) {
    return customUrl.trim().replace(/\/+$/, '');
  }

  // 2. Check Vite environment variable
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, '');
  }

  // 3. In web development with proxy, use empty relative path; in desktop, default to local/hosted fallback
  if (typeof window !== 'undefined' && window.location.protocol.startsWith('http') && !window.location.hostname.includes('tauri')) {
    return '';
  }

  return 'http://127.0.0.1:8000';
}

export function setApiBaseUrl(url: string): void {
  const cleanUrl = url.trim().replace(/\/+$/, '');
  localStorage.setItem('fbr_api_endpoint', cleanUrl);
}

let isRefreshing = false;

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const fullUrl = `${baseUrl}/api/v1${cleanEndpoint}`;

  const response = await fetch(fullUrl, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // Attempt automatic refresh token rotation once
    const refreshToken = localStorage.getItem('refresh_token');
    const deviceFingerprint = localStorage.getItem('fbr_hw_fingerprint');

    if (refreshToken && deviceFingerprint && !isRefreshing && !endpoint.includes('/auth/refresh') && !endpoint.includes('/activation/')) {
      isRefreshing = true;
      try {
        const refreshResp = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            refresh_token: refreshToken,
            device_fingerprint: deviceFingerprint,
          }),
        });

        if (refreshResp.ok) {
          const refreshData = await refreshResp.json();
          localStorage.setItem('token', refreshData.access_token);
          localStorage.setItem('refresh_token', refreshData.refresh_token);
          isRefreshing = false;

          // Retry original request with newly rotated token
          headers['Authorization'] = `Bearer ${refreshData.access_token}`;
          const retryResp = await fetch(fullUrl, {
            ...options,
            headers,
          });
          if (retryResp.ok) {
            return retryResp.json();
          }
        }
      } catch {
        // Refresh failed, proceed to logout
      } finally {
        isRefreshing = false;
      }
    }

    // Session expired or invalid
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    throw new Error('Authentication expired. Please activate your device or log in again.');
  }

  if (!response.ok) {
    let errorMsg = `API Error (${response.status}): ${response.statusText}`;
    try {
      const errData = await response.json();
      if (errData && errData.detail) {
        errorMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      } else if (errData && errData.error && errData.error.message) {
        errorMsg = errData.error.message;
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorMsg);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}


/** Authenticated image transport for protected invoice QR endpoints. */
export async function apiFetchImage(endpoint: string): Promise<Blob> {
  const token = localStorage.getItem('token');
  if (!token) throw new Error('Sign in to view an invoice QR code');
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const response = await fetch(`${getApiBaseUrl()}/api/v1${cleanEndpoint}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'image/png' },
    cache: 'no-store',
  });
  if (!response.ok) {
    let message = `QR request failed (HTTP ${response.status})`;
    try {
      const result = await response.json();
      if (typeof result.detail === 'string') message = result.detail;
    } catch { /* May not be JSON. */ }
    throw new Error(message);
  }
  const image = await response.blob();
  if (!image.type.startsWith('image/')) throw new Error('QR endpoint returned non-image content');
  return image;
}
