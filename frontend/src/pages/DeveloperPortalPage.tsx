import React, { useState, useEffect } from 'react';
import { 
  Code2, 
  Key, 
  Webhook, 
  Award, 
  ExternalLink, 
  Copy, 
  Check, 
  Play, 
  RefreshCw, 
  ShieldCheck, 
  AlertCircle,
  FileCode
} from 'lucide-react';
import { apiFetch } from '../api/client';

export const DeveloperPortalPage: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'erp' | 'keys' | 'webhooks' | 'cert'>('erp');
  const [erpLang, setErpLang] = useState<'curl' | 'python' | 'nodejs' | 'sap' | 'oracle' | 'odoo'>('curl');
  const [copied, setCopied] = useState<string | null>(null);

  // API Keys state
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [keyName, setKeyName] = useState('');
  const [keyEnv, setKeyEnv] = useState<'TEST' | 'LIVE'>('LIVE');
  const [newKeyResult, setNewKeyResult] = useState<string | null>(null);
  const [isLoadingKeys, setIsLoadingKeys] = useState(false);

  // Certification state
  const [certResult, setCertResult] = useState<any | null>(null);
  const [isCertRunning, setIsCertRunning] = useState(false);
  const [certMode, setCertMode] = useState<'SANDBOX' | 'PRODUCTION'>('SANDBOX');

  useEffect(() => {
    if (activeSubTab === 'keys') {
      loadKeys();
    }
  }, [activeSubTab]);

  const loadKeys = async () => {
    setIsLoadingKeys(true);
    try {
      const data = await apiFetch<any[]>('/developer/keys');
      setApiKeys(data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingKeys(false);
    }
  };

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyName) return;
    try {
      const data = await apiFetch<any>('/developer/keys', {
        method: 'POST',
        body: JSON.stringify({
          name: keyName,
          environment: keyEnv,
          scopes: ['invoices:read', 'invoices:write'],
        }),
      });
      setNewKeyResult(data.raw_api_key);
      setKeyName('');
      loadKeys();
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunCertification = async () => {
    setIsCertRunning(true);
    setCertResult(null);
    try {
      const data = await apiFetch<any>(`/fbr/certification/run?forced_adapter_mode=${certMode}`, {
        method: 'POST',
      });
      setCertResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsCertRunning(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const snippets: Record<string, string> = {
    curl: `curl -X POST "http://localhost:8000/api/v1/external/invoices" \\
  -H "X-API-Key: fbr_live_xxxxxxxxxxxxxxxxxxxxxx" \\
  -H "Content-Type: application/json" \\
  -d '{
    "branch_code": "KHI-01",
    "external_reference_id": "ERP-INV-1002",
    "buyer": {
      "name": "Standard Chartered Pakistan",
      "ntn": "1122334-5",
      "buyer_type": "REGISTERED_BUSINESS"
    },
    "items": [
      {
        "item_name": "Enterprise Software License",
        "hs_code": "8523.49.20",
        "uom": "NUM",
        "quantity": 2,
        "unit_price": 50000.0,
        "tax_rate": 18.0,
        "sale_type": "SERVICES"
      }
    ],
    "auto_submit_fbr": true
  }'`,
    python: `import requests

payload = {
    "branch_code": "KHI-01",
    "external_reference_id": "ERP-INV-1002",
    "buyer": {
        "name": "Standard Chartered Pakistan",
        "ntn": "1122334-5",
        "buyer_type": "REGISTERED_BUSINESS"
    },
    "items": [{
        "item_name": "Enterprise Software License",
        "hs_code": "8523.49.20",
        "uom": "NUM",
        "quantity": 2,
        "unit_price": 50000.0,
        "tax_rate": 18.0
    }],
    "auto_submit_fbr": True
}

headers = {"X-API-Key": "fbr_live_xxxxxxxxxxxxxxxxxxxxxx"}
resp = requests.post("http://localhost:8000/api/v1/external/invoices", json=payload, headers=headers)
print(resp.json())`,
    nodejs: `const axios = require('axios');

async function submitInvoice() {
  const resp = await axios.post('http://localhost:8000/api/v1/external/invoices', {
    branch_code: 'KHI-01',
    external_reference_id: 'ERP-INV-1002',
    buyer: {
      name: 'Standard Chartered Pakistan',
      ntn: '1122334-5',
      buyer_type: 'REGISTERED_BUSINESS'
    },
    items: [{
      item_name: 'Enterprise Software License',
      hs_code: '8523.49.20',
      uom: 'NUM',
      quantity: 2,
      unit_price: 50000.0,
      tax_rate: 18.0
    }],
    auto_submit_fbr: true
  }, {
    headers: { 'X-API-Key': 'fbr_live_xxxxxxxxxxxxxxxxxxxxxx' }
  });

  console.log(resp.data);
}`,
    sap: `" SAP ABAP REST Integration Pattern
DATA: lo_http TYPE REF TO if_http_client.
cl_http_client=>create_by_url(
  EXPORTING url = 'http://localhost:8000/api/v1/external/invoices'
  IMPORTING client = lo_http ).
lo_http->request->set_method( 'POST' ).
lo_http->request->set_header_field( name = 'X-API-Key' value = 'fbr_live_xxxxxxxx' ).
lo_http->request->set_cdata( lv_json_invoice ).
lo_http->send( ).
lo_http->receive( ).`,
    oracle: `-- Oracle Cloud PL/SQL REST Invocation
DECLARE
  l_resp CLOB;
BEGIN
  apex_web_service.set_request_header('X-API-Key', 'fbr_live_xxxxxxxx');
  l_resp := apex_web_service.make_rest_request(
    p_url => 'http://localhost:8000/api/v1/external/invoices',
    p_http_method => 'POST',
    p_body => l_json_body
  );
END;`,
    odoo: `# Odoo 16/17 External Digital Invoicing Integration
import requests

def action_post_fbr(self):
    payload = {
        "branch_code": "KHI-01",
        "external_reference_id": self.name,
        "buyer": { "name": self.partner_id.name, "ntn": self.partner_id.vat },
        "items": [{ "item_name": l.name, "hs_code": "8523.49.20", "quantity": l.quantity, "unit_price": l.price_unit, "tax_rate": 18.0 } for l in self.invoice_line_ids],
        "auto_submit_fbr": True
    }
    requests.post("http://localhost:8000/api/v1/external/invoices", json=payload, headers={"X-API-Key": self.env['ir.config_parameter'].get_param('fbr.api_key')})`
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 bg-emerald-100 text-emerald-700 rounded-lg">
              <Code2 className="w-5 h-5" />
            </span>
            <h2 className="text-xl font-bold text-slate-900">Developer & ERP Integration Hub</h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Connect SAP, Oracle, Odoo, and custom POS systems directly to the FBR Digital Invoicing engine.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a 
            href="/developer/portal" 
            target="_blank" 
            rel="noreferrer" 
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Standalone Docs Portal
          </a>
          <a 
            href="/openapi.json" 
            target="_blank" 
            rel="noreferrer" 
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition"
          >
            <FileCode className="w-3.5 h-3.5" />
            OpenAPI JSON
          </a>
        </div>
      </div>

      {/* Sub Navigation */}
      <div className="flex border-b border-slate-200 bg-white px-6 pt-3 rounded-t-xl gap-6">
        <button
          onClick={() => setActiveSubTab('erp')}
          className={`pb-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
            activeSubTab === 'erp' ? 'border-emerald-600 text-emerald-700' : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Code2 className="w-4 h-4" />
          ERP Code Blueprints
        </button>
        <button
          onClick={() => setActiveSubTab('keys')}
          className={`pb-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
            activeSubTab === 'keys' ? 'border-emerald-600 text-emerald-700' : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Key className="w-4 h-4" />
          API Keys Management
        </button>
        <button
          onClick={() => setActiveSubTab('webhooks')}
          className={`pb-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
            activeSubTab === 'webhooks' ? 'border-emerald-600 text-emerald-700' : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Webhook className="w-4 h-4" />
          HMAC Webhooks Guide
        </button>
        <button
          onClick={() => setActiveSubTab('cert')}
          className={`pb-3 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
            activeSubTab === 'cert' ? 'border-emerald-600 text-emerald-700' : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Award className="w-4 h-4" />
          PRAL Certification Runner
        </button>
      </div>

      {/* TAB 1: ERP Blueprints */}
      {activeSubTab === 'erp' && (
        <div className="bg-white border border-slate-200 rounded-b-xl rounded-tr-xl p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Endpoint: POST /api/v1/external/invoices</h3>
              <p className="text-xs text-slate-500">Idempotent ERP ingestion with automatic PRAL sales tax calculation.</p>
            </div>
            <div className="flex bg-slate-100 p-1 rounded-lg gap-1 text-xs">
              {(['curl', 'python', 'nodejs', 'sap', 'oracle', 'odoo'] as const).map(l => (
                <button
                  key={l}
                  onClick={() => setErpLang(l)}
                  className={`px-3 py-1 rounded font-medium uppercase text-[11px] transition ${
                    erpLang === l ? 'bg-white shadow-sm text-slate-900 font-bold' : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>

          <div className="relative bg-slate-950 text-slate-100 p-4 rounded-xl font-mono text-xs overflow-x-auto border border-slate-800">
            <button
              onClick={() => copyToClipboard(snippets[erpLang], 'snippet')}
              className="absolute top-3 right-3 p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              title="Copy code"
            >
              {copied === 'snippet' ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
            <pre><code>{snippets[erpLang]}</code></pre>
          </div>
        </div>
      )}

      {/* TAB 2: API Keys Management */}
      {activeSubTab === 'keys' && (
        <div className="bg-white border border-slate-200 rounded-b-xl rounded-tr-xl p-6 shadow-sm space-y-6">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Generate Developer API Key</h3>
            <p className="text-xs text-slate-500">API keys are salted and SHA-256 hashed. Plaintext is shown only once.</p>
          </div>

          {newKeyResult && (
            <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-xl space-y-2">
              <div className="flex items-center gap-2 text-emerald-900 text-xs font-bold">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                API Key Generated Successfully — Copy It Now!
              </div>
              <div className="flex items-center gap-2">
                <input 
                  type="text" 
                  readOnly 
                  value={newKeyResult} 
                  className="flex-1 bg-white border border-emerald-200 text-xs font-mono p-2 rounded text-slate-800 select-all"
                />
                <button
                  onClick={() => copyToClipboard(newKeyResult, 'newkey')}
                  className="px-3 py-2 bg-emerald-700 text-white rounded text-xs font-semibold hover:bg-emerald-800 transition flex items-center gap-1"
                >
                  {copied === 'newkey' ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  Copy
                </button>
              </div>
            </div>
          )}

          <form onSubmit={handleCreateKey} className="flex flex-col sm:flex-row items-end gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
            <div className="flex-1 space-y-1">
              <label className="text-[11px] font-bold text-slate-700 uppercase">Key Name / ERP Description</label>
              <input
                type="text"
                placeholder="e.g. SAP Production Connector"
                value={keyName}
                onChange={e => setKeyName(e.target.value)}
                className="w-full text-xs p-2 rounded border border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div className="w-36 space-y-1">
              <label className="text-[11px] font-bold text-slate-700 uppercase">Environment</label>
              <select
                value={keyEnv}
                onChange={e => setKeyEnv(e.target.value as any)}
                className="w-full text-xs p-2 rounded border border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
              >
                <option value="LIVE">LIVE (fbr_live_*)</option>
                <option value="TEST">TEST (fbr_test_*)</option>
              </select>
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-emerald-600 text-white text-xs font-bold rounded hover:bg-emerald-700 transition"
            >
              Generate Key
            </button>
          </form>

          {/* Key Table */}
          <div className="overflow-x-auto border border-slate-200 rounded-lg">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase text-[10px] font-bold">
                <tr>
                  <th className="p-3">Name</th>
                  <th className="p-3">Prefix</th>
                  <th className="p-3">Environment</th>
                  <th className="p-3">Scopes</th>
                  <th className="p-3">Rate Limit</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoadingKeys ? (
                  <tr><td colSpan={6} className="p-4 text-center text-slate-400">Loading API keys...</td></tr>
                ) : apiKeys.length === 0 ? (
                  <tr><td colSpan={6} className="p-4 text-center text-slate-400">No developer API keys active.</td></tr>
                ) : (
                  apiKeys.map(k => (
                    <tr key={k.id} className="hover:bg-slate-50">
                      <td className="p-3 font-semibold text-slate-800">{k.name}</td>
                      <td className="p-3 font-mono text-emerald-700">{k.key_prefix}...</td>
                      <td className="p-3 font-semibold text-slate-600">{k.environment}</td>
                      <td className="p-3 text-slate-500">{k.scopes}</td>
                      <td className="p-3 text-slate-500">{k.rate_limit_per_minute} rpm</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${k.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                          {k.is_active ? 'ACTIVE' : 'REVOKED'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: Webhooks Guide */}
      {activeSubTab === 'webhooks' && (
        <div className="bg-white border border-slate-200 rounded-b-xl rounded-tr-xl p-6 shadow-sm space-y-6">
          <div>
            <h3 className="text-sm font-bold text-slate-900">HMAC-SHA256 Webhook Verification</h3>
            <p className="text-xs text-slate-500">Every webhook includes an HMAC digest computed over the timestamp and payload body.</p>
          </div>

          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 font-mono text-xs space-y-1 text-slate-700">
            <div><span className="font-bold text-slate-900">Header:</span> X-FBR-Signature: sha256=&lt;hex_digest&gt;</div>
            <div><span className="font-bold text-slate-900">Header:</span> X-FBR-Timestamp: &lt;unix_timestamp&gt;</div>
            <div><span className="font-bold text-slate-900">Signed String:</span> &quot;&lt;timestamp&gt;.&lt;raw_json_payload&gt;&quot;</div>
          </div>

          <div className="bg-slate-950 p-4 rounded-xl text-slate-100 font-mono text-xs">
            <pre><code>{`# Python Flask / FastAPI Webhook Handler
import hmac
import hashlib
import time

def verify_signature(payload_bytes, signature_header, timestamp_header, signing_secret):
    # Reject if timestamp differs by more than 5 minutes
    if abs(time.time() - int(timestamp_header)) > 300:
        return False
        
    expected = hmac.new(
        signing_secret.encode('utf-8'),
        f"{timestamp_header}.".encode('utf-8') + payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    received = signature_header.replace("sha256=", "")
    return hmac.compare_digest(expected, received)`}</code></pre>
          </div>
        </div>
      )}

      {/* TAB 4: PRAL Certification Runner */}
      {activeSubTab === 'cert' && (
        <div className="bg-white border border-slate-200 rounded-b-xl rounded-tr-xl p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">PRAL Pre-Production Certification Runner</h3>
              <p className="text-xs text-slate-500">Executes the 5 test transmission cycles required by PRAL before going live.</p>
            </div>
            <div className="flex items-center gap-3">
              <select
                value={certMode}
                onChange={e => setCertMode(e.target.value as any)}
                className="text-xs p-2 rounded border border-slate-300 bg-white font-medium"
              >
                <option value="SANDBOX">SANDBOX GATEWAY</option>
                <option value="PRODUCTION">PRODUCTION GATEWAY</option>
              </select>
              <button
                onClick={handleRunCertification}
                disabled={isCertRunning}
                className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded text-xs font-bold hover:bg-emerald-700 transition disabled:opacity-50"
              >
                {isCertRunning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                {isCertRunning ? 'Executing Cycles...' : 'Execute Certification Drill'}
              </button>
            </div>
          </div>

          {certResult && (
            <div className="space-y-4 border border-slate-200 rounded-xl p-5 bg-slate-50">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                <div>
                  <span className="text-xs font-mono text-slate-500">Dossier: {certResult.dossier_id}</span>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${certResult.certified ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                      {certResult.certification_status}
                    </span>
                    <span className="text-xs font-bold text-slate-700">Score: {certResult.compliance_score}%</span>
                  </div>
                </div>
                <div className="text-right text-xs text-slate-500">
                  <div>Seal: <span className="font-mono text-slate-800 font-semibold">{certResult.cryptographic_seal.slice(0, 16)}...</span></div>
                  <div>Duration: {certResult.total_duration_ms} ms</div>
                </div>
              </div>

              <div className="space-y-2">
                {certResult.cycles.map((c: any) => (
                  <div key={c.cycle_number} className="flex items-center justify-between bg-white p-3 rounded border border-slate-200 text-xs">
                    <div className="flex items-center gap-2">
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${c.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                        {c.cycle_number}
                      </span>
                      <div>
                        <div className="font-bold text-slate-800">{c.cycle_name}</div>
                        <div className="text-[11px] text-slate-500">{c.description}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] text-slate-400 font-mono">{c.duration_ms}ms</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${c.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                        {c.passed ? 'PASS' : 'FAIL'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
