import React, { useEffect, useState } from 'react';
import { 
  FileText, 
  CheckCircle2, 
  Clock, 
  AlertOctagon, 
  TrendingUp, 
  Coins, 
  Send,
  Eye,
  QrCode,
  RefreshCw,
  ArrowUpRight,
  ShieldCheck,
  PlayCircle
} from 'lucide-react';
import { masterApi } from '../api/master';
import { invoicesApi } from '../api/invoices';
import { fbrApi, FBRStatus } from '../api/fbr';
import { DashboardKPIs, Invoice, FBRSubmission } from '../types';
import { StatusBadge } from '../components/common/StatusBadge';
import { QRViewerModal } from '../components/invoices/QRViewerModal';
import { SubmissionDetailModal } from '../components/invoices/SubmissionDetailModal';

interface DashboardPageProps {
  onNavigate: (tab: string) => void;
  onNewInvoice: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate, onNewInvoice }) => {
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [fbrStatus, setFbrStatus] = useState<FBRStatus | null>(null);
  const [loading, setLoading] = useState(true);

  // Modals state
  const [selectedQRInvoice, setSelectedQRInvoice] = useState<Invoice | null>(null);
  const [selectedSubmission, setSelectedSubmission] = useState<FBRSubmission | null>(null);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [kpisData, invData, statusData] = await Promise.all([
        masterApi.getDashboardKPIs(),
        invoicesApi.getInvoices(),
        fbrApi.getStatus(),
      ]);
      setKpis(kpisData);
      setInvoices(invData.slice(0, 5));
      setFbrStatus(statusData);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSubmitToFBR = async (invoiceId: string, scenario: string = 'AUTO') => {
    setSubmittingId(invoiceId);
    try {
      const submission = await invoicesApi.submitToFBR(invoiceId, scenario);
      setSelectedSubmission(submission);
      await fetchData();
    } catch (err: any) {
      alert(`Submission failed: ${err.message}`);
    } finally {
      setSubmittingId(null);
    }
  };

  const handleTestConnection = async () => {
    try {
      const res = await fbrApi.testConnection();
      setTestResult(`Gateway connected: ${res.message}`);
      setTimeout(() => setTestResult(null), 4000);
    } catch (err: any) {
      setTestResult(`Gateway error: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner / Welcome */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Tax Invoicing Overview</h2>
          <p className="text-xs text-slate-500 mt-1">
            Real-time compliance status for FBR digital tax invoices under Sales Tax Act 1990.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleTestConnection}
            className="flex items-center gap-2 px-3 py-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700 transition-colors"
          >
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Test FBR Gateway
          </button>
          <button
            onClick={onNewInvoice}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm shadow-emerald-200 transition-colors"
          >
            + Create Tax Invoice
          </button>
        </div>
      </div>

      {testResult && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium rounded-xl flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>{testResult}</span>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Monthly Invoices</span>
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <FileText className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            {kpis?.monthly_invoices_count || 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Today: {kpis?.today_invoices_count || 0} issued</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">FBR Valid Submissions</span>
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-emerald-600 mt-2">
            {kpis?.valid_fbr_count || 0}
          </div>
          <div className="text-[11px] text-emerald-700 mt-1">Verified with Central Ledger</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Total Taxable Amount</span>
            <div className="p-2 bg-slate-50 text-slate-600 rounded-lg">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-bold text-slate-900 mt-2 truncate">
            PKR {Number(kpis?.total_taxable_amount || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Gross sales before GST</div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Sales Tax (GST)</span>
            <div className="p-2 bg-emerald-50 text-emerald-700 rounded-lg">
              <Coins className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-bold text-emerald-700 mt-2 truncate">
            PKR {Number(kpis?.total_tax || 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Total Output Tax</div>
        </div>
      </div>

      {/* Second Row: FBR Gateway Status & Demo Scenarios */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* FBR Gateway Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
              <h3 className="font-bold text-sm text-slate-900">FBR Integration Status</h3>
            </div>
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full">
              CONNECTED
            </span>
          </div>

          <div className="space-y-2 text-xs text-slate-600 border-t border-slate-100 pt-3">
            <div className="flex justify-between">
              <span className="text-slate-400">Environment:</span>
              <span className="font-bold text-slate-800">{fbrStatus?.environment || 'DEMO'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Adapter Route:</span>
              <span className="font-semibold text-slate-700">{fbrStatus?.adapter || 'MockFBRAdapter'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Pending Queue:</span>
              <span className="font-semibold text-amber-600">{fbrStatus?.pending_queue_count || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Failed / Rejected:</span>
              <span className="font-semibold text-rose-600">{fbrStatus?.failed_submissions_count || 0}</span>
            </div>
          </div>

          <button
            onClick={() => onNavigate('fbr')}
            className="w-full py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 transition-colors flex items-center justify-center gap-1.5"
          >
            <span>Open FBR Submission Center</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Demo Scenarios Interactive Box */}
        <div className="md:col-span-2 bg-gradient-to-br from-slate-900 to-slate-800 p-6 rounded-2xl text-white shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PlayCircle className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-sm">Demo Mode Scenario Simulator</h3>
              </div>
              <span className="text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 px-2.5 py-0.5 rounded-full border border-emerald-500/30">
                Blueprint Section 47
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-2 leading-relaxed">
              Test end-to-end digital invoicing workflows against all Blueprint test scenarios.
              Experience valid submissions, timeouts with exponential backoff, rejection handling, and fiscal QR rendering.
            </p>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-700/60 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <button
              onClick={() => onNavigate('invoices')}
              className="p-2.5 bg-slate-800/80 hover:bg-emerald-600 border border-slate-700 rounded-lg transition-colors text-left font-medium"
            >
              <div className="text-emerald-400 text-[10px] uppercase font-bold">Scenario 1</div>
              <div className="text-white text-xs mt-0.5">Valid Submission & QR</div>
            </button>
            <button
              onClick={() => onNavigate('fbr')}
              className="p-2.5 bg-slate-800/80 hover:bg-amber-600 border border-slate-700 rounded-lg transition-colors text-left font-medium"
            >
              <div className="text-amber-400 text-[10px] uppercase font-bold">Scenario 2</div>
              <div className="text-white text-xs mt-0.5">Timeout & Retry</div>
            </button>
            <button
              onClick={() => onNavigate('invoices')}
              className="p-2.5 bg-slate-800/80 hover:bg-rose-600 border border-slate-700 rounded-lg transition-colors text-left font-medium"
            >
              <div className="text-rose-400 text-[10px] uppercase font-bold">Scenario 3</div>
              <div className="text-white text-xs mt-0.5">Rejection Handling</div>
            </button>
            <button
              onClick={() => onNavigate('settings')}
              className="p-2.5 bg-slate-800/80 hover:bg-blue-600 border border-slate-700 rounded-lg transition-colors text-left font-medium"
            >
              <div className="text-blue-400 text-[10px] uppercase font-bold">Scenario 4</div>
              <div className="text-white text-xs mt-0.5">Switch FBR Mode</div>
            </button>
          </div>
        </div>
      </div>

      {/* Recent Invoices Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-sm text-slate-900">Recent Tax Invoices</h3>
            <p className="text-xs text-slate-400 mt-0.5">Latest invoices generated in current tenant session</p>
          </div>
          <button
            onClick={() => onNavigate('invoices')}
            className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center gap-1"
          >
            <span>View All Invoices</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
              <tr>
                <th className="py-3 px-4">Invoice #</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Buyer (Customer)</th>
                <th className="py-3 px-4">Taxable Amount</th>
                <th className="py-3 px-4">Sales Tax</th>
                <th className="py-3 px-4">Grand Total</th>
                <th className="py-3 px-4">FBR Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {invoices.length > 0 ? (
                invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      {inv.invoice_number}
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {new Date(inv.invoice_date).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-800">{inv.buyer_name}</div>
                      <div className="text-[10px] text-slate-400">{inv.buyer_ntn || 'Unregistered'}</div>
                    </td>
                    <td className="py-3 px-4 font-medium">
                      PKR {Number(inv.taxable_amount).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-medium text-emerald-700">
                      PKR {Number(inv.total_tax).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900">
                      PKR {Number(inv.grand_total).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={inv.fbr_status} />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {inv.fbr_status === 'VALID' ? (
                          <button
                            onClick={() => setSelectedQRInvoice(inv)}
                            className="p-1.5 text-slate-600 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                            title="View Official FBR QR Code"
                          >
                            <QrCode className="w-4 h-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleSubmitToFBR(inv.id)}
                            disabled={submittingId === inv.id}
                            className="flex items-center gap-1 px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-semibold rounded-lg text-xs transition-colors border border-emerald-200"
                            title="Submit to FBR"
                          >
                            <Send className="w-3 h-3" />
                            <span>{submittingId === inv.id ? 'Sending...' : 'Transmit'}</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400 text-xs">
                    No invoices recorded yet. Click "+ Create Tax Invoice" to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* QR Viewer Modal */}
      {selectedQRInvoice && (
        <QRViewerModal
          invoice={selectedQRInvoice}
          onClose={() => setSelectedQRInvoice(null)}
        />
      )}

      {/* Submission Detail Modal */}
      {selectedSubmission && (
        <SubmissionDetailModal
          submission={selectedSubmission}
          onClose={() => setSelectedSubmission(null)}
        />
      )}
    </div>
  );
};
