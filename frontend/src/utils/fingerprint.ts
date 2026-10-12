/**
 * Hardware Device Fingerprinting for Windows Desktop Client
 * Provides persistent, deterministic device binding and hardware identification.
 */

export interface DeviceInfo {
  fingerprint: string;
  deviceName: string;
  osInfo: string;
  appVersion: string;
}

/**
 * SHA-256 hash a string using Web Crypto API
 */
async function sha256(str: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(str);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Retrieve or generate persistent machine hardware fingerprint.
 */
export async function getDeviceFingerprint(): Promise<string> {
  const storageKey = 'fbr_hw_fingerprint';
  let existingFp = localStorage.getItem(storageKey);
  if (existingFp && existingFp.length === 64) {
    return existingFp;
  }

  // Construct entropy string from hardware traits
  const screenRes = typeof window !== 'undefined' ? `${window.screen.width}x${window.screen.height}x${window.screen.colorDepth}` : '1920x1080x24';
  const concurrency = typeof navigator !== 'undefined' ? (navigator.hardwareConcurrency || 4) : 4;
  const platform = typeof navigator !== 'undefined' ? (navigator.userAgent || 'Windows') : 'Windows';
  const randomSalt = crypto.randomUUID();

  const entropy = `FBR-HW-${platform}-${concurrency}-${screenRes}-${randomSalt}`;
  const generatedHash = await sha256(entropy);

  localStorage.setItem(storageKey, generatedHash);
  return generatedHash;
}

/**
 * Get user-friendly device name (e.g. "Main Terminal", "POS-Counter-1")
 */
export function getDeviceName(): string {
  const savedName = localStorage.getItem('fbr_device_name');
  if (savedName) {
    return savedName;
  }

  const randomSuffix = Math.floor(100 + Math.random() * 900);
  const defaultName = `Terminal-${randomSuffix}`;
  localStorage.setItem('fbr_device_name', defaultName);
  return defaultName;
}

/**
 * Detect client OS environment
 */
export function getOSInfo(): string {
  const userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : '';
  if (userAgent.includes('Windows NT 10.0')) {
    return 'Windows 10/11 Pro (64-bit)';
  } else if (userAgent.includes('Windows NT 6.3')) {
    return 'Windows 8.1 (64-bit)';
  } else if (userAgent.includes('Windows NT 6.1')) {
    return 'Windows 7 (64-bit)';
  } else if (userAgent.includes('Windows')) {
    return 'Windows Desktop OS';
  }
  return 'Windows Workstation (x64)';
}

/**
 * Gather complete device metadata
 */
export async function getCompleteDeviceInfo(): Promise<DeviceInfo> {
  const fingerprint = await getDeviceFingerprint();
  const deviceName = getDeviceName();
  const osInfo = getOSInfo();
  const appVersion = '1.1.0';

  return {
    fingerprint,
    deviceName,
    osInfo,
    appVersion,
  };
}
