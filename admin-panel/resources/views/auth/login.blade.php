<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-950 text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Administrator Login | FBR Invoice Cloud</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="h-full flex items-center justify-center p-6 antialiased">
    <div class="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
        <!-- Brand Header -->
        <div class="text-center space-y-2">
            <div class="w-12 h-12 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-extrabold text-xl mx-auto shadow-inner">
                F
            </div>
            <h1 class="text-xl font-bold text-white tracking-tight">FBR INVOICE CLOUD</h1>
            <p class="text-xs text-slate-400 uppercase tracking-widest font-semibold">Super Administrator Portal</p>
        </div>

        @if ($errors->any())
            <div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs space-y-1">
                @foreach ($errors->all() as $error)
                    <p>{{ $error }}</p>
                @endforeach
            </div>
        @endif

        <form method="POST" action="{{ route('login') }}" class="space-y-4">
            @csrf

            <div class="space-y-1.5">
                <label for="email" class="block text-xs font-semibold text-slate-300">Administrator Email</label>
                <input id="email" type="email" name="email" value="{{ old('email', 'superadmin@fbrinvoicecloud.com') }}" required autofocus class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
            </div>

            <div class="space-y-1.5">
                <label for="password" class="block text-xs font-semibold text-slate-300">Master Password</label>
                <input id="password" type="password" name="password" required class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors">
            </div>

            <div class="flex items-center justify-between text-xs">
                <label class="flex items-center gap-2 cursor-pointer text-slate-400">
                    <input type="checkbox" name="remember" class="rounded bg-slate-950 border-slate-700 text-sky-600 focus:ring-0">
                    <span>Keep session active</span>
                </label>
            </div>

            <button type="submit" class="w-full py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-sm transition-colors shadow-sm">
                Sign In to Platform Panel
            </button>
        </form>

        <div class="border-t border-slate-800/80 pt-4 text-center">
            <span class="text-[11px] text-slate-500">Secured with MFA policies and AES-256 encrypted credential records</span>
        </div>
    </div>
</body>
</html>
