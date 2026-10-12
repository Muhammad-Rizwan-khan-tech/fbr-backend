import React, { useState } from 'react';
import { useAuth } from './context/AuthContext';
import { Shell } from './components/layout/Shell';
import { LoginPage } from './pages/LoginPage';
import { ActivationPage } from './pages/ActivationPage';
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
  const { token, isActivated, isLoading } = useAuth();
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [showLogin, setShowLogin] = useState<boolean>(() => {
    // If the device already has token or isActivated flag in storage, default to login view
    return isActivated;
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white text-xs font-semibold space-y-3">
        <div className="w-8 h-8 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin"></div>
        <p className="text-slate-300">Initializing FBR Invoice Cloud Desktop Engine...</p>
      </div>
    );
  }

  // Not authenticated: Show either Activation screen or Login screen
  if (!token) {
    if (showLogin) {
      return <LoginPage onSwitchToActivation={() => setShowLogin(false)} />;
    }
    return <ActivationPage onSwitchToLogin={() => setShowLogin(true)} />;
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
