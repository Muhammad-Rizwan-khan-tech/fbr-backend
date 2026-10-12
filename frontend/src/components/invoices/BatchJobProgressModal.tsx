import React, { useEffect, useState } from 'react';
import { X, CheckCircle2, AlertTriangle, Clock, RefreshCw, Layers } from 'lucide-react';
import { invoicesApi } from '../../api/invoices';
import { BatchSubmissionJob } from '../../types';

interface BatchJobProgressModalProps {
  jobId: string;
  onClose: () => void;
  onComplete?: () => void;
}

export const BatchJobProgressModal: React.FC<BatchJobProgressModalProps> = ({
  jobId,
  onClose,
  onComplete,
}) => {
  const [job, setJob] = useState<BatchSubmissionJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobStatus = async () => {
    try {
      const data = await invoicesApi.getBatchJobStatus(jobId);
      setJob(data);
      if (data.status === 'COMPLETED' || data.status === 'FAILED') {
        if (onComplete) onComplete();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load batch status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobStatus();
    const interval = setInterval(() => {
      if (job?.status === 'COMPLETED' || job?.status === 'FAILED') {
        clearInterval(interval);
        return;
      }
      fetchJobStatus();
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, job?.status]);

  const percentComplete = job && job.total_items > 0
    ? Math.round((job.processed_items / job.total_items) * 100)
    : 0;

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-emerald-100 text-emerald-700 rounded-lg">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">FBR Batch Bulk Submission</h3>
              <p className="text-[11px] font-mono text-slate-500">Job ID: {jobId}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {loading && !job ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3">
              <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin" />
              <p className="text-xs text-slate-500 font-medium">Querying asynchronous batch status...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-xl flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          ) : job ? (
            <>
              {/* Status Header & Progress */}
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-700">Status:</span>
                    <span
                      className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                        job.status === 'COMPLETED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : job.status === 'IN_PROGRESS'
                          ? 'bg-blue-100 text-blue-800 animate-pulse'
                          : job.status === 'FAILED'
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {job.status}
                    </span>
                  </div>
                  <span className="font-mono font-bold text-slate-700">{percentComplete}% Complete</span>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      job.status === 'FAILED' ? 'bg-rose-500' : 'bg-emerald-600'
                    }`}
                    style={{ width: `${percentComplete}%` }}
                  />
                </div>
              </div>

              {/* Counters Grid */}
              <div className="grid grid-cols-4 gap-3">
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-center">
                  <p className="text-[10px] uppercase font-bold text-slate-400">Total Items</p>
                  <p className="text-lg font-bold text-slate-800 mt-0.5">{job.total_items}</p>
                </div>
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-center">
                  <p className="text-[10px] uppercase font-bold text-blue-600">Processed</p>
                  <p className="text-lg font-bold text-blue-800 mt-0.5">{job.processed_items}</p>
                </div>
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-center">
                  <p className="text-[10px] uppercase font-bold text-emerald-600">Accepted</p>
                  <p className="text-lg font-bold text-emerald-800 mt-0.5">{job.successful_items}</p>
                </div>
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-center">
                  <p className="text-[10px] uppercase font-bold text-rose-600">Failed</p>
                  <p className="text-lg font-bold text-rose-800 mt-0.5">{job.failed_items}</p>
                </div>
              </div>

              {/* Item Level Details */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-800">Batch Invoices Execution Log</h4>
                <div className="border border-slate-200 rounded-xl overflow-hidden max-h-56 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 text-[11px]">
                      <tr>
                        <th className="py-2 px-3">Invoice ID</th>
                        <th className="py-2 px-3">Status</th>
                        <th className="py-2 px-3">FBR Invoice # / Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                      {job.items && job.items.length > 0 ? (
                        job.items.map((it, idx) => (
                          <tr key={idx} className="hover:bg-slate-50">
                            <td className="py-2 px-3 text-slate-700 truncate max-w-[140px]" title={it.invoice_id}>
                              {it.invoice_id}
                            </td>
                            <td className="py-2 px-3">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  it.status === 'ACCEPTED'
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : it.status === 'REJECTED' || it.status === 'FAILED'
                                    ? 'bg-rose-100 text-rose-800'
                                    : it.status === 'PROCESSING'
                                    ? 'bg-blue-100 text-blue-800'
                                    : 'bg-slate-100 text-slate-700'
                                }`}
                              >
                                {it.status}
                              </span>
                            </td>
                            <td className="py-2 px-3 text-slate-600 truncate max-w-[200px]" title={it.fbr_invoice_number || it.error}>
                              {it.fbr_invoice_number ? (
                                <span className="text-emerald-700 font-bold">{it.fbr_invoice_number}</span>
                              ) : it.error ? (
                                <span className="text-rose-600">{it.error}</span>
                              ) : (
                                <span className="text-slate-400">In Queue...</span>
                              )}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={3} className="py-4 text-center text-slate-400">
                            No individual item logs available yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
          <div className="flex items-center gap-1 text-[11px] text-slate-500">
            {job?.status === 'IN_PROGRESS' || job?.status === 'PENDING' ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-600" />
                <span>Auto-refreshing worker queue status...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                <span>Batch processing completed</span>
              </>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold transition-colors"
          >
            {job?.status === 'COMPLETED' || job?.status === 'FAILED' ? 'Done' : 'Dismiss to Background'}
          </button>
        </div>
      </div>
    </div>
  );
};
