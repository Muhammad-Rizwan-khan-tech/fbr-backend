<?php

namespace App\Http\Controllers;

use App\Services\FastApiClient;
use Illuminate\Http\Request;
use Exception;

class DeviceController extends Controller
{
    protected FastApiClient $api;

    public function __construct(FastApiClient $api)
    {
        $this->api = $api;
    }

    /**
     * Display all authorized desktop devices across all organizations.
     */
    public function index()
    {
        $devices = [];
        $apiError = null;

        try {
            // Retrieve all organizations to aggregate device installations
            $orgs = $this->api->getOrganizations();
            foreach ($orgs as $orgSummary) {
                try {
                    $orgDetail = $this->api->getOrganization($orgSummary['id']);
                    foreach ($orgDetail['devices'] ?? [] as $dev) {
                        $dev['organization_name'] = $orgSummary['name'];
                        $dev['organization_id'] = $orgSummary['id'];
                        $devices[] = $dev;
                    }
                } catch (Exception $e) {
                    // Ignore single org fetch failures in global list
                }
            }
        } catch (Exception $e) {
            $apiError = $e->getMessage();
        }

        return view('devices.index', compact('devices', 'apiError'));
    }

    /**
     * Revoke an authorized desktop installation.
     */
    public function revoke(Request $request, string $deviceId)
    {
        $validated = $request->validate([
            'reason' => ['nullable', 'string', 'max:500'],
        ]);

        try {
            $this->api->revokeDevice($deviceId, $validated['reason'] ?? 'Revoked by administrator');
            return back()->with('success', 'Device installation authorization revoked successfully.');
        } catch (Exception $e) {
            return back()->with('error', $e->getMessage());
        }
    }
}
