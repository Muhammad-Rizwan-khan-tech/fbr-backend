import React from 'react';

interface StatusBadgeProps {
  status: string;
  type?: 'invoice' | 'fbr';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, type = 'fbr' }) => {
  const s = (status || '').toUpperCase();

  let bg = 'bg-slate-100 text-slate-700 border-slate-200';
  let dot = 'bg-slate-400';

  if (s === 'VALID' || s === 'SUBMITTED' || s === 'ACTIVE' || s === 'ACCEPTED' || s === 'COMPLETED') {
    bg = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    dot = 'bg-emerald-500';
  } else if (s === 'PENDING' || s === 'VALIDATING' || s === 'SUBMITTING' || s === 'PROCESSING' || s === 'QUEUED' || s === 'RETRYING') {
    bg = 'bg-amber-50 text-amber-700 border-amber-200';
    dot = 'bg-amber-500 animate-pulse';
  } else if (s === 'FAILED' || s === 'INVALID' || s === 'REJECTED') {
    bg = 'bg-rose-50 text-rose-700 border-rose-200';
    dot = 'bg-rose-500';
  } else if (s === 'READY') {
    bg = 'bg-blue-50 text-blue-700 border-blue-200';
    dot = 'bg-blue-500';
  } else if (s === 'NOT_SUBMITTED' || s === 'DRAFT') {
    bg = 'bg-slate-100 text-slate-600 border-slate-200';
    dot = 'bg-slate-400';
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`}></span>
      {s.replace('_', ' ')}
    </span>
  );
};
