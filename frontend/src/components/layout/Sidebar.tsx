import React from 'react';
import { 
  LayoutDashboard, 
  FileText, 
  Send, 
  Users, 
  Package, 
  Sliders, 
  Settings, 
  ShieldAlert,
  Building2,
  CheckCircle2,
  Scale,
  Code2
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, setCurrentTab }) => {
  const { orgName } = useAuth();

  const navigation = [
    { name: 'Dashboard', id: 'dashboard', icon: LayoutDashboard },
    { name: 'Invoices', id: 'invoices', icon: FileText },
    { name: 'Credit & Debit Notes', id: 'notes', icon: Scale },
    { name: 'FBR Submission Center', id: 'fbr', icon: Send },
    { name: 'Customers (Buyers)', id: 'customers', icon: Users },
    { name: 'Products & HS Codes', id: 'products', icon: Package },
    { name: 'Tax Configuration', id: 'tax', icon: Sliders },
  ];

  const adminNav = [
    { name: 'Developer & ERP API', id: 'developer', icon: Code2 },
    { name: 'Settings & FBR Mode', id: 'settings', icon: Settings },
    { name: 'Audit Logs', id: 'audit', icon: ShieldAlert },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200 flex flex-col h-screen fixed left-0 top-0 z-30">
      {/* Brand Header */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-slate-100">
        <div className="w-9 h-9 rounded-lg bg-emerald-600 flex items-center justify-center text-white font-bold shadow-sm shadow-emerald-200">
          <CheckCircle2 className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-bold text-slate-900 leading-tight text-sm">FBR Invoice Cloud</h1>
          <p className="text-[10px] text-emerald-700 font-semibold uppercase tracking-wider">Digital Invoicing</p>
        </div>
      </div>

      {/* Tenant Context Card */}
      <div className="p-4 mx-3 my-3 bg-slate-50 border border-slate-200/80 rounded-xl">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-slate-500" />
          <span className="text-xs font-semibold text-slate-800 truncate" title={orgName}>
            {orgName}
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
          <span>NTN: 1234567-8</span>
          <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 font-medium rounded text-[10px]">
            DEMO ADAPTER
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-6">
        <div>
          <div className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
            Workspace
          </div>
          <nav className="space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-xs font-medium rounded-lg transition-colors text-left ${
                    isActive
                      ? 'bg-emerald-50 text-emerald-700 font-semibold'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-600' : 'text-slate-400'}`} />
                  {item.name}
                </button>
              );
            })}
          </nav>
        </div>

        <div>
          <div className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
            Administration
          </div>
          <nav className="space-y-1">
            {adminNav.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 text-xs font-medium rounded-lg transition-colors text-left ${
                    isActive
                      ? 'bg-emerald-50 text-emerald-700 font-semibold'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-600' : 'text-slate-400'}`} />
                  {item.name}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-100 text-center">
        <p className="text-[11px] text-slate-400">Pakistan Digital Tax Invoicing</p>
        <p className="text-[10px] text-slate-400">Sales Tax Act 1990 Compliant</p>
      </div>
    </aside>
  );
};
