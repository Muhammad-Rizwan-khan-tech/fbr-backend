import React from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

interface ShellProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  children: React.ReactNode;
  onNewInvoiceClick?: () => void;
}

export const Shell: React.FC<ShellProps> = ({
  currentTab,
  setCurrentTab,
  children,
  onNewInvoiceClick
}) => {
  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar currentTab={currentTab} setCurrentTab={setCurrentTab} />
      <div className="flex-1 flex flex-col pl-64">
        <Header onNewInvoiceClick={onNewInvoiceClick} />
        <main className="p-8 flex-1">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
