<?php

namespace App\Http\Controllers;

use App\Services\FastApiClient;
use Illuminate\Http\Request;
use Exception;

class DashboardController extends Controller
{
    protected FastApiClient $api;

    public function __construct(FastApiClient $api)
    {
        $this->api = $api;
    }

    /**
     * Render Super Admin Dashboard with live stats and recent activity.
     */
    public function index()
    {
        $stats = [
            'total_organizations' => 0,
            'active_organizations' => 0,
            'suspended_organizations' => 0,
            'total_licenses' => 0,
            'active_licenses' => 0,
            'revoked_licenses' => 0,
            'total_devices' => 0,
            'active_devices' => 0,
            'invoices_total' => 0,
            'invoices_submitted' => 0,
            'invoices_failed' => 0,
            'fbr_healthy' => true,
        ];
        $recentAuditLogs = [];
        $apiError = null;

        try {
            $stats = $this->api->getPlatformStats();
            $recentAuditLogs = $this->api->getAuditLogs(8);
        } catch (Exception $e) {
            $apiError = $e->getMessage();
        }

        return view('dashboard', compact('stats', 'recentAuditLogs', 'apiError'));
    }
}
