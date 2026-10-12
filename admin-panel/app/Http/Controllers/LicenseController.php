<?php

namespace App\Http\Controllers;

use App\Services\FastApiClient;
use Illuminate\Http\Request;
use Exception;

class LicenseController extends Controller
{
    protected FastApiClient $api;

    public function __construct(FastApiClient $api)
    {
        $this->api = $api;
    }

    /**
     * Reissue a new one-time activation secret for the customer organization.
     */
    public function reissue(Request $request, string $orgId)
    {
        $validated = $request->validate([
            'reason' => ['required', 'string', 'min:3', 'max:500'],
        ]);

        try {
            $result = $this->api->reissueActivationKey($orgId, $validated['reason']);
            $secret = $result['one_time_activation_secret'] ?? null;
            $licenseNumber = $result['license_number'] ?? null;

            return back()
                ->with('success', 'New permanent activation key generated successfully.')
                ->with('reveal_activation_secret', $secret)
                ->with('reveal_license_number', $licenseNumber);
        } catch (Exception $e) {
            return back()->with('error', $e->getMessage());
        }
    }

    /**
     * Revoke permanent license.
     */
    public function revoke(Request $request, string $licenseId)
    {
        $validated = $request->validate([
            'reason' => ['required', 'string', 'min:3', 'max:500'],
        ]);

        try {
            $this->api->revokeLicense($licenseId, $validated['reason']);
            return back()->with('success', 'Permanent license has been revoked. All active client sessions terminated.');
        } catch (Exception $e) {
            return back()->with('error', $e->getMessage());
        }
    }

    /**
     * Restore permanent license.
     */
    public function restore(string $licenseId)
    {
        try {
            $this->api->restoreLicense($licenseId);
            return back()->with('success', 'Permanent license has been restored successfully.');
        } catch (Exception $e) {
            return back()->with('error', $e->getMessage());
        }
    }
}
