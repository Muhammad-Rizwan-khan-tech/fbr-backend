@extends('layouts.app')

@section('title', 'Register Organization')
@section('page_title', 'Register New Customer Organization')

@section('content')
<div class="max-w-4xl mx-auto space-y-6">
    <div class="flex items-center justify-between">
        <div>
            <h2 class="text-base font-bold text-white">Organization Registration & License Provisioning</h2>
            <p class="text-xs text-slate-400">Creates taxpayer profile, issues permanent license, and generates one-time activation secret.</p>
        </div>
        <a href="{{ route('organizations.index') }}" class="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 font-semibold transition-colors">
            &larr; Back to List
        </a>
    </div>

    @if ($errors->any())
        <div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs space-y-1">
            <strong class="font-bold block">Please resolve the following errors:</strong>
            @foreach ($errors->all() as $error)
                <p>&bull; {{ $error }}</p>
            @endforeach
        </div>
    @endif

    <form method="POST" action="{{ route('organizations.store') }}" class="space-y-6">
        @csrf

        <!-- Section 1: Business Taxpayer Identification -->
        <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div class="border-b border-slate-800 pb-3 flex items-center justify-between">
                <div>
                    <h3 class="text-xs font-bold text-sky-400 uppercase tracking-wider">1. Taxpayer Legal Details</h3>
                    <p class="text-[11px] text-slate-400">Official business registration with Pakistan Federal Board of Revenue</p>
                </div>
                <span class="text-[10px] uppercase font-bold text-slate-500">Required</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="md:col-span-2 space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Company Legal Business Name *</label>
                    <input type="text" name="name" value="{{ old('name') }}" placeholder="e.g. Tariq Traders Pvt Ltd" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">NTN (National Tax Number) *</label>
                    <input type="text" name="ntn" value="{{ old('ntn') }}" placeholder="e.g. 1234567-8" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white font-mono placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">STRN (Sales Tax Registration Number)</label>
                    <input type="text" name="strn" value="{{ old('strn') }}" placeholder="e.g. 3277876123456" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white font-mono placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Province *</label>
                    <select name="province" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-sky-500 transition-colors">
                        <option value="Sindh" {{ old('province') === 'Sindh' ? 'selected' : '' }}>Sindh (SRB)</option>
                        <option value="Punjab" {{ old('province') === 'Punjab' ? 'selected' : '' }}>Punjab (PRA)</option>
                        <option value="Khyber Pakhtunkhwa" {{ old('province') === 'Khyber Pakhtunkhwa' ? 'selected' : '' }}>Khyber Pakhtunkhwa (KPRA)</option>
                        <option value="Balochistan" {{ old('province') === 'Balochistan' ? 'selected' : '' }}>Balochistan (BRA)</option>
                        <option value="Islamabad Capital Territory" {{ old('province') === 'Islamabad Capital Territory' ? 'selected' : '' }}>Islamabad Capital Territory (ICT)</option>
                    </select>
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">City *</label>
                    <input type="text" name="city" value="{{ old('city', 'Karachi') }}" placeholder="e.g. Karachi, Lahore, Islamabad" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="md:col-span-2 space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Principal Business Address *</label>
                    <input type="text" name="address" value="{{ old('address') }}" placeholder="e.g. Suite 402, Business Avenue, Shahrah-e-Faisal" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>
            </div>
        </div>

        <!-- Section 2: Permanent License & Administrative Contact -->
        <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div class="border-b border-slate-800 pb-3 flex items-center justify-between">
                <div>
                    <h3 class="text-xs font-bold text-emerald-400 uppercase tracking-wider">2. Permanent License & Primary Administrator</h3>
                    <p class="text-[11px] text-slate-400">Issues permanent desktop license and provisions tenant root admin</p>
                </div>
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">NO EXPIRY</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Administrator Full Name *</label>
                    <input type="text" name="admin_name" value="{{ old('admin_name', 'Company Admin') }}" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Administrator Email *</label>
                    <input type="email" name="admin_email" value="{{ old('admin_email') }}" placeholder="admin@customerdomain.pk" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Max Allowed Desktop Terminals *</label>
                    <input type="number" name="max_devices" value="{{ old('max_devices', 5 prisoners ?? 5) }}" min="1" max="50" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-sky-500 transition-colors">
                    <p class="text-[11px] text-slate-500">Maximum concurrent Windows workstations bound to this permanent license.</p>
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Initial Admin Password (Optional)</label>
                    <input type="password" name="admin_password" placeholder="Leave blank for auto-generated secure password" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>
            </div>
        </div>

        <!-- Section 3: Authorized FBR Digital Invoicing Integration -->
        <div class="bg-slate-950 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div class="border-b border-slate-800 pb-3 flex items-center justify-between">
                <div>
                    <h3 class="text-xs font-bold text-indigo-400 uppercase tracking-wider">3. Authorized FBR Digital Invoicing Credentials</h3>
                    <p class="text-[11px] text-slate-400">Encrypted at rest with AES-256-GCM. Managed exclusively by platform administrator.</p>
                </div>
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">AES-256 ENCRYPTED</span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">FBR Environment *</label>
                    <select name="fbr_environment" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-sky-500 transition-colors">
                        <option value="DEMO" {{ old('fbr_environment') === 'DEMO' ? 'selected' : '' }}>DEMO (Internal Mock Engine)</option>
                        <option value="SANDBOX" {{ old('fbr_environment') === 'SANDBOX' ? 'selected' : '' }}>SANDBOX (Official FBR Test Sandbox)</option>
                        <option value="PRODUCTION" {{ old('fbr_environment') === 'PRODUCTION' ? 'selected' : '' }}>PRODUCTION (Live FBR PRAL Invoicing Gateway)</option>
                    </select>
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">FBR Adapter Provider *</label>
                    <select name="fbr_provider" required class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-sky-500 transition-colors">
                        <option value="MOCK" {{ old('fbr_provider') === 'MOCK' ? 'selected' : '' }}>Mock Simulator (Local Testing)</option>
                        <option value="SANDBOX" {{ old('fbr_provider') === 'SANDBOX' ? 'selected' : '' }}>Direct Sandbox (FBR IRIS)</option>
                        <option value="LICENSED_INTEGRATOR" {{ old('fbr_provider') === 'LICENSED_INTEGRATOR' ? 'selected' : '' }}>Licensed Integrator Gateway</option>
                        <option value="PRODUCTION" {{ old('fbr_provider') === 'PRODUCTION' ? 'selected' : '' }}>Direct Production (PRAL)</option>
                    </select>
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">FBR POS / Branch Identifier</label>
                    <input type="text" name="fbr_pos_id" value="{{ old('fbr_pos_id') }}" placeholder="e.g. POS-98765-BR01" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white font-mono placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">FBR API Key / Bearer Secret</label>
                    <input type="password" name="fbr_api_key" placeholder="Enter FBR integration key..." class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Client ID (OAuth2 if applicable)</label>
                    <input type="text" name="fbr_client_id" value="{{ old('fbr_client_id') }}" placeholder="Optional client ID" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white font-mono placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Client Secret (OAuth2)</label>
                    <input type="password" name="fbr_client_secret" placeholder="Optional client secret" class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
                </div>
            </div>
        </div>

        <div class="flex items-center justify-end gap-3 pt-4">
            <a href="{{ route('organizations.index') }}" class="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition-colors">
                Cancel
            </a>
            <button type="submit" class="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold transition-colors shadow-lg">
                Create Organization & Issue Permanent License
            </button>
        </div>
    </form>
</div>
@endsection
