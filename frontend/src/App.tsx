import React, { useState } from 'react';
import { useAuth } from './context/AuthContext';
import { Shell } from './components/layout/Shell';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { InvoicesPage } from './pages/InvoicesPage';
import { CreateInvoicePage } from './pages/CreateInvoicePage';
import { FBRSubmissionCenterPage } from './pages/FBRSubmissionCenterPage';
import { CustomersPage } from './pages/CustomersPage';
import { ProductsPage } from './pages/ProductsPage';
import { TaxConfigPage } from './pages/TaxConfigPage';
import { SettingsPage } from './pages/SettingsPage';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { CreditDebitNotesPage } from './pages/CreditDebitNotesPage';
import { DeveloperPortalPage } from './pages/DeveloperPortalPage';

export const App: React.FC = () => {
  const { token, isLoading } = useAuth();
  const [currentTab, setCurrentTab] = useState<string>('dashboard');

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white text-xs font-semibold">
        Loading FBR Invoice Cloud...
      </div>
    );
  }

  if (!token) {
    return <LoginPage />;
  }

  const renderContent = () => {
    switch (currentTab) {
      case 'dashboard':
        return (
          <DashboardPage
            onNavigate={(tab) => setCurrentTab(tab)}
            onNewInvoice={() => setCurrentTab('create-invoice')}
          />
        );
      case 'invoices':
        return <InvoicesPage onNewInvoice={() => setCurrentTab('create-invoice')} />;
      case 'notes':
        return <CreditDebitNotesPage />;
      case 'create-invoice':
        return (
          <CreateInvoicePage
            onBack={() => setCurrentTab('invoices')}
            onSuccess={(_invoiceId) => setCurrentTab('invoices')}
          />
        );
      case 'fbr':
        return <FBRSubmissionCenterPage />;
      case 'customers':
        return <CustomersPage />;
      case 'products':
        return <ProductsPage />;
      case 'tax':
        return <TaxConfigPage />;
      case 'settings':
        return <SettingsPage />;
      case 'audit':
        return <AuditLogsPage />;
      case 'developer':
        return <DeveloperPortalPage />;
      default:
        return (
          <DashboardPage
            onNavigate={(tab) => setCurrentTab(tab)}
            onNewInvoice={() => setCurrentTab('create-invoice')}
          />
        );
    }
  };

  return (
    <Shell
      currentTab={currentTab === 'create-invoice' ? 'invoices' : currentTab}
      setCurrentTab={setCurrentTab}
      onNewInvoiceClick={currentTab !== 'create-invoice' ? () => setCurrentTab('create-invoice') : undefined}
    >
      {renderContent()}
    </Shell>
  );
};
