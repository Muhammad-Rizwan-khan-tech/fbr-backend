<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-900 text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@yield('title', 'Super Admin') | FBR Invoice Cloud</title>
    <!-- Tailwind CSS Play CDN for zero-dependency standalone admin styling -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        brand: {
                            50: '#f0f9ff',
                            500: '#0284c7',
                            600: '#0369a1',
                            700: '#075985',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        [x-cloak] { display: none !important; }
    </style>
</head>
<body class="h-full flex flex-col antialiased">
    <div class="flex h-full">
        <!-- Sidebar Navigation -->
        <aside class="w-64 bg-slate-950 border-r border-slate-800 flex flex-col justify-between shrink-0">
            <div>
                <!-- Brand Header -->
                <div class="h-16 flex items-center px-6 border-b border-slate-800 gap-3">
                    <div class="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold">
                        F
                    </div>
                    <div>
                        <div class="font-bold text-sm text-white tracking-wide">FBR INVOICE CLOUD</div>
                        <div class="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Super Admin Panel</div>
                    </div>
                </div>

                <!-- Navigation Links -->
                <nav class="p-4 space-y-1.5">
                    <a href="{{ route('dashboard') }}" class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors {{ request()->routeIs('dashboard') ? 'bg-sky-600/20 text-sky-400 border border-sky-500/30' : 'text-slate-300 hover:bg-slate-900 hover:text-white' }}">
                        <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
                        </svg>
                        <span>Dashboard</span>
                    </a>

                    <a href="{{ route('organizations.index') }}" class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors {{ request()->routeIs('organizations.*') ? 'bg-sky-600/20 text-sky-400 border border-sky-500/30' : 'text-slate-300 hover:bg-slate-900 hover:text-white' }}">
                        <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
                        </svg>
                        <span>Organizations</span>
                    </a>

                    <a href="{{ route('devices.index') }}" class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors {{ request()->routeIs('devices.*') ? 'bg-sky-600/20 text-sky-400 border border-sky-500/30' : 'text-slate-300 hover:bg-slate-900 hover:text-white' }}">
                        <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                        </svg>
                        <span>Authorized Terminals</span>
                    </a>

                    <a href="{{ route('audit.index') }}" class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors {{ request()->routeIs('audit.*') ? 'bg-sky-600/20 text-sky-400 border border-sky-500/30' : 'text-slate-300 hover:bg-slate-900 hover:text-white' }}">
                        <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                        </svg>
                        <span>Audit Logs</span>
                    </a>
                </nav>
            </div>

            <!-- Footer User Section -->
            <div class="p-4 border-t border-slate-800">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2.5">
                        <div class="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-semibold text-slate-300">
                            {{ substr(auth()->user()->name ?? 'SA', 0, 2) }}
                        </div>
                        <div class="overflow-hidden">
                            <div class="text-xs font-semibold text-white truncate">{{ auth()->user()->name ?? 'Super Admin' }}</div>
                            <div class="text-[11px] text-slate-400 truncate">{{ auth()->user()->email ?? '' }}</div>
                        </div>
                    </div>
                </div>

                <form method="POST" action="{{ route('logout') }}">
                    @csrf
                    <button type="submit" class="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 rounded-lg transition-colors">
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
                        </svg>
                        <span>Log Out</span>
                    </button>
                </form>
            </div>
        </aside>

        <!-- Main Content Area -->
        <main class="flex-1 overflow-y-auto flex flex-col bg-slate-900">
            <!-- Top Navbar -->
            <header class="h-16 bg-slate-950/50 backdrop-blur border-b border-slate-800 px-8 flex items-center justify-between sticky top-0 z-20">
                <div class="flex items-center gap-3">
                    <h1 class="text-lg font-bold text-white">@yield('page_title', 'Dashboard')</h1>
                    <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">LIVE BACKEND</span>
                </div>

                <div class="flex items-center gap-4">
                    <a href="{{ route('organizations.create') }}" class="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-sm transition-colors">
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                        </svg>
                        <span>New Organization</span>
                    </a>
                </div>
            </header>

            <!-- Flash Alert Messages -->
            <div class="px-8 pt-6">
                @if (session('success'))
                    <div class="mb-4 flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
                        <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        <span>{{ session('success') }}</span>
                    </div>
                @endif

                @if (session('error'))
                    <div class="mb-4 flex items-center gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
                        <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        <span>{{ session('error') }}</span>
                    </div>
                @endif

                @if (session('warning'))
                    <div class="mb-4 flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm">
                        <svg class="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                        </svg>
                        <span>{{ session('warning') }}</span>
                    </div>
                @endif
            </div>

            <!-- Page Body -->
            <div class="px-8 py-4 flex-1">
                @yield('content')
            </div>
        </main>
    </div>

    <!-- Controlled One-Time Activation Secret Reveal Modal -->
    @if (session('reveal_activation_secret'))
        <div id="revealModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div class="bg-slate-900 border border-amber-500/50 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
                <div class="flex items-center gap-3 text-amber-400">
                    <div class="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                        <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/>
                        </svg>
                    </div>
                    <div>
                        <h3 class="text-base font-bold text-white">One-Time Activation Key Generated</h3>
                        <p class="text-xs text-amber-400 font-medium">Permanent License Activation Secret</p>
                    </div>
                </div>

                <div class="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-xs text-amber-200 space-y-1">
                    <p class="font-bold text-amber-300">IMPORTANT SECURITY NOTICE:</p>
                    <p>This activation key is shown <strong>ONCE ONLY</strong>. Once this dialog is closed, the plaintext key is destroyed on the server and only a secure SHA-256 hash is preserved.</p>
                    <p class="pt-1">Provide this secret to the customer for their first-time desktop application activation.</p>
                </div>

                <div class="space-y-1.5">
                    <label class="text-xs font-semibold text-slate-300">Activation Secret Key</label>
                    <div class="flex items-center gap-2">
                        <input id="secretKeyInput" type="text" readonly value="{{ session('reveal_activation_secret') }}" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-emerald-400 font-mono text-sm tracking-wider font-bold focus:outline-none selection:bg-emerald-500 selection:text-black">
                        <button onclick="copySecretKey()" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 shrink-0 border border-slate-700">
                            <span id="copyBtnText">Copy</span>
                        </button>
                    </div>
                </div>

                <div class="pt-2 flex justify-end">
                    <button onclick="document.getElementById('revealModal').remove()" class="px-5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold transition-colors">
                        I Have Safely Saved This Key
                    </button>
                </div>
            </div>
        </div>

        <script>
            function copySecretKey() {
                var copyText = document.getElementById("secretKeyInput");
                copyText.select();
                copyText.setSelectionRange(0, 99999);
                navigator.clipboard.writeText(copyText.value);
                document.getElementById("copyBtnText").innerText = "Copied!";
                setTimeout(() => {
                    document.getElementById("copyBtnText").innerText = "Copy";
                }, 2000);
            }
        </script>
    @endif
</body>
</html>
