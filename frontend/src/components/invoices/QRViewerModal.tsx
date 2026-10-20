import React, { useEffect, useState } from 'react';
import { apiFetchImage } from '../../api/client';
import { X, CheckCircle2, Printer, ShieldCheck } from 'lucide-react';
import { Invoice } from '../../types';

interface QRViewerModalProps {
  invoice: Invoice | null;
  onClose: () => void;
}

export const QRViewerModal: React.FC<QRViewerModalProps> = ({ invoice, onClose }) => {
  const [qrImageUrl, setQrImageUrl] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);

  useEffect(() => {
    if (!invoice || invoice.fbr_status !== 'VALID') return;
    let active = true;
    let objectUrl: string | null = null;
    setQrImageUrl(null);
    setQrError(null);
    apiFetchImage(`/invoices/${invoice.id}/qr`)
      .then(blob => {
        objectUrl = URL.createObjectURL(blob);
        if (active) setQrImageUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch(err => { if (active) setQrError(err.message || 'QR unavailable'); });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [invoice?.id, invoice?.fbr_status]);

  if (!invoice) return null;
  const simulated = Boolean(invoice.fbr_is_simulated || invoice.fbr_environment === 'DEMO');

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-100 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2 text-emerald-800">
            <ShieldCheck className="w-5 h-5 text-emerald-600" />
            <h3 className="font-bold text-sm">{simulated ? "Demo Invoice QR (Not Official)" : "FBR Invoice QR"}</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 text-slate-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="py-6 flex flex-col items-center text-center">
          <div className="p-3 bg-white border-2 border-slate-200 rounded-xl shadow-inner mb-4">
            {qrImageUrl ? (
              <img src={qrImageUrl} alt={simulated ? 'Demo QR code' : 'FBR invoice QR code'} className="w-48 h-48 object-contain" />
            ) : (
              <div className="w-48 h-48 flex items-center justify-center text-xs text-slate-500 p-4">
                {qrError || 'Loading QR code...'}
              </div>
            )}
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full border border-emerald-200 mb-3">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{simulated ? "Simulated — not registered with FBR" : "Accepted by FBR"}</span>
          </div>

          <div className="text-xs font-mono font-bold text-slate-800 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 w-full mb-4 truncate">
            {invoice.fbr_invoice_number || 'FBR-VERIFICATION-PENDING'}
          </div>

          <div className="w-full text-left space-y-1.5 text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200">
            <div className="flex justify-between">
              <span className="text-slate-400">Invoice Number:</span>
              <span className="font-semibold text-slate-700">{invoice.invoice_number}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Seller NTN:</span>
              <span className="font-semibold text-slate-700">{invoice.seller_ntn}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Buyer NTN:</span>
              <span className="font-semibold text-slate-700">{invoice.buyer_ntn || 'Unregistered'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Taxable Amount:</span>
              <span className="font-semibold text-slate-700">PKR {Number(invoice.taxable_amount).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Total Sales Tax:</span>
              <span className="font-semibold text-emerald-700">PKR {Number(invoice.total_tax).toLocaleString()}</span>
            </div>
            <div className="flex justify-between border-t border-slate-200 pt-1.5">
              <span className="font-bold text-slate-700">Grand Total:</span>
              <span className="font-bold text-slate-900">PKR {Number(invoice.grand_total).toLocaleString()}</span>
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={() => window.print()}
            className="flex-1 flex items-center justify-center gap-2 py-2 px-4 border border-slate-200 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700"
          >
            <Printer className="w-4 h-4" />
            Print Receipt
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2 px-4 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-xs font-semibold text-white"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
