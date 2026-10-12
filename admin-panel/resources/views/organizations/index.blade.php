@extends('layouts.app')

@section('title', 'Organizations')
@section('page_title', 'Customer Organization Management')

@section('content')
<div class="space-y-6">
    <!-- Filter and Search Header -->
    <div class="bg-slate-950 border border-slate-800 rounded-2xl p-5 flex flex-col md:flex-row items-center justify-between gap-4">
        <form method="GET" action="{{ route('organizations.index') }}" class="flex-1 w-full flex items-center gap-3">
            <div class="relative flex-1">
                <input type="text" name="search" value="{{ $search }}" placeholder="Search by company name, NTN, or slug..." class="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors pl-10">
                <svg class="w-4 h-4 text-slate-500 absolute left-3.5 top-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
            </div>

            <select name="status" class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-slate-300 focus:outline-none focus:border-sky-500 transition-colors">
                <option value="ALL" {{ $status === 'ALL' ? 'selected' : '' }}>All Statuses</option>
                <option value="ACTIVE" {{ $status === 'ACTIVE' ? 'selected' : '' }}>Active Only</option>
                <option value="SUSPENDED" {{ $status === 'SUSPENDED' ? 'selected' : '' }}>Suspended Only</option>
            </select>

            <button type="submit" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold rounded-xl transition-colors shrink-0">
                Filter
            </button>
        </form>

        <a href="{{ route('organizations.create') }}" class="px-4 py-2.5 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-xl transition-colors shrink-0 flex items-center gap-1.5 shadow-sm">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            <span>Create Organization</span>
        </a>
    </div>

    <!-- Organizations Table -->
    <div class="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
                <thead class="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-900/40">
                    <tr>
                        <th class="py-3 px-4">Organization / Taxpayer</th>
                        <th class="py-3 px-4">NTN / Province</th>
                        <th class="py-3 px-4">Permanent License</th>
                        <th class="py-3 px-4">Authorized Devices</th>
                        <th class="py-3 px-4">Status</th>
                        <th class="py-3 px-4 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60">
                    @forelse ($organizations as $org)
                        <tr class="hover:bg-slate-900/30 transition-colors">
                            <td class="py-3.5 px-4">
                                <a href="{{ route('organizations.show', $org['id']) }}" class="font-bold text-white hover:text-sky-400 transition-colors block text-sm">
                                    {{ $org['name'] }}
                                </a>
                                <span class="text-[11px] text-slate-400 font-mono">{{ $org['slug'] }}</span>
                            </td>
                            <td class="py-3.5 px-4">
                                <div class="font-mono text-slate-200">{{ $org['ntn'] ?? 'N/A' }}</div>
                                <div class="text-[11px] text-slate-400">{{ $org['province'] ?? 'Pakistan' }}</div>
                            </td>
                            <td class="py-3.5 px-4 font-mono">
                                <span class="text-emerald-400 font-semibold">{{ $org['license_number'] ?? 'LIC-PERMANENT' }}</span>
                                <div class="text-[10px] text-slate-400 uppercase tracking-wider font-sans font-medium">Permanent License</div>
                            </td>
                            <td class="py-3.5 px-4">
                                <span class="font-semibold text-white">{{ $org['active_devices_count'] ?? 0 }}</span>
                                <span class="text-slate-400">/ {{ $org['max_devices'] ?? 5 }} max</span>
                            </td>
                            <td class="py-3.5 px-4">
                                @if (($org['status'] ?? 'ACTIVE') === 'ACTIVE')
                                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                                        ACTIVE
                                    </span>
                                @else
                                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                        <span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                                        SUSPENDED
                                    </span>
                                @endif
                            </td>
                            <td class="py-3.5 px-4 text-right">
                                <div class="flex items-center justify-end gap-2">
                                    <a href="{{ route('organizations.show', $org['id']) }}" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs font-semibold transition-colors">
                                        View Details
                                    </a>
                                </div>
                            </td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="6" class="py-12 text-center text-slate-500">
                                <p class="text-sm">No organizations found matching your search.</p>
                                <a href="{{ route('organizations.create') }}" class="mt-2 inline-block text-xs text-sky-400 hover:underline">
                                    Register a new organization &rarr;
                                </a>
                            </td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
    </div>
</div>
@endsection
