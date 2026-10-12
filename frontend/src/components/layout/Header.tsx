import React from 'react';
import { LogOut, User as UserIcon, ShieldCheck, Key } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface HeaderProps {
  onNewInvoiceClick?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onNewInvoiceClick }) => {
  const { user, license, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 bg-emerald-50 text-emerald-800 text-xs px-3 py-1 rounded-full font-medium border border-emerald-200">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>FBR Gateway: <strong>{license?.fbr_mode || 'DEMO'} MODE ACTIVE</strong></span>
        </div>

        {license?.license_number && (
          <div className="hidden md:flex items-center gap-1.5 bg-sky-50 text-sky-800 text-xs px-3 py-1 rounded-full font-medium border border-sky-200">
            <Key className="w-3.5 h-3.5 text-sky-600" />
            <span>Permanent License: <strong className="font-mono">{license.license_number}</strong></span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {onNewInvoiceClick && (
          <button
            onClick={onNewInvoiceClick}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-sm shadow-emerald-200 transition-colors"
          >
            + Create Tax Invoice
          </button>
        )}

        <div className="h-6 w-px bg-slate-200" />

        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-semibold text-xs border border-slate-200">
            <UserIcon className="w-4 h-4" />
          </div>
          <div className="text-left hidden sm:block">
            <div className="text-xs font-bold text-slate-800">{user?.full_name || 'Admin User'}</div>
            <div className="text-[10px] text-slate-400 capitalize">{user?.role?.replace('_', ' ') || 'Admin'}</div>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-slate-100 rounded-lg transition-colors ml-1"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
