import React, { useEffect, useState } from 'react';
import { Settings, ShieldCheck, CheckCircle2, RefreshCw, Save, Server, Building2 } from 'lucide-react';
import { masterApi } from '../api/master';
import { fbrApi } from '../api/fbr';
import { Organization } from '../types';

export const SettingsPage: React.FC = () => {
  const [org, setOrg] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<{ message: string; success: boolean; latency_ms?: number; adapter?: string } | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);

  // Editable settings
  const [fbrMode, setFbrMode] = useState<'DEMO' | 'SANDBOX' | 'PRODUCTION'>('DEMO');
  const [fbrPosId, setFbrPosId] = useState('');
  const [fbrApiToken, setFbrApiToken] = useState('');
  const [fbrBaseUrl, setFbrBaseUrl] = useState('');
  const [invoicePrefix, setInvoicePrefix] = useState('INV');
  const [nextInvoiceNumber, setNextInvoiceNumber] = useState(1001);
  const [defaultTerms, setDefaultTerms] = useState('');

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const data = await masterApi.getOrganization();
      setOrg(data);
      if (data.settings) {
        setFbrMode(data.settings.fbr_mode);
        setFbrPosId(data.settings.fbr_pos_id || '');
        setFbrApiToken(''); // Never repopulate a saved bearer token in the UI.
        setFbrBaseUrl(data.settings.fbr_base_url || '');
        setInvoicePrefix(data.settings.invoice_prefix);
        setNextInvoiceNumber(data.settings.next_invoice_number);
        setDefaultTerms(data.settings.default_terms || '');
      }
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await masterApi.updateSettings({
        fbr_mode: fbrMode,
        fbr_pos_id: fbrPosId || null,
        fbr_api_token: fbrApiToken.trim() || undefined,
        fbr_base_url: fbrBaseUrl || null,
        invoice_prefix: invoicePrefix,
        next_invoice_number: nextInvoiceNumber,
        default_terms: defaultTerms,
      });
      alert('Settings saved. Use Verify PRAL Token to confirm authenticated reference-API access before invoicing.');
      await fetchSettings();
    } catch (err: any) {
      alert(`Failed to save settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    try {
      const res = await fbrApi.testConnection();
      setTestResult({
        message: res.message,
        success: res.success,
        latency_ms: res.latency_ms,
        adapter: res.details?.adapter || res.environment,
      });
      setTimeout(() => setTestResult(null), 8000);
    } catch (err: any) {
      setTestResult({
        message: `Connection failed: ${err.message}`,
        success: false,
      });
    } finally {
      setTestingConnection(false);
    }
  };

  if (loading) {
    return <div className="p-12 text-center text-xs text-slate-500">Loading settings...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Integration & System Settings</h2>
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full">
              TENANT ISOLATED
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Configure FBR integration adapters, invoice numbering sequence, and organization compliance profile.
          </p>
        </div>

        <button
          onClick={handleTestConnection}
          disabled={testingConnection}
          className="flex items-center gap-2 px-3 py-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700 transition-colors disabled:opacity-50"
        >
          <Server className="w-4 h-4 text-emerald-600" />
          <span>{testingConnection ? 'Checking token...' : 'Verify PRAL Token'}</span>
        </button>
      </div>

      {testResult && (
        <div className={`p-4 border text-xs font-semibold rounded-xl flex items-center justify-between gap-3 ${
          testResult.success
            ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
            : 'bg-rose-50 border-rose-200 text-rose-900'
        }`}>
          <div className="flex items-center gap-2">
            {testResult.success ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            ) : (
              <ShieldCheck className="w-5 h-5 text-rose-600 flex-shrink-0" />
            )}
            <div>
              <p className="font-bold">{testResult.message}</p>
              {testResult.adapter && (
                <p className="text-[11px] opacity-80 mt-0.5">Adapter: <span className="font-mono">{testResult.adapter}</span></p>
              )}
            </div>
          </div>
          {testResult.latency_ms !== undefined && (
            <span className="px-2 py-1 bg-white/80 rounded font-mono text-[11px] border border-slate-200">
              {testResult.latency_ms} ms
            </span>
          )}
        </div>
      )}

      <form onSubmit={handleSaveSettings} className="space-y-6">
        {/* FBR Gateway Configuration Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
              <h3 className="font-bold text-sm text-slate-900">FBR Digital Invoicing Gateway Integration</h3>
            </div>
            <span className={`px-2.5 py-1 text-[11px] font-bold rounded-full ${
              fbrMode === 'PRODUCTION'
                ? 'bg-rose-100 text-rose-800 border border-rose-200'
                : fbrMode === 'SANDBOX'
                ? 'bg-amber-100 text-amber-800 border border-amber-200'
                : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
            }`}>
              {fbrMode} MODE
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Integration Mode / Environment</label>
              <select
                value={fbrMode}
                onChange={(e) => setFbrMode(e.target.value as any)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white font-semibold text-slate-800"
              >
                <option value="DEMO">DEMO / MOCK (Local development & testing simulator)</option>
                <option value="SANDBOX">SANDBOX (FBR / Licensed Integrator Test Environment)</option>
                <option value="PRODUCTION">PRODUCTION (Authorized PRAL / Licensed Integrator Gateway)</option>
              </select>
              <p className="text-[11px] text-slate-400 mt-1">
                {fbrMode === 'DEMO' && 'Simulates fiscal validation, timeout retries, and QR code generation without live tax tokens.'}
                {fbrMode === 'SANDBOX' && 'Official FBR staging gateway for IRIS schema certification and POS ID verification.'}
                {fbrMode === 'PRODUCTION' && 'Live PRAL / Licensed Integrator gateway. Transmits irreversible legal fiscal records.'}
              </p>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Default Terms & Conditions</label>
              <textarea
                rows={3}
                value={defaultTerms}
                onChange={(e) => setDefaultTerms(e.target.value)}
                placeholder="Payment due within 30 days..."
                className="w-full px-3 py-2 border border-slate-200 rounded-lg"
              />
            </div>
          </div>

          {/* FBR Credentials Section */}
          <div className="mt-4 pt-4 border-t border-slate-100">
            <h4 className="font-semibold text-xs text-slate-800 mb-3">FBR POS & API Gateway Credentials</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  FBR POS ID {fbrMode !== 'DEMO' && <span className="text-rose-500">*</span>}
                </label>
                <input
                  type="text"
                  placeholder="e.g. POS-987654"
                  value={fbrPosId}
                  onChange={(e) => setFbrPosId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono text-slate-800"
                />
                <p className="text-[10px] text-slate-400 mt-1">POS identifier registered in FBR IRIS portal</p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  API Bearer Token {fbrMode !== 'DEMO' && <span className="text-rose-500">*</span>}
                </label>
                <input
                  type="password"
                  placeholder="Enter new token (leave blank to keep saved token)"
                  value={fbrApiToken}
                  onChange={(e) => setFbrApiToken(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono text-slate-800"
                />
                <p className="text-[10px] text-slate-400 mt-1">Stored encrypted server-side. Save settings, then verify token. A successful reference lookup does not guarantee invoice acceptance.</p>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Custom Gateway URL (Optional)</label>
                <input
                  type="url"
                  placeholder="https://gw.fbr.gov.pk"
                  value={fbrBaseUrl}
                  onChange={(e) => setFbrBaseUrl(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono text-slate-800"
                />
                <p className="text-[10px] text-slate-400 mt-1">Overrides default PRAL gateway endpoint</p>
              </div>
            </div>
          </div>
        </div>

        {/* Invoice Numbering Sequence Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Settings className="w-5 h-5 text-slate-600" />
            <h3 className="font-bold text-sm text-slate-900">Invoice Numbering & Series</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Invoice Prefix</label>
              <input
                type="text"
                value={invoicePrefix}
                onChange={(e) => setInvoicePrefix(e.target.value.toUpperCase())}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono uppercase"
              />
              <p className="text-[11px] text-slate-400 mt-1">Generated format: {invoicePrefix}-BRANCH-YEAR-SEQ</p>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Next Invoice Sequence Number</label>
              <input
                type="number"
                min="1"
                value={nextInvoiceNumber}
                onChange={(e) => setNextInvoiceNumber(parseInt(e.target.value) || 1)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono font-medium"
              />
              <p className="text-[11px] text-slate-400 mt-1">Server-side atomic counter protects against duplicates.</p>
            </div>
          </div>
        </div>

        {/* Taxpayer Information Summary */}
        {org?.taxpayer && (
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3 text-xs">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Building2 className="w-5 h-5 text-slate-600" />
              <h3 className="font-bold text-sm text-slate-900">Taxpayer Registration Profile (Immutable Core)</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-1">
              <div>
                <span className="text-slate-400">Legal Name:</span>
                <div className="font-bold text-slate-800 mt-0.5">{org.taxpayer.legal_name}</div>
              </div>
              <div>
                <span className="text-slate-400">National Tax # (NTN):</span>
                <div className="font-mono font-bold text-emerald-700 mt-0.5">{org.taxpayer.ntn}</div>
              </div>
              <div>
                <span className="text-slate-400">STRN:</span>
                <div className="font-mono font-bold text-slate-800 mt-0.5">{org.taxpayer.strn || 'N/A'}</div>
              </div>
              <div>
                <span className="text-slate-400">Jurisdiction:</span>
                <div className="font-bold text-slate-800 mt-0.5">{org.taxpayer.city}, {org.taxpayer.province}</div>
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-sm shadow-emerald-200 transition-colors disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save Settings'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
