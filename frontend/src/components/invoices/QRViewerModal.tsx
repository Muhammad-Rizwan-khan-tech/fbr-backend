import React, { useEffect, useState } from 'react';
import { X, Printer, ShieldCheck, AlertTriangle } from 'lucide-react';
import { Invoice } from '../../types';
import { apiFetchBlob } from '../../api/client';

interface QRViewerModalProps {
  invoice: Invoice | null;
  onClose: () => void;
}

export const QRViewerModal: React.FC<QRViewerModalProps> = ({ invoice, onClose }) => {
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!invoice) return;
    let active = true;
    let objectUrl: string | null = null;
    setLoading(true);
    setQrUrl(null);
    setError('');

    apiFetchBlob(`/invoices/${invoice.id}/qr`)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        objectUrl = url;
        if (active) setQrUrl(url);
        else URL.revokeObjectURL(url);
      })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [invoice?.id]);

  if (!invoice) return null;

  const isSandbox = invoice.fbr_environment === 'SANDBOX';
  const isOfficial = invoice.fbr_status === 'VALID' &&
    !!invoice.fbr_invoice_number && !invoice.fbr_is_simulated &&
    invoice.fbr_environment !== 'DEMO';

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-100">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2 text-slate-800">
            <ShieldCheck className="w-5 h-5 text-emerald-600" />
            <h3 className="font-bold text-sm">FBR Invoice Reference QR</h3>
          </div>
          <button onClick={onClose} aria-label="Close QR viewer" className="p-1 rounded-lg hover:bg-slate-100 text-slate-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        {isOfficial ? (
          <div className="py-6 flex flex-col items-center text-center">
            <div className="w-48 h-48 border rounded-xl flex justify-center items-center bg-white">
              {loading && <p className="text-xs text-slate-500">Loading QR…</p>}
              {qrUrl && <img src={qrUrl} alt="Invoice reference QR" className="w-44 h-44 object-contain" />}
              {error && <AlertTriangle className="w-8 h-8 text-rose-500" />}
            </div>
            {error && <p role="alert" className="mt-3 text-xs text-rose-700">{error}</p>}
            <p className="mt-4 text-xs font-semibold text-emerald-800">
              {isSandbox ? 'Accepted in FBR Sandbox (test environment)' : 'FBR submission accepted'}
            </p>
            <p className="mt-2 text-[11px] text-slate-500">
              This QR contains invoice reference information. It does not independently certify an FBR digital signature.
            </p>
            <p className="mt-3 font-mono text-sm text-slate-800 break-all">{invoice.fbr_invoice_number}</p>
          </div>
        ) : (
          <div className="py-8 text-center">
            <AlertTriangle className="mx-auto w-8 h-8 text-amber-500" />
            <p className="mt-3 text-sm font-semibold">No verified invoice QR available</p>
            <p className="mt-2 text-xs text-slate-600">The invoice must first receive an accepted, non-simulated FBR invoice number.</p>
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            onClick={() => window.print()}
            disabled={!qrUrl || !isOfficial}
            className="flex-1 flex items-center justify-center gap-2 py-2 px-4 border border-slate-200 rounded-lg text-xs font-semibold disabled:opacity-50"
          >
            <Printer className="w-4 h-4" /> Print
          </button>
          <button onClick={onClose} className="flex-1 py-2 px-4 bg-emerald-600 text-white rounded-lg text-xs font-semibold">
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
