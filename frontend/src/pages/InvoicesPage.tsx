import React, { useEffect, useState } from 'react';
import { 
  Search, 
  Filter, 
  Send, 
  QrCode, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Plus,
  Play,
  FileText,
  Layers,
  CheckSquare,
  Square,
  RefreshCcw,
} from 'lucide-react';
import { invoicesApi } from '../api/invoices';
import { Invoice, FBRSubmission } from '../types';
import { StatusBadge } from '../components/common/StatusBadge';
import { QRViewerModal } from '../components/invoices/QRViewerModal';
import { SubmissionDetailModal } from '../components/invoices/SubmissionDetailModal';
import { BatchJobProgressModal } from '../components/invoices/BatchJobProgressModal';

interface InvoicesPageProps {
  onNewInvoice: () => void;
}

export const InvoicesPage: React.FC<InvoicesPageProps> = ({ onNewInvoice }) => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  
  const [selectedQRInvoice, setSelectedQRInvoice] = useState<Invoice | null>(null);
  const [selectedSubmission, setSelectedSubmission] = useState<FBRSubmission | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [activeBatchJobId, setActiveBatchJobId] = useState<string | null>(null);
  const [reconciling, setReconciling] = useState(false);
  const [batchSubmitting, setBatchSubmitting] = useState(false);

  const fetchInvoices = async () => {
    setLoading(true);
    try {
      const data = await invoicesApi.getInvoices({
        search: searchTerm || undefined,
        fbr_status: statusFilter || undefined,
      });
      setInvoices(data);
    } catch (err) {
      console.error('Error fetching invoices:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, [statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchInvoices();
  };

  const handleValidate = async (invoiceId: string) => {
    setProcessingId(invoiceId);
    try {
      const res = await invoicesApi.validateInvoice(invoiceId);
      if (res.is_valid) {
        alert('Validation Successful! Invoice is fully compliant with FBR tax schema.');
      } else {
        alert(`Validation Errors:\n${res.errors.join('\n')}`);
      }
      await fetchInvoices();
    } catch (err: any) {
      alert(`Validation error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleSubmit = async (invoiceId: string, scenario: string = 'AUTO') => {
    setProcessingId(invoiceId);
    try {
      const sub = await invoicesApi.submitToFBR(invoiceId, scenario);
      setSelectedSubmission(sub);
      await fetchInvoices();
    } catch (err: any) {
      alert(`Submission error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const [downloadingPdfId, setDownloadingPdfId] = useState<string | null>(null);

  const handleDownloadPdf = async (invoiceId: string) => {
    setDownloadingPdfId(invoiceId);
    try {
      await invoicesApi.triggerPdfDownload(invoiceId);
    } catch (err: any) {
      alert(`Failed to download PDF: ${err.message}`);
    } finally {
      setDownloadingPdfId(null);
    }
  };

  const handleToggleSelectAll = () => {
    if (selectedIds.length === invoices.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(invoices.map((inv) => inv.id));
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleBatchSubmit = async () => {
    if (selectedIds.length === 0) return;
    setBatchSubmitting(true);
    try {
      const res = await invoicesApi.batchSubmitInvoices(selectedIds);
      if (res.batch_job_id) {
        setActiveBatchJobId(res.batch_job_id);
      } else {
        alert(res.message);
        await fetchInvoices();
      }
    } catch (err: any) {
      alert(`Batch submission error: ${err.message}`);
    } finally {
      setBatchSubmitting(false);
    }
  };

  const handleReconcileSelected = async () => {
    setReconciling(true);
    try {
      const res = await invoicesApi.reconcileFbrInvoices(
        selectedIds.length > 0 ? selectedIds : undefined
      );
      alert(
        `FBR Reconciliation Complete:\n• Inspected: ${res.total_inspected}\n• Matched & Accepted: ${res.matched_accepted}\n• Marked Failed: ${res.marked_failed}\n• Already Valid: ${res.already_valid}`
      );
      await fetchInvoices();
    } catch (err: any) {
      alert(`Reconciliation error: ${err.message}`);
    } finally {
      setReconciling(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Tax Invoice Register</h2>
          <p className="text-xs text-slate-500 mt-1">
            Browse, validate, transmit, and monitor compliance status of digital sales tax invoices.
          </p>
        </div>
        <button
          onClick={onNewInvoice}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm shadow-emerald-200 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>New Tax Invoice</span>
        </button>
      </div>

      {/* Filters and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full sm:max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by invoice #, buyer name, or NTN..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </form>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Filter className="w-4 h-4 text-slate-400" />
            <span>FBR Status:</span>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="NOT_SUBMITTED">Not Submitted</option>
            <option value="VALID">Valid / Verified</option>
            <option value="PENDING">Pending Fiscal Queue</option>
            <option value="FAILED">Failed / Rejected</option>
          </select>

          <button
            onClick={fetchInvoices}
            className="p-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-slate-500 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Batch Actions Bar */}
      {selectedIds.length > 0 && (
        <div className="bg-emerald-900 text-white p-4 rounded-xl flex flex-wrap items-center justify-between gap-3 shadow-md animate-in slide-in-from-top-2 duration-200">
          <div className="flex items-center gap-2">
            <span className="bg-emerald-800 text-emerald-100 font-bold px-2.5 py-1 rounded-full text-xs font-mono">
              {selectedIds.length}
            </span>
            <span className="text-xs font-semibold">invoices selected for bulk operations</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleBatchSubmit}
              disabled={batchSubmitting}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-400 text-white rounded-lg text-xs font-bold transition-colors disabled:opacity-50"
            >
              <Layers className="w-4 h-4" />
              <span>{batchSubmitting ? 'Queueing Batch...' : 'Batch Submit to FBR'}</span>
            </button>

            <button
              onClick={handleReconcileSelected}
              disabled={reconciling}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-800 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
            >
              <RefreshCcw className={`w-4 h-4 ${reconciling ? 'animate-spin' : ''}`} />
              <span>{reconciling ? 'Reconciling...' : 'Reconcile with FBR'}</span>
            </button>

            <button
              onClick={() => setSelectedIds([])}
              className="px-3 py-1.5 text-xs text-emerald-200 hover:text-white transition-colors"
            >
              Clear Selection
            </button>
          </div>
        </div>
      )}

      {/* Invoices Data Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
              <tr>
                <th className="py-3.5 px-4 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={invoices.length > 0 && selectedIds.length === invoices.length}
                    onChange={handleToggleSelectAll}
                    className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                  />
                </th>
                <th className="py-3.5 px-4">Invoice #</th>
                <th className="py-3.5 px-4">Date</th>
                <th className="py-3.5 px-4">Branch</th>
                <th className="py-3.5 px-4">Customer (Buyer)</th>
                <th className="py-3.5 px-4">Taxable Amount</th>
                <th className="py-3.5 px-4">Sales Tax</th>
                <th className="py-3.5 px-4">Grand Total</th>
                <th className="py-3.5 px-4">FBR Status</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center">
                    <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin mx-auto" />
                  </td>
                </tr>
              ) : invoices.length > 0 ? (
                invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3.5 px-4 text-center">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(inv.id)}
                        onChange={() => handleToggleSelect(inv.id)}
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                      />
                    </td>
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                      {inv.invoice_number}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500">
                      {new Date(inv.invoice_date).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-600">
                      {inv.seller_branch_code}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-800">{inv.buyer_name}</div>
                      <div className="text-[10px] text-slate-400">NTN: {inv.buyer_ntn || 'Unregistered'}</div>
                    </td>
                    <td className="py-3.5 px-4 font-medium">
                      PKR {Number(inv.taxable_amount).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-emerald-700">
                      PKR {Number(inv.total_tax).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-slate-900">
                      PKR {Number(inv.grand_total).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={inv.fbr_status} />
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleDownloadPdf(inv.id)}
                          disabled={downloadingPdfId === inv.id}
                          className="flex items-center gap-1 px-2.5 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-medium border border-slate-200 transition-colors"
                          title="Download Official Tax PDF"
                        >
                          <FileText className="w-3.5 h-3.5 text-slate-500" />
                          <span>{downloadingPdfId === inv.id ? '...' : 'PDF'}</span>
                        </button>
                        {inv.fbr_status === 'VALID' ? (
                          <button
                            onClick={() => setSelectedQRInvoice(inv)}
                            className="flex items-center gap-1 px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-lg font-medium border border-emerald-200 transition-colors"
                            title="View Official FBR QR Code"
                          >
                            <QrCode className="w-3.5 h-3.5" />
                            <span>QR Code</span>
                          </button>
                        ) : (
                          <>
                            <button
                              onClick={() => handleValidate(inv.id)}
                              disabled={processingId === inv.id}
                              className="px-2 py-1 border border-slate-200 hover:bg-slate-100 text-slate-600 rounded-lg text-xs font-medium transition-colors"
                              title="Validate rules"
                            >
                              Validate
                            </button>
                            <button
                              onClick={() => handleSubmit(inv.id)}
                              disabled={processingId === inv.id}
                              className="flex items-center gap-1 px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
                              title="Submit to FBR"
                            >
                              <Send className="w-3 h-3" />
                              <span>{processingId === inv.id ? 'Sending...' : 'Submit'}</span>
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-slate-400 text-xs">
                    No invoices match the filter criteria.
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

      {/* Batch Bulk Submission Modal */}
      {activeBatchJobId && (
        <BatchJobProgressModal
          jobId={activeBatchJobId}
          onClose={() => {
            setActiveBatchJobId(null);
            fetchInvoices();
          }}
          onComplete={() => {
            fetchInvoices();
          }}
        />
      )}
    </div>
  );
};
