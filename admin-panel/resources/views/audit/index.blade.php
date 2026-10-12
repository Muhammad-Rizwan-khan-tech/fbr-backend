@extends('layouts.app')

@section('title', 'Audit Logs')
@section('page_title', 'Administrative Audit Trail')

@section('content')
<div class="space-y-6">
    <div class="bg-slate-950 border border-slate-800 rounded-2xl p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
            <h2 class="text-sm font-bold text-white">Immutable Security Audit Logs</h2>
            <p class="text-xs text-slate-400">Detailed record of administrator logins, license grants, revocations, and FBR credential updates</p>
        </div>

        <form method="GET" action="{{ route('audit.index') }}" class="flex items-center gap-3">
            <select name="target_type" onchange="this.form.submit()" class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-sky-500 transition-colors">
                <option value="ALL" {{ $targetType === 'ALL' ? 'selected' : '' }}>All Event Types</option>
                <option value="ORGANIZATION" {{ $targetType === 'ORGANIZATION' ? 'selected' : '' }}>Organization Events</option>
                <option value="LICENSE" {{ $targetType === 'LICENSE' ? 'selected' : '' }}>License Events</option>
                <option value="DEVICE" {{ $targetType === 'DEVICE' ? 'selected' : '' }}>Device Events</option>
                <option value="CREDENTIAL" {{ $targetType === 'CREDENTIAL' ? 'selected' : '' }}>Credential Events</option>
            </select>
        </form>
    </div>

    <!-- Audit Logs Table -->
    <div class="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
                <thead class="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-900/40">
                    <tr>
                        <th class="py-3 px-4">Timestamp (UTC)</th>
                        <th class="py-3 px-4">Admin Principal</th>
                        <th class="py-3 px-4">Action</th>
                        <th class="py-3 px-4">Target Type</th>
                        <th class="py-3 px-4">Target ID</th>
                        <th class="py-3 px-4">Details</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60 font-mono">
                    @forelse ($logs as $log)
                        <tr class="hover:bg-slate-900/30 transition-colors">
                            <td class="py-3 px-4 whitespace-nowrap text-slate-400 text-[11px]">
                                {{ \Carbon\Carbon::parse($log['created_at'])->format('Y-m-d H:i:s') }}
                            </td>
                            <td class="py-3 px-4 text-slate-300">
                                {{ $log['admin_identity'] }}
                            </td>
                            <td class="py-3 px-4">
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                                    {{ $log['action'] }}
                                </span>
                            </td>
                            <td class="py-3 px-4 text-slate-400 text-[11px]">
                                {{ $log['target_type'] ?? 'SYSTEM' }}
                            </td>
                            <td class="py-3 px-4 text-slate-500 text-[11px] truncate max-w-[120px]">
                                {{ $log['target_id'] ?? '—' }}
                            </td>
                            <td class="py-3 px-4 font-sans text-xs text-slate-300">
                                {{ $log['details'] }}
                            </td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="6" class="py-12 text-center text-slate-500 font-sans">
                                No audit log records found for the selected filter.
                            </td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
    </div>
</div>
@endsection
