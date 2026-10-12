import React, { useEffect, useState } from 'react';
import { 
  FileText, 
  Plus, 
  Send, 
  Download, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle2, 
  ArrowLeftRight,
  ShieldCheck,
  Search,
  Scale
} from 'lucide-react';
import { notesApi } from '../api/notes';
import { invoicesApi } from '../api/invoices';
import { CreditNote, DebitNote, Invoice, NoteReconciliation } from '../types';

export const CreditDebitNotesPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'CREDIT' | 'DEBIT'>('CREDIT');
  const [creditNotes, setCreditNotes] = useState<CreditNote[]>([]);
  const [debitNotes, setDebitNotes] = useState<DebitNote[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState('');
  const [reconciliation, setReconciliation] = useState<NoteReconciliation | null>(null);
  const [loadingReconciliation, setLoadingReconciliation] = useState(false);

  // Form Fields
  const [reason, setReason] = useState('Goods returned by customer');
  const [taxableAmount, setTaxableAmount] = useState<number>(0);
  const [salesTax, setSalesTax] = useState<number>(0);
  const [autoSubmit, setAutoSubmit] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Action loading states
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [cNotes, dNotes, invList] = await Promise.all([
        notesApi.getCreditNotes(),
        notesApi.getDebitNotes(),
        invoicesApi.getInvoices(),
      ]);
      setCreditNotes(cNotes);
      setDebitNotes(dNotes);
      setInvoices(invList);
    } catch (err) {
      console.error('Failed to load notes data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleInvoiceSelect = async (invoiceId: string) => {
    setSelectedInvoiceId(invoiceId);
    setFormError(null);
    if (!invoiceId) {
      setReconciliation(null);
      return;
    }

    if (activeTab === 'CREDIT') {
      setLoadingReconciliation(true);
      try {
        const recon = await notesApi.getReconciliation(invoiceId);
        setReconciliation(recon);
        // Pre-fill reasonable defaults
        if (recon.remaining_creditable_amount > 0) {
          const maxTaxable = Math.round((recon.remaining_creditable_amount / 1.18) * 100) / 100;
          setTaxableAmount(maxTaxable);
          setSalesTax(Math.round(maxTaxable * 0.18 * 100) / 100);
        }
      } catch (err: any) {
        setFormError(err.message || 'Failed to check invoice reconciliation balance');
      } finally {
        setLoadingReconciliation(false);
      }
    } else {
      const inv = invoices.find(i => i.id === invoiceId);
      if (inv) {
        setTaxableAmount(Number(inv.taxable_amount));
        setSalesTax(Number(inv.total_tax));
      }
    }
  };

  const handleTaxableChange = (val: number) => {
    setTaxableAmount(val);
    setSalesTax(Math.round(val * 0.18 * 100) / 100);
  };

  const handleCreateNote = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!selectedInvoiceId) {
      setFormError('Please select an original invoice for reconciliation');
      return;
    }

    const grandTotal = Number(taxableAmount) + Number(salesTax);
    if (activeTab === 'CREDIT' && reconciliation) {
      if (grandTotal > reconciliation.remaining_creditable_amount) {
        setFormError(
          `Credit total (PKR ${grandTotal.toLocaleString()}) exceeds allowable remaining creditable limit (PKR ${reconciliation.remaining_creditable_amount.toLocaleString()})`
        );
        return;
      }
    }

    setSubmitting(true);
    try {
      if (activeTab === 'CREDIT') {
        await notesApi.createCreditNote({
          original_invoice_id: selectedInvoiceId,
          reason,
          taxable_amount: Number(taxableAmount),
          sales_tax: Number(salesTax),
          auto_submit: autoSubmit,
        });
      } else {
        await notesApi.createDebitNote({
          original_invoice_id: selectedInvoiceId,
          reason,
          taxable_amount: Number(taxableAmount),
          sales_tax: Number(salesTax),
          auto_submit: autoSubmit,
        });
      }

      setIsModalOpen(false);
      setSelectedInvoiceId('');
      setReconciliation(null);
      await fetchData();
    } catch (err: any) {
      setFormError(err.message || 'Failed to issue note');
    } finally {
      setSubmitting(false);
    }
  };

  const handleQueueSubmit = async (id: string, type: 'CREDIT' | 'DEBIT') => {
    setActionLoadingId(id);
    try {
      if (type === 'CREDIT') {
        await notesApi.queueSubmitCreditNote(id);
      } else {
        await notesApi.queueSubmitDebitNote(id);
      }
      alert('Note queued for FBR fiscal verification!');
      await fetchData();
    } catch (err: any) {
      alert(`Submission error: ${err.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDownloadPdf = async (id: string, type: 'CREDIT' | 'DEBIT') => {
    setActionLoadingId(id);
    try {
      if (type === 'CREDIT') {
        await notesApi.triggerCreditNotePdfDownload(id);
      } else {
        await notesApi.triggerDebitNotePdfDownload(id);
      }
    } catch (err: any) {
      alert(`PDF Download error: ${err.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const currentNotes = activeTab === 'CREDIT' ? creditNotes : debitNotes;
  const totalCredited = creditNotes.reduce((acc, n) => acc + Number(n.grand_total || 0), 0);
  const totalDebited = debitNotes.reduce((acc, n) => acc + Number(n.grand_total || 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Credit & Debit Note Reconciliation</h2>
            <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded-full">
              FBR SEC 9 COMPLIANT
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Reconcile post-issuance sales tax adjustments, price variations, and goods returns with cumulative balance verification.
          </p>
        </div>

        <button
          onClick={() => {
            setIsModalOpen(true);
            setSelectedInvoiceId('');
            setReconciliation(null);
            setFormError(null);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm shadow-emerald-200 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Issue {activeTab === 'CREDIT' ? 'Credit Note' : 'Debit Note'}</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Credit Notes Issued</p>
            <div className="p-2 bg-amber-50 text-amber-600 rounded-lg">
              <Scale className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{creditNotes.length}</p>
          <p className="text-[11px] text-slate-500 mt-1">
            Total Adjustment: <span className="font-mono font-bold text-amber-700">PKR {totalCredited.toLocaleString()}</span>
          </p>
        </div>

        <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Debit Notes Issued</p>
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <ArrowLeftRight className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{debitNotes.length}</p>
          <p className="text-[11px] text-slate-500 mt-1">
            Total Adjustment: <span className="font-mono font-bold text-blue-700">PKR {totalDebited.toLocaleString()}</span>
          </p>
        </div>

        <div className="p-5 bg-white border border-slate-200 rounded-2xl shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Cumulative Balance Engine</p>
            <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <p className="text-sm font-bold text-emerald-800 mt-2">Ceiling Enforced</p>
          <p className="text-[11px] text-slate-500 mt-1">
            Prevents cumulative credit adjustments exceeding original tax invoice total.
          </p>
        </div>
      </div>

      {/* Tabs and Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('CREDIT')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
              activeTab === 'CREDIT'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Credit Notes ({creditNotes.length})
          </button>
          <button
            onClick={() => setActiveTab('DEBIT')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
              activeTab === 'DEBIT'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Debit Notes ({debitNotes.length})
          </button>
        </div>

        <button
          onClick={fetchData}
          className="p-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-slate-500 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Notes Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
              <tr>
                <th className="py-3.5 px-4">Note #</th>
                <th className="py-3.5 px-4">Date</th>
                <th className="py-3.5 px-4">Original Invoice</th>
                <th className="py-3.5 px-4">Reason</th>
                <th className="py-3.5 px-4">Taxable Adjustment</th>
                <th className="py-3.5 px-4">Tax Amount</th>
                <th className="py-3.5 px-4">Grand Total</th>
                <th className="py-3.5 px-4">FBR Fiscal Status</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center">
                    <RefreshCw className="w-6 h-6 text-emerald-600 animate-spin mx-auto" />
                  </td>
                </tr>
              ) : currentNotes.length > 0 ? (
                currentNotes.map((note) => {
                  const origInv = invoices.find(i => i.id === note.original_invoice_id);
                  const isAccepted = !!note.fbr_invoice_number;

                  return (
                    <tr key={note.id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                        {note.note_number}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500">
                        {new Date(note.note_date).toLocaleDateString()}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="font-mono font-semibold text-slate-800">
                          {origInv ? origInv.invoice_number : note.original_invoice_id.slice(0, 8)}
                        </span>
                        {origInv && (
                          <div className="text-[10px] text-slate-400">Total: PKR {Number(origInv.grand_total).toLocaleString()}</div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 max-w-[180px] truncate" title={note.reason}>
                        {note.reason}
                      </td>
                      <td className="py-3.5 px-4 font-medium">
                        PKR {Number(note.taxable_amount).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-emerald-700">
                        PKR {Number(note.total_tax).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4 font-bold text-slate-900">
                        PKR {Number(note.grand_total).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4">
                        {isAccepted ? (
                          <div>
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                              <CheckCircle2 className="w-3 h-3" />
                              VERIFIED
                            </span>
                            <div className="font-mono text-[10px] text-slate-400 mt-0.5 truncate max-w-[120px]" title={note.fbr_invoice_number}>
                              {note.fbr_invoice_number}
                            </div>
                          </div>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                            PENDING SUBMISSION
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleDownloadPdf(note.id, activeTab)}
                            disabled={actionLoadingId === note.id}
                            className="flex items-center gap-1 px-2.5 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-medium border border-slate-200 transition-colors"
                            title="Download Legal Note PDF"
                          >
                            <FileText className="w-3.5 h-3.5 text-slate-500" />
                            <span>PDF</span>
                          </button>

                          {!isAccepted && (
                            <button
                              onClick={() => handleQueueSubmit(note.id, activeTab)}
                              disabled={actionLoadingId === note.id}
                              className="flex items-center gap-1 px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
                              title="Transmit to FBR Gateway"
                            >
                              <Send className="w-3 h-3" />
                              <span>{actionLoadingId === note.id ? 'Queueing...' : 'Submit'}</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-400 text-xs">
                    No {activeTab.toLowerCase()} notes registered yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Create Credit or Debit Note */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="font-bold text-slate-900 text-base">
                  Issue New {activeTab === 'CREDIT' ? 'Tax Credit Note' : 'Tax Debit Note'}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Link with an existing valid digital invoice for legal tax adjustment.
                </p>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                ✕
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-xl flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateNote} className="space-y-4 text-xs">
              {/* Select Original Invoice */}
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Original Tax Invoice <span className="text-rose-500">*</span>
                </label>
                <select
                  value={selectedInvoiceId}
                  onChange={(e) => handleInvoiceSelect(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white font-mono text-slate-800"
                  required
                >
                  <option value="">-- Select Original Invoice to Reconcile --</option>
                  {invoices.map((inv) => (
                    <option key={inv.id} value={inv.id}>
                      {inv.invoice_number} | {inv.buyer_name} | PKR {Number(inv.grand_total).toLocaleString()} ({inv.fbr_status})
                    </option>
                  ))}
                </select>
              </div>

              {/* Cumulative Reconciliation Card */}
              {loadingReconciliation ? (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-center gap-2 text-slate-500">
                  <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                  <span>Checking original invoice cumulative credit history...</span>
                </div>
              ) : reconciliation ? (
                <div className="p-4 bg-emerald-50/60 border border-emerald-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-emerald-900">Reconciliation Analysis:</span>
                    <span className="font-mono text-slate-700">{reconciliation.invoice_number}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 pt-1 text-[11px]">
                    <div>
                      <span className="text-slate-500">Original Total:</span>
                      <p className="font-mono font-bold text-slate-800">PKR {Number(reconciliation.invoice_grand_total).toLocaleString()}</p>
                    </div>
                    <div>
                      <span className="text-slate-500">Already Credited:</span>
                      <p className="font-mono font-bold text-amber-700">PKR {Number(reconciliation.total_previously_credited).toLocaleString()}</p>
                    </div>
                    <div>
                      <span className="text-slate-500">Allowable Ceiling:</span>
                      <p className="font-mono font-bold text-emerald-700">PKR {Number(reconciliation.remaining_creditable_amount).toLocaleString()}</p>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Reason */}
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Reason for Adjustment <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Return of damaged goods / Discount correction"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-slate-800"
                  required
                />
              </div>

              {/* Amounts */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Taxable Amount (PKR) <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={taxableAmount || ''}
                    onChange={(e) => handleTaxableChange(parseFloat(e.target.value) || 0)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono text-slate-800"
                    required
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Sales Tax (18% PKR)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={salesTax || ''}
                    onChange={(e) => setSalesTax(parseFloat(e.target.value) || 0)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono text-slate-800"
                    required
                  />
                </div>
              </div>

              {/* Grand Total Preview */}
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs font-bold text-slate-800">
                <span>Total Adjustment Grand Amount:</span>
                <span className="font-mono text-emerald-700 text-sm">
                  PKR {(Number(taxableAmount || 0) + Number(salesTax || 0)).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </div>

              {/* Auto submit checkbox */}
              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="autoSubmit"
                  checked={autoSubmit}
                  onChange={(e) => setAutoSubmit(e.target.checked)}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                />
                <label htmlFor="autoSubmit" className="font-semibold text-slate-700 cursor-pointer">
                  Automatically enqueue submission to FBR gateway upon creation
                </label>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold shadow-sm transition-colors disabled:opacity-50"
                >
                  {submitting ? 'Creating...' : `Issue ${activeTab === 'CREDIT' ? 'Credit Note' : 'Debit Note'}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
