<?php

namespace App\Http\Controllers;

use App\Services\FastApiClient;
use Illuminate\Http\Request;
use Exception;

class FbrCredentialController extends Controller
{
    protected FastApiClient $api;

    public function __construct(FastApiClient $api)
    {
        $this->api = $api;
    }

    /**
     * Configure or rotate organization-specific FBR credentials (encrypted at rest on backend).
     */
    public function update(Request $request, string $orgId)
    {
        $validated = $request->validate([
            'environment' => ['required', 'in:DEMO,SANDBOX,PRODUCTION'],
            'provider' => ['required', 'in:MOCK,SANDBOX,LICENSED_INTEGRATOR,PRODUCTION'],
            'fbr_pos_id' => ['nullable', 'string', 'max:50'],
            'base_url' => ['nullable', 'url', 'max:255'],
            'api_key' => ['nullable', 'string'],
            'client_id' => ['nullable', 'string'],
            'client_secret' => ['nullable', 'string'],
            'auth_token' => ['nullable', 'string'],
            'cert_passphrase' => ['nullable', 'string'],
        ]);

        try {
            $this->api->setFBRCredentials($orgId, $validated);
            return back()->with('success', 'FBR digital invoicing credentials updated and encrypted at rest.');
        } catch (Exception $e) {
            return back()->with('error', $e->getMessage());
        }
    }

    /**
     * Test live integration connection for an organization.
     */
    public function test(string $orgId)
    {
        try {
            $result = $this->api->testFBRConnection($orgId);
            $status = $result['status'] ?? 'UNKNOWN';
            $msg = $result['message'] ?? 'Handshake completed.';
            $latency = isset($result['latency_ms']) ? " (Latency: {$result['latency_ms']}ms)" : '';

            if ($status === 'CONNECTED' || $status === 'HEALTHY' || ($result['success'] ?? false)) {
                return back()->with('success', "FBR Connection Test: [{$status}] {$msg}{$latency}");
            }

            return back()->with('warning', "FBR Connection Test: [{$status}] {$msg}");
        } catch (Exception $e) {
            return back()->with('error', "FBR Connection Failed: " . $e->getMessage());
        }
    }
}
