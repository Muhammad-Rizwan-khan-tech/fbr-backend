@extends('layouts.app')

@section('title', $org['name'] ?? 'Organization Profile')
@section('page_title', $org['name'] ?? 'Organization Details')

@section('content')
<div class="space-y-6">
    <!-- Top Action Banner -->
    <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
            <div class="flex items-center gap-3">
                <h2 class="text-xl font-bold text-white tracking-tight">{{ $org['name'] }}</h2>
                @if (($org['status'] ?? 'ACTIVE') === 'ACTIVE')
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        ACTIVE
                    </span>
                @else
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        <span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                        SUSPENDED
                    </span>
                @endif
            </div>
            <p class="text-xs text-slate-400 font-mono mt-1">Tenant ID: {{ $org['id'] }} &bull; Slug: {{ $org['slug'] }}</p>
        </div>

        <div class="flex items-center gap-3">
            @if (($org['status'] ?? 'ACTIVE') === 'ACTIVE')
                <form method="POST" action="{{ route('organizations.status', $org['id']) }}" onsubmit="return confirm('Are you sure you want to suspend this organization? All client terminals will be disconnected.');">
                    @csrf
                    @method('PUT')
                    <input type="hidden" name="status" value="SUSPENDED">
                    <input type="hidden" name="reason" value="Suspended by Super Administrator">
                    <button type="submit" class="px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-xs font-semibold transition-colors">
                        Suspend Access
                    </button>
                </form>
            @else
                <form method="POST" action="{{ route('organizations.status', $org['id']) }}">
                    @csrf
                    @method('PUT')
                    <input type="hidden" name="status" value="ACTIVE">
                    <button type="submit" class="px-4 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 text-xs font-semibold transition-colors">
                        Restore Access
                    </button>
                </form>
            @endif

            <a href="{{ route('organizations.index') }}" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors">
                Back to List
            </a>
        </div>
    </div>

    <!-- 2 Column Grid: Left = License & Terminals, Right = FBR & Taxpayer Info -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left 2 Cols -->
        <div class="lg:col-span-2 space-y-6">
            <!-- Permanent License Card -->
            <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
                <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div class="flex items-center gap-2.5">
                        <span class="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
                            </svg>
                        </span>
                        <div>
                            <h3 class="text-sm font-bold text-white">Permanent License Management</h3>
                            <p class="text-[11px] text-slate-400">Lifetime access &bull; No subscription expiry</p>
                        </div>
                    </div>

                    <div class="flex items-center gap-2">
                        @if (isset($org['license']) && ($org['license']['status'] ?? '') === 'ACTIVE')
                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                ACTIVE &bull; PERMANENT
                            </span>
                        @else
                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                {{ $org['license']['status'] ?? 'REVOKED' }}
                            </span>
                        @endif
                    </div>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
                    <div>
                        <span class="text-slate-400 block text-[11px]">License Number</span>
                        <span class="font-mono text-emerald-400 font-bold text-sm">{{ $org['license']['license_number'] ?? 'N/A' }}</span>
                    </div>

                    <div>
                        <span class="text-slate-400 block text-[11px]">Authorized Workstations</span>
                        <span class="font-bold text-white text-sm">
                            {{ $org['stats']['active_devices_count'] ?? 0 }} / {{ $org['license']['max_devices'] ?? 5 }}
                        </span>
                    </div>

                    <div>
                        <span class="text-slate-400 block text-[11px]">Issued Timestamp</span>
                        <span class="text-slate-200">
                            {{ isset($org['license']['issued_at']) ? \Carbon\Carbon::parse($org['license']['issued_at'])->format('Y-m-d H:i') : 'N/A' }}
                        </span>
                    </div>
                </div>

                @if (isset($org['pending_activation_key']) && $org['pending_activation_key'])
                    <div class="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between">
                        <div>
                            <span class="font-bold block">Pending Activation Key Unredeemed:</span>
                            <span class="font-mono text-[11px]">{{ $org['pending_activation_key']['key_prefix'] }}...</span>
                            <span class="text-[10px] text-amber-400 block">Created: {{ \Carbon\Carbon::parse($org['pending_activation_key']['created_at'])->diffForHumans() }}</span>
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-200 font-semibold">Awaiting Client</span>
                    </div>
                @endif

                <div class="pt-2 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3">
                    <!-- Reissue Key Button and Form -->
                    <form method="POST" action="{{ route('licenses.reissue', $org['id']) }}" class="flex items-center gap-2">
                        @csrf
                        <input type="text" name="reason" placeholder="Reason for new key (e.g. 2nd Terminal)..." required class="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors w-64">
                        <button type="submit" class="px-3.5 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold transition-colors shrink-0">
                            Reissue Activation Key
                        </button>
                    </form>

                    <!-- Revoke / Restore License -->
                    @if (isset($org['license']['id']))
                        @if (($org['license']['status'] ?? '') === 'ACTIVE')
                            <form method="POST" action="{{ route('licenses.revoke', $org['license']['id']) }}" onsubmit="return confirm('Revoking permanent license will permanently disable invoicing on all terminals.');">
                                @csrf
                                @method('PUT')
                                <input type="hidden" name="reason" value="Administrative revocation from panel">
                                <button type="submit" class="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-xs font-semibold transition-colors">
                                    Revoke License
                                </button>
                            </form>
                        @else
                            <form method="POST" action="{{ route('licenses.restore', $org['license']['id']) }}">
                                @csrf
                                @method('PUT')
                                <button type="submit" class="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 text-xs font-semibold transition-colors">
                                    Restore License
                                </button>
                            </form>
                        @endif
                    @endif
                </div>
            </div>

            <!-- Authorized Desktop Workstations Table -->
            <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
                <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                        <h3 class="text-sm font-bold text-white">Authorized Client Terminals</h3>
                        <p class="text-[11px] text-slate-400">Windows workstations bound to this permanent license</p>
                    </div>
                    <span class="text-xs text-slate-400 font-semibold">{{ count($org['devices'] ?? []) }} Registered</span>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs text-slate-300">
                        <thead class="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-900/40">
                            <tr>
                                <th class="py-2.5 px-3">Terminal Name</th>
                                <th class="py-2.5 px-3">Operating System</th>
                                <th class="py-2.5 px-3">Hardware Fingerprint</th>
                                <th class="py-2.5 px-3">Last Seen</th>
                                <th class="py-2.5 px-3">Status</th>
                                <th class="py-2.5 px-3 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800/60">
                            @forelse ($org['devices'] ?? [] as $dev)
                                <tr class="hover:bg-slate-900/30 transition-colors">
                                    <td class="py-3 px-3">
                                        <span class="font-bold text-white block">{{ $dev['device_name'] }}</span>
                                        <span class="text-[10px] text-slate-400 font-mono">v{{ $dev['app_version'] }}</span>
                                    </td>
                                    <td class="py-3 px-3 text-slate-400">{{ $dev['os_info'] ?? 'Windows' }}</td>
                                    <td class="py-3 px-3 font-mono text-[11px] text-slate-400">{{ $dev['device_fingerprint'] }}</td>
                                    <td class="py-3 px-3 text-slate-400 whitespace-nowrap">
                                        {{ \Carbon\Carbon::parse($dev['last_seen_at'])->diffForHumans() }}
                                    </td>
                                    <td class="py-3 px-3">
                                        @if (($dev['status'] ?? 'ACTIVE') === 'ACTIVE')
                                            <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                                ACTIVE
                                            </span>
                                        @else
                                            <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                                REVOKED
                                            </span>
                                        @endif
                                    </td>
                                    <td class="py-3 px-3 text-right">
                                        @if (($dev['status'] ?? 'ACTIVE') === 'ACTIVE')
                                            <form method="POST" action="{{ route('devices.revoke', $dev['id']) }}" onsubmit="return confirm('Revoking this device will immediately disable its local session.');">
                                                @csrf
                                                @method('PUT')
                                                <input type="hidden" name="reason" value="Revoked by Super Administrator">
                                                <button type="submit" class="px-2.5 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-[10px] font-semibold transition-colors">
                                                    Revoke
                                                </button>
                                            </form>
                                        @else
                                            <span class="text-[10px] text-slate-500">Revoked</span>
                                        @endif
                                    </td>
                                </tr>
                            @empty
                                <tr>
                                    <td colspan="6" class="py-8 text-center text-slate-500">
                                        No desktop devices activated yet. Customer can activate using the one-time activation secret.
                                    </td>
                                </tr>
                            @endforelse
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Right 1 Col: FBR Credentials & Taxpayer Summary -->
        <div class="space-y-6">
            <!-- FBR Integration Credentials Card -->
            <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
                <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                        <h3 class="text-sm font-bold text-white">FBR Integration Configuration</h3>
                        <p class="text-[11px] text-slate-400">Server-side credentials encrypted at rest</p>
                    </div>
                    <form method="POST" action="{{ route('fbr.connection.test', $org['id']) }}">
                        @csrf
                        <button type="submit" class="px-3 py-1 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 border border-indigo-500/30 text-[11px] font-semibold transition-colors flex items-center gap-1">
                            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                            </svg>
                            <span>Test Live</span>
                        </button>
                    </form>
                </div>

                <div class="space-y-3 text-xs">
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400">Environment:</span>
                        <span class="font-bold text-sky-400">{{ $org['fbr_credentials']['environment'] ?? 'DEMO' }}</span>
                    </div>

                    <div class="flex items-center justify-between">
                        <span class="text-slate-400">Provider Adapter:</span>
                        <span class="font-bold text-white">{{ $org['fbr_credentials']['provider'] ?? 'MOCK' }}</span>
                    </div>

                    <div class="flex items-center justify-between">
                        <span class="text-slate-400">POS Identifier:</span>
                        <span class="font-mono text-slate-300">{{ $org['fbr_credentials']['fbr_pos_id'] ?? 'N/A' }}</span>
                    </div>

                    <div class="flex items-center justify-between">
                        <span class="text-slate-400">Masked API Key:</span>
                        <span class="font-mono text-emerald-400">{{ $org['fbr_credentials']['masked_api_key'] ?? 'None Configured' }}</span>
                    </div>

                    <div class="flex items-center justify-between">
                        <span class="text-slate-400">Masked Auth Token:</span>
                        <span class="font-mono text-emerald-400">{{ $org['fbr_credentials']['masked_auth_token'] ?? 'None Configured' }}</span>
                    </div>

                    <div class="flex items-center justify-between pt-1 border-t border-slate-900">
                        <span class="text-slate-400">Health / Test Status:</span>
                        <span class="font-semibold text-emerald-400">{{ $org['fbr_credentials']['status'] ?? 'UNTESTED' }}</span>
                    </div>
                </div>

                <!-- Update Credentials Toggle Form -->
                <details class="pt-3 border-t border-slate-800">
                    <summary class="text-xs font-semibold text-sky-400 cursor-pointer hover:underline">
                        Rotate / Update FBR Credentials
                    </summary>
                    <form method="POST" action="{{ route('fbr.credentials.update', $org['id']) }}" class="mt-3 space-y-3 text-xs">
                        @csrf
                        <div class="space-y-1">
                            <label class="text-slate-300 font-medium">Environment</label>
                            <select name="environment" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white">
                                <option value="DEMO" {{ ($org['fbr_credentials']['environment'] ?? '') === 'DEMO' ? 'selected' : '' }}>DEMO</option>
                                <option value="SANDBOX" {{ ($org['fbr_credentials']['environment'] ?? '') === 'SANDBOX' ? 'selected' : '' }}>SANDBOX</option>
                                <option value="PRODUCTION" {{ ($org['fbr_credentials']['environment'] ?? '') === 'PRODUCTION' ? 'selected' : '' }}>PRODUCTION</option>
                            </select>
                        </div>

                        <div class="space-y-1">
                            <label class="text-slate-300 font-medium">Provider</label>
                            <select name="provider" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white">
                                <option value="MOCK" {{ ($org['fbr_credentials']['provider'] ?? '') === 'MOCK' ? 'selected' : '' }}>MOCK</option>
                                <option value="SANDBOX" {{ ($org['fbr_credentials']['provider'] ?? '') === 'SANDBOX' ? 'selected' : '' }}>SANDBOX</option>
                                <option value="LICENSED_INTEGRATOR" {{ ($org['fbr_credentials']['provider'] ?? '') === 'LICENSED_INTEGRATOR' ? 'selected' : '' }}>LICENSED_INTEGRATOR</option>
                                <option value="PRODUCTION" {{ ($org['fbr_credentials']['provider'] ?? '') === 'PRODUCTION' ? 'selected' : '' }}>PRODUCTION</option>
                            </select>
                        </div>

                        <div class="space-y-1">
                            <label class="text-slate-300 font-medium">FBR POS ID</label>
                            <input type="text" name="fbr_pos_id" value="{{ $org['fbr_credentials']['fbr_pos_id'] ?? '' }}" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono">
                        </div>

                        <div class="space-y-1">
                            <label class="text-slate-300 font-medium">New API Key</label>
                            <input type="password" name="api_key" placeholder="Enter new secret key..." class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white">
                        </div>

                        <div class="space-y-1">
                            <label class="text-slate-300 font-medium">New Auth Token</label>
                            <input type="password" name="auth_token" placeholder="Enter new auth token..." class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white">
                        </div>

                        <button type="submit" class="w-full py-2 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded-lg text-xs transition-colors">
                            Save Encrypted Credentials
                        </button>
                    </form>
                </details>
            </div>

            <!-- Taxpayer Information Card -->
            <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
                <div class="border-b border-slate-800 pb-3">
                    <h3 class="text-sm font-bold text-white">Taxpayer Profile</h3>
                    <p class="text-[11px] text-slate-400">Registered tax identity</p>
                </div>

                <div class="space-y-2.5 text-xs">
                    <div>
                        <span class="text-slate-400 block text-[11px]">Legal Name</span>
                        <span class="font-bold text-white">{{ $org['taxpayer']['legal_name'] ?? $org['name'] }}</span>
                    </div>

                    <div>
                        <span class="text-slate-400 block text-[11px]">NTN</span>
                        <span class="font-mono text-slate-200">{{ $org['taxpayer']['ntn'] ?? 'N/A' }}</span>
                    </div>

                    <div>
                        <span class="text-slate-400 block text-[11px]">STRN</span>
                        <span class="font-mono text-slate-200">{{ $org['taxpayer']['strn'] ?? 'None Registered' }}</span>
                    </div>

                    <div>
                        <span class="text-slate-400 block text-[11px]">Jurisdiction</span>
                        <span class="text-slate-200">{{ $org['taxpayer']['province'] ?? 'Sindh' }}</span>
                    </div>

                    <div>
                        <span class="text-slate-400 block text-[11px]">Registered Address</span>
                        <span class="text-slate-300">{{ $org['taxpayer']['address'] ?? 'N/A' }}</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
@endsection
