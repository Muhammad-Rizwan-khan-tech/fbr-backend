<?php

namespace App\Http\Controllers;

use App\Services\FastApiClient;
use Illuminate\Http\Request;
use Exception;

class AuditLogController extends Controller
{
    protected FastApiClient $api;

    public function __construct(FastApiClient $api)
    {
        $this->api = $api;
    }

    /**
     * Display administrative audit trail logs.
     */
    public function index(Request $request)
    {
        $targetType = $request->query('target_type', 'ALL');
        $limit = (int) $request->query('limit', 100);

        $logs = [];
        $apiError = null;

        try {
            $logs = $this->api->getAuditLogs($limit, $targetType);
        } catch (Exception $e) {
            $apiError = $e->getMessage();
        }

        return view('audit.index', compact('logs', 'targetType', 'apiError'));
    }
}
