import React from 'react';
import { X, RefreshCw, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { FBRSubmission } from '../../types';
import { StatusBadge } from '../common/StatusBadge';

interface SubmissionDetailModalProps {
  submission: FBRSubmission | null;
  onClose: () => void;
  onRetry?: (id: string) => Promise<void>;
  isRetrying?: boolean;
}

export const SubmissionDetailModal: React.FC<SubmissionDetailModalProps> = ({
  submission,
  onClose,
  onRetry,
  isRetrying = false,
}) => {
  if (!submission) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] flex flex-col animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-slate-900 text-sm">FBR Submission Audit Detail</h3>
              <StatusBadge status={submission.status} />
            </div>
            <p className="text-xs text-slate-400 mt-0.5">Request ID: {submission.request_id}</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 text-slate-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {/* Metadata Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <div className="text-slate-400">Environment</div>
              <div className="font-bold text-slate-800 mt-1">{submission.environment}</div>
            </div>
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <div className="text-slate-400">Adapter</div>
              <div className="font-bold text-slate-800 mt-1 truncate" title={submission.adapter_name}>
                {submission.adapter_name}
              </div>
            </div>
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <div className="text-slate-400">FBR Invoice #</div>
              <div className="font-bold text-emerald-700 mt-1 truncate">
                {submission.fbr_invoice_number || 'N/A'}
              </div>
            </div>
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <div className="text-slate-400">Retries</div>
              <div className="font-bold text-slate-800 mt-1">{submission.retry_count} attempts</div>
            </div>
          </div>

          {/* Error Message if Failed */}
          {submission.error_message && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-2 text-xs text-rose-800">
              <AlertTriangle className="w-4 h-4 text-rose-600 mt-0.5 shrink-0" />
              <div>
                <div className="font-bold">Error Code: {submission.error_code || 'FBR-ERR'}</div>
                <div className="mt-0.5 text-rose-700">{submission.error_message}</div>
              </div>
            </div>
          )}

          <p className="text-[11px] text-slate-500">
            Note: older submissions may display synthetic HTTP 400 values. New submissions
            distinguish real FBR HTTP responses from local validation or transport failures.
          </p>

          {/* Attempt Timeline */}
          <div>
            <h4 className="text-xs font-bold text-slate-700 mb-2">Transmission Attempts Timeline</h4>
            <div className="border border-slate-200 rounded-lg overflow-hidden divide-y divide-slate-100">
              {submission.attempts && submission.attempts.length > 0 ? (
                submission.attempts.map((att) => (
                  <div key={att.id} className="p-3 flex items-center justify-between text-xs hover:bg-slate-50">
                    <div className="flex items-center gap-3">
                      <div className="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600 text-[10px]">
                        #{att.attempt_number}
                      </div>
                      <div>
                        <div className="font-semibold text-slate-800">
                          {att.http_status_code
                            ? `Recorded HTTP ${att.http_status_code} - ${att.status}`
                            : `No upstream HTTP response - ${att.status}`}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {new Date(att.created_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] text-slate-400">{att.latency_ms} ms</span>
                      <StatusBadge status={att.status} />
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-xs text-slate-400">No attempt logs recorded</div>
              )}
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="pt-4 border-t border-slate-100 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="py-2 px-4 border border-slate-200 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700"
          >
            Close
          </button>
          {onRetry && submission.is_retryable && (
            <button
              onClick={() => onRetry(submission.id)}
              disabled={isRetrying}
              className="flex items-center gap-2 py-2 px-4 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm shadow-emerald-200 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
              {isRetrying ? 'Retrying Submission...' : 'Retry Submission'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
