@extends('layouts.app')

@section('title', 'Dashboard')
@section('page_title', 'Platform Operations Overview')

@section('content')
<div class="space-y-6">
    @if ($apiError)
        <div class="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between">
            <div class="flex items-center gap-2.5">
                <svg class="w-5 h-5 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                </svg>
                <span>Backend FastAPI is unreachable at {{ config('services.fastapi.url') }}. Metrics displayed may be cached or offline.</span>
            </div>
            <button onclick="location.reload()" class="px-2.5 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 rounded text-xs font-semibold">Retry</button>
        </div>
    @endif

    <!-- Metric KPI Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <!-- Organizations Card -->
        <div class="bg-slate-950 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-slate-400">ORGANIZATIONS</span>
                <span class="p-2 rounded-lg bg-sky-500/10 text-sky-400">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
                    </svg>
                </span>
            </div>
            <div class="flex items-baseline justify-between">
                <span class="text-3xl font-extrabold text-white">{{ $stats['total_organizations'] ?? 0 }}</span>
                <span class="text-xs font-semibold text-emerald-400">{{ $stats['active_organizations'] ?? 0 }} Active</span>
            </div>
            <div class="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-900">
                <span>Suspended: {{ $stats['suspended_organizations'] ?? 0 }}</span>
                <a href="{{ route('organizations.index') }}" class="text-sky-400 hover:underline">Manage &rarr;</a>
            </div>
        </div>

        <!-- Permanent Licenses Card -->
        <div class="bg-slate-950 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-slate-400">PERMANENT LICENSES</span>
                <span class="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
                    </svg>
                </span>
            </div>
            <div class="flex items-baseline justify-between">
                <span class="text-3xl font-extrabold text-white">{{ $stats['total_licenses'] ?? 0 }}</span>
                <span class="text-xs font-semibold text-emerald-400">{{ $stats['active_licenses'] ?? 0 }} Valid</span>
            </div>
            <div class="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-900">
                <span>Revoked: {{ $stats['revoked_licenses'] ?? 0 }}</span>
                <span class="text-emerald-400 font-medium">No Expiry Policy</span>
            </div>
        </div>

        <!-- Desktop Devices Card -->
        <div class="bg-slate-950 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-slate-400">ACTIVATED TERMINALS</span>
                <span class="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                    </svg>
                </span>
            </div>
            <div class="flex items-baseline justify-between">
                <span class="text-3xl font-extrabold text-white">{{ $stats['total_devices'] ?? 0 }}</span>
                <span class="text-xs font-semibold text-indigo-400">{{ $stats['active_devices'] ?? 0 }} Online</span>
            </div>
            <div class="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-900">
                <span>Hardware Bound</span>
                <a href="{{ route('devices.index') }}" class="text-sky-400 hover:underline">View All &rarr;</a>
            </div>
        </div>

        <!-- Invoices & FBR Submissions Card -->
        <div class="bg-slate-950 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-slate-400">FBR SUBMISSIONS</span>
                <span class="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                    </svg>
                </span>
            </div>
            <div class="flex items-baseline justify-between">
                <span class="text-3xl font-extrabold text-white">{{ $stats['invoices_total'] ?? 0 }}</span>
                <span class="text-xs font-semibold text-emerald-400">{{ $stats['invoices_submitted'] ?? 0 }} Transmitted</span>
            </div>
            <div class="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-900">
                <span>Failed: {{ $stats['invoices_failed'] ?? 0 }}</span>
                <span class="text-emerald-400 font-semibold">Integrator Active</span>
            </div>
        </div>
    </div>

    <!-- Quick Operations & Recent Activity Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left 2 Cols: Recent Administrative Activity -->
        <div class="lg:col-span-2 bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-sm font-bold text-white tracking-wide">AUDIT TRAIL & RECENT ACTIONS</h2>
                    <p class="text-xs text-slate-400">Immutable log of license issuance, revocations, and credentials configuration</p>
                </div>
                <a href="{{ route('audit.index') }}" class="text-xs font-semibold text-sky-400 hover:text-sky-300">View Full Log &rarr;</a>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-300">
                    <thead class="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-900/40">
                        <tr>
                            <th class="py-2.5 px-3">Timestamp</th>
                            <th class="py-2.5 px-3">Administrator</th>
                            <th class="py-2.5 px-3">Action</th>
                            <th class="py-2.5 px-3">Details</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800/60 font-mono">
                        @forelse ($recentAuditLogs as $log)
                            <tr class="hover:bg-slate-900/30 transition-colors">
                                <td class="py-2.5 px-3 whitespace-nowrap text-slate-400 text-[11px]">
                                    {{ \Carbon\Carbon::parse($log['created_at'])->format('Y-m-d H:i') }}
                                </td>
                                <td class="py-2.5 px-3 text-slate-300">{{ $log['admin_identity'] }}</td>
                                <td class="py-2.5 px-3">
                                    <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                                        {{ $log['action'] }}
                                    </span>
                                </td>
                                <td class="py-2.5 px-3 text-slate-300 truncate max-w-xs font-sans text-xs">
                                    {{ $log['details'] }}
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="4" class="py-8 text-center text-slate-500 font-sans">
                                    No administrative actions recorded yet.
                                </td>
                            </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Right 1 Col: Platform Security & Policy Info -->
        <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4 flex flex-col justify-between">
            <div class="space-y-4">
                <div>
                    <h2 class="text-sm font-bold text-white tracking-wide">PLATFORM SECURITY RULES</h2>
                    <p class="text-xs text-slate-400">Strict architectural policies enforced by FastAPI backend</p>
                </div>

                <div class="space-y-3 text-xs text-slate-300">
                    <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-2.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-400 mt-1.5 shrink-0"></span>
                        <div>
                            <strong class="text-white block">Permanent Licenses:</strong>
                            No recurring subscription expiry. Valid forever until explicitly revoked by an administrator.
                        </div>
                    </div>

                    <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-2.5">
                        <span class="w-2 h-2 rounded-full bg-sky-400 mt-1.5 shrink-0"></span>
                        <div>
                            <strong class="text-white block">FBR Credential Isolation:</strong>
                            Encrypted at rest with AES-256-GCM. Never transmitted to client desktop apps.
                        </div>
                    </div>

                    <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-2.5">
                        <span class="w-2 h-2 rounded-full bg-indigo-400 mt-1.5 shrink-0"></span>
                        <div>
                            <strong class="text-white block">Hardware Device Binding:</strong>
                            Desktop activation binds device machine GUID and SHA-256 fingerprint with replay prevention.
                        </div>
                    </div>
                </div>
            </div>

            <div class="pt-2 border-t border-slate-800">
                <a href="{{ route('organizations.create') }}" class="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-semibold shadow-sm transition-colors">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                    </svg>
                    <span>Register New Customer</span>
                </a>
            </div>
        </div>
    </div>
</div>
@endsection
