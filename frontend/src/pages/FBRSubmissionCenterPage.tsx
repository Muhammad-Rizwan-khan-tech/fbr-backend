import React, { useEffect, useState } from 'react';
import { 
  Send, 
  RefreshCw, 
  Filter, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  ExternalLink,
  ShieldCheck
} from 'lucide-react';
import { fbrApi } from '../api/fbr';
import { FBRSubmission } from '../types';
import { StatusBadge } from '../components/common/StatusBadge';
import { SubmissionDetailModal } from '../components/invoices/SubmissionDetailModal';

export const FBRSubmissionCenterPage: React.FC = () => {
  const [submissions, setSubmissions] = useState<FBRSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedSub, setSelectedSub] = useState<FBRSubmission | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const fetchSubmissions = async () => {
    setLoading(true);
    try {
      const data = await fbrApi.getSubmissions(statusFilter || undefined);
      setSubmissions(data);
    } catch (err) {
      console.error('Failed to load FBR submissions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubmissions();
  }, [statusFilter]);

  const handleRetry = async (submissionId: string) => {
    setRetryingId(submissionId);
    try {
      const updated = await fbrApi.retrySubmission(submissionId);
      setSelectedSub(updated);
      await fetchSubmissions();
    } catch (err: any) {
      alert(`Retry failed: ${err.message}`);
    } finally {
      setRetryingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">FBR Digital Invoicing Submission Center</h2>
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full">
              CENTRAL LEDGER
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Real-time audit log of all electronic tax invoice transmissions, PRAL confirmations, and retry queues.
          </p>
        </div>

        <button
          onClick={fetchSubmissions}
          className="flex items-center gap-2 px-3 py-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-medium text-slate-600">Filter By Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 font-medium"
          >
            <option value="">All Transmissions</option>
            <option value="VALID">Valid / Verified</option>
            <option value="FAILED">Failed / Timeout</option>
            <option value="PENDING">Pending Fiscal Queue</option>
            <option value="INVALID">Schema Invalid</option>
          </select>
        </div>

        <div className="text-xs text-slate-400 font-medium">
          Showing {submissions.length} submission records
        </div>
      </div>

      {/* Submissions Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
              <tr>
                <th className="py-3.5 px-4">Transmission ID</th>
                <th className="py-3.5 px-4">FBR Invoice #</th>
                <th className="py-3.5 px-4">Adapter / Mode</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Error / Response Code</th>
                <th className="py-3.5 px-4">Attempts</th>
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center">
                    <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin mx-auto" />
                  </td>
                </tr>
              ) : submissions.length > 0 ? (
                submissions.map((sub) => (
                  <tr key={sub.id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-medium text-slate-600">
                      {sub.request_id.slice(0, 13)}...
                    </td>
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                      {sub.fbr_invoice_number || (
                        <span className="text-slate-400 font-normal">Not Registered</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-[10px] font-semibold border border-slate-200">
                        {sub.environment} ({sub.adapter_name})
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={sub.status} />
                    </td>
                    <td className="py-3.5 px-4 max-w-xs truncate">
                      {sub.error_code ? (
                        <span className="text-rose-600 font-semibold" title={sub.error_message}>
                          {sub.error_code}: {sub.error_message}
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-medium">00 (Success)</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-slate-600">
                      {sub.retry_count + 1}
                    </td>
                    <td className="py-3.5 px-4 text-slate-400">
                      {new Date(sub.submitted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setSelectedSub(sub)}
                          className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
                        >
                          Audit Details
                        </button>
                        {sub.is_retryable && (
                          <button
                            onClick={() => handleRetry(sub.id)}
                            disabled={retryingId === sub.id}
                            className="flex items-center gap-1 px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
                          >
                            <RefreshCw className={`w-3 h-3 ${retryingId === sub.id ? 'animate-spin' : ''}`} />
                            <span>Retry</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400 text-xs">
                    No submissions found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Submission Detail Modal */}
      {selectedSub && (
        <SubmissionDetailModal
          submission={selectedSub}
          onClose={() => setSelectedSub(null)}
          onRetry={handleRetry}
          isRetrying={retryingId === selectedSub.id}
        />
      )}
    </div>
  );
};
