import React, { useEffect, useState } from 'react';
import { Sliders, ShieldCheck, CheckCircle2, Database } from 'lucide-react';
import { masterApi } from '../api/master';

export const TaxConfigPage: React.FC = () => {
  const [rates, setRates] = useState<any[]>([]);
  const [hsCodes, setHsCodes] = useState<any[]>([]);
  const [uoms, setUoms] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'rates' | 'hs' | 'uom'>('rates');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadTaxData() {
      try {
        const [rData, hData, uData] = await Promise.all([
          masterApi.getTaxRates(),
          masterApi.getHSCodes(),
          masterApi.getUOMs(),
        ]);
        setRates(rData);
        setHsCodes(hData);
        setUoms(uData);
      } catch (err) {
        console.error('Error fetching tax reference data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadTaxData();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">FBR Reference Data & Tax Rates</h2>
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full">
              STATUTORY VERSION 2026.1
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Federal and provincial sales tax schedules, standard rates, UOM mappings, and HS code tables.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200">
          <Database className="w-4 h-4 text-emerald-600" />
          <span>Synchronized with Central Repository</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-4 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('rates')}
          className={`pb-3 border-b-2 transition-colors ${
            activeTab === 'rates' ? 'border-emerald-600 text-emerald-600' : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Sales Tax Rates & Schedules ({rates.length})
        </button>
        <button
          onClick={() => setActiveTab('hs')}
          className={`pb-3 border-b-2 transition-colors ${
            activeTab === 'hs' ? 'border-emerald-600 text-emerald-600' : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Pakistan HS Codes ({hsCodes.length})
        </button>
        <button
          onClick={() => setActiveTab('uom')}
          className={`pb-3 border-b-2 transition-colors ${
            activeTab === 'uom' ? 'border-emerald-600 text-emerald-600' : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Units of Measure (UOM) ({uoms.length})
        </button>
      </div>

      {/* Content */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {activeTab === 'rates' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                <tr>
                  <th className="py-3 px-4">Rate Name</th>
                  <th className="py-3 px-4">Rate %</th>
                  <th className="py-3 px-4">Tax Type</th>
                  <th className="py-3 px-4">Jurisdiction / Province</th>
                  <th className="py-3 px-4">SRO Reference</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {rates.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-bold text-slate-900">{r.name}</td>
                    <td className="py-3 px-4 font-bold text-emerald-700">{r.rate_percent}%</td>
                    <td className="py-3 px-4 font-semibold text-slate-600">{r.tax_type}</td>
                    <td className="py-3 px-4">{r.province}</td>
                    <td className="py-3 px-4 text-slate-400">{r.sro_reference || 'General Schedule'}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 text-emerald-600 text-[11px] font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Active
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'hs' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                <tr>
                  <th className="py-3 px-4">HS Code</th>
                  <th className="py-3 px-4">Description</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {hsCodes.map((h) => (
                  <tr key={h.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">{h.code}</td>
                    <td className="py-3 px-4 text-slate-600">{h.description}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 text-emerald-600 text-[11px] font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Active
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'uom' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                <tr>
                  <th className="py-3 px-4">UOM Code</th>
                  <th className="py-3 px-4">Name</th>
                  <th className="py-3 px-4">FBR Standard Code</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {uoms.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">{u.code}</td>
                    <td className="py-3 px-4 font-medium text-slate-700">{u.name}</td>
                    <td className="py-3 px-4 font-mono text-emerald-700">{u.fbr_code}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 text-emerald-600 text-[11px] font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Active
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
