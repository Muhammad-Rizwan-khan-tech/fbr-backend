@extends('layouts.app')

@section('title', 'Authorized Terminals')
@section('page_title', 'Authorized Desktop Workstations & Terminals')

@section('content')
<div class="space-y-6">
    <div class="bg-slate-950 border border-slate-800 rounded-2xl p-5 flex items-center justify-between">
        <div>
            <h2 class="text-sm font-bold text-white">Global Client Device Registry</h2>
            <p class="text-xs text-slate-400">Desktop installations authenticated and bound to active customer licenses</p>
        </div>
        <span class="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            {{ count($devices) }} Terminals Bound
        </span>
    </div>

    <!-- Terminals Table -->
    <div class="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
                <thead class="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-900/40">
                    <tr>
                        <th class="py-3 px-4">Terminal Name</th>
                        <th class="py-3 px-4">Organization</th>
                        <th class="py-3 px-4">OS & Client Version</th>
                        <th class="py-3 px-4">Machine Fingerprint</th>
                        <th class="py-3 px-4">Last Active</th>
                        <th class="py-3 px-4">Status</th>
                        <th class="py-3 px-4 text-right">Action</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60 font-sans">
                    @forelse ($devices as $dev)
                        <tr class="hover:bg-slate-900/30 transition-colors">
                            <td class="py-3.5 px-4 font-bold text-white">
                                {{ $dev['device_name'] }}
                            </td>
                            <td class="py-3.5 px-4">
                                <a href="{{ route('organizations.show', $dev['organization_id']) }}" class="text-sky-400 hover:underline font-semibold">
                                    {{ $dev['organization_name'] ?? 'View Org' }}
                                </a>
                            </td>
                            <td class="py-3.5 px-4">
                                <div>{{ $dev['os_info'] ?? 'Windows' }}</div>
                                <span class="text-[10px] text-slate-500 font-mono">v{{ $dev['app_version'] }}</span>
                            </td>
                            <td class="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                                {{ $dev['device_fingerprint'] }}
                            </td>
                            <td class="py-3.5 px-4 text-slate-400 whitespace-nowrap">
                                {{ \Carbon\Carbon::parse($dev['last_seen_at'])->diffForHumans() }}
                            </td>
                            <td class="py-3.5 px-4">
                                @if (($dev['status'] ?? 'ACTIVE') === 'ACTIVE')
                                    <span class="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                        ACTIVE
                                    </span>
                                @else
                                    <span class="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                        REVOKED
                                    </span>
                                @endif
                            </td>
                            <td class="py-3.5 px-4 text-right">
                                @if (($dev['status'] ?? 'ACTIVE') === 'ACTIVE')
                                    <form method="POST" action="{{ route('devices.revoke', $dev['id']) }}" onsubmit="return confirm('Revoking this terminal will immediately terminate its access.');">
                                        @csrf
                                        @method('PUT')
                                        <input type="hidden" name="reason" value="Terminal revoked from Global Terminals view">
                                        <button type="submit" class="px-3 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-xs font-semibold transition-colors">
                                            Revoke Device
                                        </button>
                                    </form>
                                @else
                                    <span class="text-xs text-slate-500 font-medium">Revoked</span>
                                @endif
                            </td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="7" class="py-12 text-center text-slate-500">
                                No desktop terminals currently active across customer organizations.
                            </td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
    </div>
</div>
@endsection
