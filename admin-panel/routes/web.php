<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\OrganizationController;
use App\Http\Controllers\LicenseController;
use App\Http\Controllers\DeviceController;
use App\Http\Controllers\FbrCredentialController;
use App\Http\Controllers\AuditLogController;

// Guest Authentication Routes
Route::middleware('guest')->group(function () {
    Route::get('/login', [AuthController::class, 'showLogin'])->name('login');
    Route::post('/login', [AuthController::class, 'login'])->middleware('throttle:10,1');
});

// Protected Super Administrator Routes
Route::middleware('auth')->group(function () {
    Route::post('/logout', [AuthController::class, 'logout'])->name('logout');
    Route::get('/', fn() => redirect()->route('dashboard'));

    // Dashboard
    Route::get('/dashboard', [DashboardController::class, 'index'])->name('dashboard');

    // Organization Management
    Route::get('/organizations', [OrganizationController::class, 'index'])->name('organizations.index');
    Route::get('/organizations/create', [OrganizationController::class, 'create'])->name('organizations.create');
    Route::post('/organizations', [OrganizationController::class, 'store'])->name('organizations.store');
    Route::get('/organizations/{id}', [OrganizationController::class, 'show'])->name('organizations.show');
    Route::put('/organizations/{id}/status', [OrganizationController::class, 'updateStatus'])->name('organizations.status');

    // Permanent License Operations
    Route::post('/organizations/{orgId}/licenses/reissue', [LicenseController::class, 'reissue'])->name('licenses.reissue');
    Route::put('/licenses/{licenseId}/revoke', [LicenseController::class, 'revoke'])->name('licenses.revoke');
    Route::put('/licenses/{licenseId}/restore', [LicenseController::class, 'restore'])->name('licenses.restore');

    // Device Management
    Route::get('/devices', [DeviceController::class, 'index'])->name('devices.index');
    Route::put('/devices/{deviceId}/revoke', [DeviceController::class, 'revoke'])->name('devices.revoke');

    // FBR Credentials & Live Connection Handshake
    Route::post('/organizations/{orgId}/fbr-credentials', [FbrCredentialController::class, 'update'])->name('fbr.credentials.update');
    Route::post('/organizations/{orgId}/fbr-test-connection', [FbrCredentialController::class, 'test'])->name('fbr.connection.test');

    // Audit Logs
    Route::get('/audit-logs', [AuditLogController::class, 'index'])->name('audit.index');
});
