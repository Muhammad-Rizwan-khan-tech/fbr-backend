import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  Plus, 
  Trash2, 
  Save, 
  Send, 
  ShieldCheck, 
  AlertCircle,
  Calculator
} from 'lucide-react';
import { masterApi } from '../api/master';
import { invoicesApi } from '../api/invoices';
import { Customer, Product, Branch } from '../types';

interface CreateInvoicePageProps {
  onBack: () => void;
  onSuccess: (invoiceId: string) => void;
}

interface FormLineItem {
  product_id?: string;
  item_code: string;
  description: string;
  hs_code: string;
  quantity: number;
  uom: string;
  unit_price: number;
  discount: number;
  tax_rate: number;
  sale_type: string;
}

export const CreateInvoicePage: React.FC<CreateInvoicePageProps> = ({ onBack, onSuccess }) => {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [fbrMode, setFbrMode] = useState<'DEMO' | 'SANDBOX' | 'PRODUCTION'>('DEMO');
  const [scenarioId, setScenarioId] = useState('SN001');
  const [hsQuery, setHsQuery] = useState('');
  const [hsOptions, setHsOptions] = useState<Array<{code: string; description: string}>>([]);
  const [hsSource, setHsSource] = useState('');
  const [hsLoading, setHsLoading] = useState(false);

  // Form State
  const [selectedBranchId, setSelectedBranchId] = useState('');
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [invoiceType, setInvoiceType] = useState('TAX_INVOICE');
  const [referenceNumber, setReferenceNumber] = useState('');
  const [paymentTerms, setPaymentTerms] = useState('Net 30 Days');
  const [notes, setNotes] = useState('Official FBR Digital Invoicing Transaction');
  const [otherCharges, setOtherCharges] = useState(0);

  // Line items state
  const [items, setItems] = useState<FormLineItem[]>([
    {
      item_code: '',
      description: '',
      hs_code: '',
      quantity: 1,
      uom: 'NOS',
      unit_price: 0,
      discount: 0,
      tax_rate: 18.00,
      sale_type: 'STANDARD',
    },
  ]);

  useEffect(() => {
    async function loadMasterData() {
      try {
        const [bList, cList, pList, organization] = await Promise.all([
          masterApi.getBranches(),
          masterApi.getCustomers(),
          masterApi.getProducts(),
          masterApi.getOrganization(),
        ]);
        setFbrMode(organization.settings?.fbr_mode || 'DEMO');
        setBranches(bList);
        setCustomers(cList);
        setProducts(pList);

        if (bList.length > 0) setSelectedBranchId(bList[0].id);
        if (cList.length > 0) setSelectedCustomerId(cList[0].id);
        if (pList.length > 0) {
          setItems([
            {
              product_id: pList[0].id,
              item_code: pList[0].item_code,
              description: pList[0].name,
              hs_code: pList[0].hs_code,
              quantity: 1,
              uom: pList[0].uom,
              unit_price: Number(pList[0].unit_price),
              discount: 0,
              tax_rate: Number(pList[0].tax_rate),
              sale_type: pList[0].sale_type,
            },
          ]);
        }
      } catch (err) {
        console.error('Failed to load invoice form master data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadMasterData();
  }, []);

  // Autocomplete from the PRAL item catalog (or clearly labeled fallback).
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      setHsLoading(true);
      try {
        const data = await masterApi.getPRALHSCodes(hsQuery);
        if (!active) return;
        setHsOptions((data.items || []).map((entry) => ({
          code: String(entry.hS_CODE || entry.hs_code || entry.code || ''),
          description: String(entry.description || entry.label || ''),
        })).filter((entry) => entry.code.length > 0));
        setHsSource(data.official_live_verified ? 'Official PRAL live catalog' :
          `${data.source || 'Local/fixture catalog'} — not live verified`);
      } catch {
        try {
          const local = await masterApi.getHSCodes(hsQuery);
          if (!active) return;
          setHsOptions(local.map((entry) => ({ code: String(entry.code), description: String(entry.description || '') })));
          setHsSource('Local catalog only — not verified with PRAL');
        } catch {
          if (active) {
            setHsOptions([]);
            setHsSource('HS catalog unavailable. Please enter an independently confirmed code.');
          }
        }
      } finally {
        if (active) setHsLoading(false);
      }
    }, 350);
    return () => { active = false; clearTimeout(timer); };
  }, [hsQuery]);

  const handleProductSelect = (index: number, productId: string) => {
    const prod = products.find((p) => p.id === productId);
    if (!prod) return;

    const newItems = [...items];
    newItems[index] = {
      ...newItems[index],
      product_id: prod.id,
      item_code: prod.item_code,
      description: prod.name,
      hs_code: prod.hs_code,
      uom: prod.uom,
      unit_price: Number(prod.unit_price),
      tax_rate: Number(prod.tax_rate),
      sale_type: prod.sale_type,
    };
    setItems(newItems);
  };

  const handleLineChange = (index: number, field: keyof FormLineItem, value: any) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: value };
    setItems(newItems);
  };

  const handleAddLine = () => {
    const defaultProd = products[0];
    setItems([
      ...items,
      {
        product_id: defaultProd?.id,
        item_code: defaultProd?.item_code || '',
        description: defaultProd?.name || '',
        hs_code: defaultProd?.hs_code || '',
        quantity: 1,
        uom: defaultProd?.uom || 'NOS',
        unit_price: defaultProd ? Number(defaultProd.unit_price) : 0,
        discount: 0,
        tax_rate: defaultProd ? Number(defaultProd.tax_rate) : 18.00,
        sale_type: 'STANDARD',
      },
    ]);
  };

  const handleRemoveLine = (index: number) => {
    if (items.length <= 1) return;
    setItems(items.filter((_, idx) => idx !== index));
  };

  // Live Totals Calculation
  let subtotal = 0;
  let totalDiscount = 0;
  let taxableAmount = 0;
  let totalTax = 0;

  items.forEach((itm) => {
    const gross = (itm.quantity || 0) * (itm.unit_price || 0);
    const disc = itm.discount || 0;
    const taxable = Math.max(0, gross - disc);
    const tax = taxable * ((itm.tax_rate || 0) / 100);

    subtotal += gross;
    totalDiscount += disc;
    taxableAmount += taxable;
    totalTax += tax;
  });

  const grandTotal = taxableAmount + totalTax + Number(otherCharges || 0);

  const selectedCustomer = customers.find((c) => c.id === selectedCustomerId);

  const handleSubmit = async (andSubmitToFBR: boolean) => {
    if (!selectedBranchId) {
      alert('Please select a branch');
      return;
    }
    if (!selectedCustomerId) {
      alert('Please select a customer');
      return;
    }
    if (items.some((i) => !i.hs_code || i.quantity <= 0)) {
      alert('All line items must have a valid Pakistan HS Code and quantity > 0');
      return;
    }

    if (fbrMode === 'SANDBOX' && !/^SN\d{3}$/.test(scenarioId)) {
      alert('Sandbox scenario ID must look like SN001 (choose the scenario assigned by PRAL).');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        branch_id: selectedBranchId,
        customer_id: selectedCustomerId,
        invoice_type: invoiceType,
        reference_number: referenceNumber || undefined,
        scenario_id: fbrMode === 'SANDBOX' ? scenarioId : undefined,
        payment_terms: paymentTerms,
        notes: notes,
        other_charges: otherCharges,
        items: items.map((i) => ({
          product_id: i.product_id,
          item_code: i.item_code,
          description: i.description,
          hs_code: i.hs_code,
          quantity: Number(i.quantity),
          uom: i.uom,
          unit_price: Number(i.unit_price),
          discount: Number(i.discount),
          tax_rate: Number(i.tax_rate),
          sale_type: i.sale_type,
        })),
      };

      const createdInvoice = await invoicesApi.createInvoice(payload);

      if (andSubmitToFBR) {
        try {
          const result = await invoicesApi.submitToFBR(createdInvoice.id, 'AUTO');
          if (result.status !== 'VALID') {
            alert(`Invoice saved, but FBR did not accept it. Status: ${result.status}. ${result.error_message || ''}`);
          } else if (fbrMode === 'SANDBOX') {
            alert('Invoice accepted in FBR Sandbox only — this is NOT a production tax invoice.');
          } else if (fbrMode === 'DEMO') {
            alert('DEMO simulated submission — NOT an official FBR invoice.');
          }
        } catch (err: any) {
          alert(`Invoice saved as ${createdInvoice.invoice_number}, but FBR submission failed: ${err.message}`);
        }
      }

      onSuccess(createdInvoice.id);
    } catch (err: any) {
      alert(`Error creating invoice: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="p-12 text-center text-xs text-slate-500">Loading master data...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 border border-slate-200 hover:bg-slate-50 rounded-xl text-slate-600 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="text-lg font-bold text-slate-900">Create Pakistan Tax Invoice</h2>
            <p className="text-xs text-slate-500">Sales Tax Act 1990 & FBR Digital Invoicing Specification</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => handleSubmit(false)}
            disabled={submitting}
            className="flex items-center gap-2 px-4 py-2 border border-slate-200 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700 transition-colors disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>Save Draft</span>
          </button>
          <button
            onClick={() => handleSubmit(true)}
            disabled={submitting}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm shadow-emerald-200 transition-colors disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            <span>{submitting ? 'Processing...' : fbrMode === 'SANDBOX' ? 'Save & Submit to FBR Sandbox' : fbrMode === 'DEMO' ? 'Save & Run Demo' : 'Save & Submit to FBR Production'}</span>
          </button>
        </div>
      </div>

      {/* Invoice Meta Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Branch & Invoice Attributes */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Branch & Invoice Details</h3>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Issuing Branch</label>
            <select
              value={selectedBranchId}
              onChange={(e) => setSelectedBranchId(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-emerald-500"
            >
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.branch_name} ({b.branch_code}) - {b.city}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Invoice Type</label>
            <select
              value={invoiceType}
              onChange={(e) => setInvoiceType(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-emerald-500"
            >
              <option value="TAX_INVOICE">Standard Tax Invoice (Registered / Commercial)</option>
              <option value="RETAIL_INVOICE">Retail POS Invoice (B2C)</option>
              <option value="EXPORT_INVOICE">Zero-Rated Export Invoice</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Reference / PO #</label>
            <input
              type="text"
              placeholder="e.g. PO-2026-9041 (use 'ERR-TIMEOUT' or 'ERR-REJ' to test mock error scenarios)"
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        {/* Customer / Buyer Master Selection */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Customer / Buyer</h3>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Select Customer</label>
            <select
              value={selectedCustomerId}
              onChange={(e) => setSelectedCustomerId(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-emerald-500 font-medium"
            >
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} (NTN: {c.ntn || 'N/A'})
                </option>
              ))}
            </select>
          </div>

          {selectedCustomer && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Buyer NTN:</span>
                <span className="font-semibold text-slate-800">{selectedCustomer.ntn || 'Unregistered'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">STRN:</span>
                <span className="font-semibold text-slate-800">{selectedCustomer.strn || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Province / City:</span>
                <span className="font-semibold text-slate-800">{selectedCustomer.province}, {selectedCustomer.city}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Reg Type:</span>
                <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 rounded font-semibold text-[10px]">
                  {selectedCustomer.registration_type}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Terms and Notes */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Terms & Compliance Notes</h3>
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Payment Terms</label>
            <input
              type="text"
              value={paymentTerms}
              onChange={(e) => setPaymentTerms(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Notes / Special Instructions</label>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>
      </div>

      {fbrMode === 'SANDBOX' && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900">
          <label className="block font-semibold mb-2">PRAL Sandbox Scenario ID (required)</label>
          <input
            value={scenarioId}
            onChange={(e) => setScenarioId(e.target.value.toUpperCase())}
            placeholder="SN001"
            maxLength={5}
            className="p-2 border border-amber-300 rounded font-mono bg-white"
          />
          <p className="mt-2">Use the scenario assigned for your business activity (SN001–SN028). Sandbox acceptance does not create a production invoice.</p>
        </div>
      )}

      {/* Dynamic Item Grid */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Line Items & FBR Tax Classification</h3>
            <p className="text-xs text-slate-400 mt-0.5">Pakistan HS codes, unit prices, discounts, and sales tax rate breakdown</p>
            <p className="text-[11px] mt-1 text-amber-700">{hsLoading ? 'Searching HS catalog…' : hsSource || 'HS search loads from available reference data. Verify classification before submission.'}</p>
          </div>
          <button
            onClick={handleAddLine}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Item</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
              <tr>
                <th className="py-2.5 px-3">Item / Product</th>
                <th className="py-2.5 px-3 w-32">HS Code</th>
                <th className="py-2.5 px-3 w-20">Qty</th>
                <th className="py-2.5 px-3 w-20">UOM</th>
                <th className="py-2.5 px-3 w-28">Unit Price</th>
                <th className="py-2.5 px-3 w-24">Discount</th>
                <th className="py-2.5 px-3 w-24">Tax Rate</th>
                <th className="py-2.5 px-3 w-28">Tax Amount</th>
                <th className="py-2.5 px-3 w-32">Line Total</th>
                <th className="py-2.5 px-3 w-10 text-center"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((item, idx) => {
                const lineGross = (item.quantity || 0) * (item.unit_price || 0);
                const lineTaxable = Math.max(0, lineGross - (item.discount || 0));
                const lineTax = lineTaxable * ((item.tax_rate || 0) / 100);
                const lineTotal = lineTaxable + lineTax;

                return (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="py-2.5 px-3">
                      <select
                        value={item.product_id || ''}
                        onChange={(e) => handleProductSelect(idx, e.target.value)}
                        className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded bg-white focus:ring-1 focus:ring-emerald-500 mb-1"
                      >
                        <option value="">-- Custom Item --</option>
                        {products.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name} ({p.item_code})
                          </option>
                        ))}
                      </select>
                      <input
                        type="text"
                        value={item.description}
                        onChange={(e) => handleLineChange(idx, 'description', e.target.value)}
                        placeholder="Description..."
                        className="w-full px-2 py-1 text-[11px] border border-slate-200 rounded text-slate-600"
                      />
                    </td>
                    <td className="py-2.5 px-3">
                      <input
                        type="text"
                        list={`hs-options-${idx}`}
                        value={item.hs_code}
                        onFocus={() => setHsQuery(item.hs_code)}
                        onChange={(e) => {
                          handleLineChange(idx, 'hs_code', e.target.value);
                          setHsQuery(e.target.value);
                        }}
                        placeholder="Search HS code..."
                        className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded font-mono font-medium"
                      />
                      <datalist id={`hs-options-${idx}`}>
                        {hsOptions.map((entry) => (
                          <option key={entry.code} value={entry.code} label={entry.description} />
                        ))}
                      </datalist>
                    </td>
                    <td className="py-2.5 px-3">
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={item.quantity}
                        onChange={(e) => handleLineChange(idx, 'quantity', parseFloat(e.target.value) || 0)}
                        className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded text-right font-medium"
                      />
                    </td>
                    <td className="py-2.5 px-3">
                      <select
                        value={item.uom}
                        onChange={(e) => handleLineChange(idx, 'uom', e.target.value)}
                        className="w-full px-1.5 py-1.5 text-xs border border-slate-200 rounded bg-white"
                      >
                        <option value="NOS">NOS</option>
                        <option value="KGS">KGS</option>
                        <option value="LTR">LTR</option>
                        <option value="MTR">MTR</option>
                        <option value="BOX">BOX</option>
                        <option value="BAG">BAG</option>
                      </select>
                    </td>
                    <td className="py-2.5 px-3">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={item.unit_price}
                        onChange={(e) => handleLineChange(idx, 'unit_price', parseFloat(e.target.value) || 0)}
                        className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded text-right font-medium"
                      />
                    </td>
                    <td className="py-2.5 px-3">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={item.discount}
                        onChange={(e) => handleLineChange(idx, 'discount', parseFloat(e.target.value) || 0)}
                        className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded text-right"
                      />
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          step="0.1"
                          value={item.tax_rate}
                          onChange={(e) => handleLineChange(idx, 'tax_rate', parseFloat(e.target.value) || 0)}
                          className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded text-right font-medium"
                        />
                        <span className="text-slate-400">%</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-emerald-700 text-right">
                      {lineTax.toFixed(2)}
                    </td>
                    <td className="py-2.5 px-3 font-bold text-slate-900 text-right">
                      {lineTotal.toFixed(2)}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => handleRemoveLine(idx)}
                        disabled={items.length <= 1}
                        className="p-1 text-slate-300 hover:text-rose-600 rounded disabled:opacity-30"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Totals Summary */}
        <div className="border-t border-slate-100 pt-6 flex justify-end">
          <div className="w-full sm:w-80 bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2 text-xs">
            <div className="flex justify-between text-slate-500">
              <span>Gross Subtotal:</span>
              <span className="font-semibold text-slate-800">PKR {subtotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Total Discount:</span>
              <span className="font-semibold text-rose-600">- PKR {totalDiscount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Taxable Amount:</span>
              <span className="font-semibold text-slate-800">PKR {taxableAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Sales Tax (GST):</span>
              <span className="font-bold text-emerald-700">+ PKR {totalTax.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
            <div className="flex justify-between items-center text-slate-500 pt-1">
              <span>Other Charges:</span>
              <input
                type="number"
                min="0"
                value={otherCharges}
                onChange={(e) => setOtherCharges(parseFloat(e.target.value) || 0)}
                className="w-24 px-2 py-1 text-xs border border-slate-200 rounded text-right bg-white"
              />
            </div>
            <div className="flex justify-between items-center text-slate-900 border-t border-slate-200 pt-2 font-bold text-sm">
              <span>Grand Total:</span>
              <span className="text-emerald-700">PKR {grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
