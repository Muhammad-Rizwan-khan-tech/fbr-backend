import React, { useState } from 'react';
import { ShieldCheck, Key, Laptop, Server, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getDeviceName } from '../utils/fingerprint';
import { getApiBaseUrl } from '../api/client';

interface ActivationPageProps {
  onSwitchToLogin?: () => void;
}

export const ActivationPage: React.FC<ActivationPageProps> = ({ onSwitchToLogin }) => {
  const { activate, updateApiEndpoint } = useAuth();

  const [activationKey, setActivationKey] = useState<string>('');
  const [deviceName, setDeviceName] = useState<string>(getDeviceName());
  const [apiEndpoint, setApiEndpoint] = useState<string>(getApiBaseUrl() || 'http://127.0.0.1:8000');
  const [showConfig, setShowConfig] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isTestingConnection, setIsTestingConnection] = useState<boolean>(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connected' | 'failed'>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<any | null>(null);

  // Auto-format key with uppercase if user pastes raw text
  const handleKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.toUpperCase();
    setActivationKey(val);
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setConnectionStatus('idle');
    try {
      const cleanUrl = apiEndpoint.replace(/\/+$/, '');
      const resp = await fetch(`${cleanUrl}/api/v1/health`, { method: 'GET' });
      if (resp.ok) {
        setConnectionStatus('connected');
        updateApiEndpoint(cleanUrl);
      } else {
        setConnectionStatus('failed');
      }
    } catch {
      setConnectionStatus('failed');
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activationKey.trim()) {
      setErrorMsg('Please enter your activation secret key.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      updateApiEndpoint(apiEndpoint);
      const res = await activate(activationKey.trim(), deviceName.trim());
      setSuccessData(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Activation failed. Please check the key or contact your administrator.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-slate-100 antialiased selection:bg-sky-500 selection:text-white">
      <div className="max-w-md w-full space-y-6">
        {/* Logo & Branding */}
        <div className="text-center space-y-2">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-extrabold text-2xl mx-auto shadow-lg shadow-emerald-500/10">
            F
          </div>
          <h1 className="text-2xl font-black text-white tracking-tight">FBR INVOICE CLOUD</h1>
          <p className="text-xs text-slate-400 font-medium">Windows Desktop SaaS &bull; Digital Tax Invoicing</p>
        </div>

        {/* Main Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6 relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-sky-500 to-indigo-500"></div>

          {successData ? (
            /* Activation Success State */
            <div className="text-center space-y-5 py-4">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center mx-auto animate-bounce">
                <CheckCircle2 className="w-10 h-10" />
              </div>

              <div className="space-y-1">
                <h2 className="text-lg font-bold text-white">Workstation Successfully Activated!</h2>
                <p className="text-xs text-emerald-400 font-semibold">Permanent License Verified & Hardware Bound</p>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 rounded-2xl p-4 text-left text-xs space-y-2 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-400">Organization:</span>
                  <span className="text-white font-sans font-bold">{successData.organization.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Permanent License:</span>
                  <span className="text-emerald-400 font-bold">{successData.license.license_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Policy:</span>
                  <span className="text-white font-sans">No Subscription Expiry</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Terminal Bound:</span>
                  <span className="text-white">{deviceName}</span>
                </div>
              </div>

              <button
                onClick={() => window.location.reload()}
                className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs tracking-wide transition-colors shadow-lg shadow-emerald-600/20"
              >
                Launch Invoicing Dashboard &rarr;
              </button>
            </div>
          ) : (
            /* Activation Key Input Form */
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-1">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Key className="w-4 h-4 text-sky-400" />
                  <span>Activate Desktop Terminal</span>
                </h2>
                <p className="text-xs text-slate-400">
                  Enter the unique activation key provided by your system administrator to unlock your organization's permanent license.
                </p>
              </div>

              {errorMsg && (
                <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Activation Secret Key</label>
                <div className="relative">
                  <input
                    type="text"
                    value={activationKey}
                    onChange={handleKeyChange}
                    placeholder="ACT-XXXX-XXXX-XXXX-XXXX"
                    required
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-emerald-400 font-mono tracking-wider placeholder-slate-600 focus:outline-none focus:border-sky-500 transition-colors uppercase font-bold"
                  />
                </div>
                <span className="text-[11px] text-slate-500 block">One-time redeemable secret issued by the platform super admin.</span>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Laptop className="w-3.5 h-3.5 text-slate-400" />
                  <span>Terminal / Workstation Name</span>
                </label>
                <input
                  type="text"
                  value={deviceName}
                  onChange={(e) => setDeviceName(e.target.value)}
                  placeholder="e.g. Counter 1 Terminal"
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500 transition-colors"
                />
              </div>

              {/* Central Backend API Server Configuration Accordion */}
              <div className="border border-slate-800 rounded-xl p-3 bg-slate-950/40 text-xs">
                <button
                  type="button"
                  onClick={() => setShowConfig(!showConfig)}
                  className="w-full flex items-center justify-between text-slate-400 hover:text-slate-200 transition-colors font-medium text-[11px]"
                >
                  <span className="flex items-center gap-1.5">
                    <Server className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Backend Server: <strong className="text-slate-300 font-mono">{apiEndpoint}</strong></span>
                  </span>
                  <span>{showConfig ? 'Hide' : 'Configure'}</span>
                </button>

                {showConfig && (
                  <div className="mt-3 pt-3 border-t border-slate-800 space-y-2.5">
                    <div className="space-y-1">
                      <label className="text-[11px] text-slate-400">Central Hosted API URL</label>
                      <input
                        type="url"
                        value={apiEndpoint}
                        onChange={(e) => setApiEndpoint(e.target.value)}
                        placeholder="https://api.example.com"
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-sky-500"
                      />
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <button
                        type="button"
                        onClick={handleTestConnection}
                        disabled={isTestingConnection}
                        className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-semibold flex items-center gap-1.5 transition-colors"
                      >
                        {isTestingConnection ? <RefreshCw className="w-3 h-3 animate-spin" /> : null}
                        <span>Test Backend Connection</span>
                      </button>

                      {connectionStatus === 'connected' && (
                        <span className="text-[11px] font-semibold text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Online
                        </span>
                      )}

                      {connectionStatus === 'failed' && (
                        <span className="text-[11px] font-semibold text-rose-400 flex items-center gap-1">
                          <AlertCircle className="w-3.5 h-3.5" /> Unreachable
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-bold text-xs tracking-wide transition-colors shadow-lg shadow-sky-600/20 flex items-center justify-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Verifying Activation Key...</span>
                  </>
                ) : (
                  <span>Activate & Unlock Application</span>
                )}
              </button>
            </form>
          )}

          {onSwitchToLogin && !successData && (
            <div className="pt-2 border-t border-slate-800 text-center">
              <button
                type="button"
                onClick={onSwitchToLogin}
                className="text-xs text-slate-400 hover:text-sky-400 transition-colors"
              >
                Already activated on this terminal? <span className="underline">Sign in with credentials</span>
              </button>
            </div>
          )}
        </div>

        {/* Security & Legal Policy Footer */}
        <div className="text-center text-[11px] text-slate-500 space-y-1">
          <p className="flex items-center justify-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
            <span>FBR SRO compliant &bull; SHA-256 Hardware Fingerprint Binding</span>
          </p>
          <p>Protected by permanent license terms. No automatic subscription expiration.</p>
        </div>
      </div>
    </div>
  );
};
