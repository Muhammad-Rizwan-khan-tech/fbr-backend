<?php

namespace App\Http\Controllers;

use App\Services\FastApiClient;
use Illuminate\Http\Request;
use Exception;

class OrganizationController extends Controller
{
    protected FastApiClient $api;

    public function __construct(FastApiClient $api)
    {
        $this->api = $api;
    }

    /**
     * Display list of customer organizations with optional search and status filter.
     */
    public function index(Request $request)
    {
        $search = $request->query('search');
        $status = $request->query('status', 'ALL');

        $organizations = [];
        $apiError = null;

        try {
            $organizations = $this->api->getOrganizations($search, $status);
        } catch (Exception $e) {
            $apiError = $e->getMessage();
        }

        return view('organizations.index', compact('organizations', 'search', 'status', 'apiError'));
    }

    /**
     * Show form for registering a new customer organization and provisioning its permanent license.
     */
    public function create()
    {
        return view('organizations.create');
    }

    /**
     * Store new organization and generate one-time permanent activation secret.
     */
    public function store(Request $request)
    {
        $validated = $request->validate([
            'name' => ['required', 'string', 'min:2', 'max:255'],
            'ntn' => ['required', 'string', 'min:7', 'max:15'],
            'strn' => ['nullable', 'string', 'max:20'],
            'province' => ['required', 'string', 'min:2', 'max:50'],
            'city' => ['required', 'string', 'min:2', 'max:100'],
            'address' => ['required', 'string', 'min:5', 'max:500'],
            'admin_email' => ['required', 'email'],
            'admin_name' => ['required', 'string', 'max:255'],
            'admin_password' => ['nullable', 'string', 'min:8'],
            'max_devices' => ['required', 'integer', 'min:1', 'max:50'],
            'fbr_environment' => ['required', 'in:DEMO,SANDBOX,PRODUCTION'],
            'fbr_provider' => ['required', 'in:MOCK,SANDBOX,LICENSED_INTEGRATOR,PRODUCTION'],
            'fbr_pos_id' => ['nullable', 'string', 'max:50'],
            'fbr_api_key' => ['nullable', 'string'],
            'fbr_client_id' => ['nullable', 'string'],
            'fbr_client_secret' => ['nullable', 'string'],
            'fbr_auth_token' => ['nullable', 'string'],
        ]);

        try {
            $result = $this->api->createOrganization($validated);

            $orgId = $result['organization_id'] ?? null;
            $activationKey = $result['one_time_activation_secret'] ?? null;
            $licenseNumber = $result['license_number'] ?? null;

            // Flash one-time activation secret for the controlled reveal modal
            return redirect()->route('organizations.show', $orgId)
                ->with('success', "Organization '{$validated['name']}' created successfully with Permanent License {$licenseNumber}.")
                ->with('reveal_activation_secret', $activationKey)
                ->with('reveal_org_name', $validated['name'])
                ->with('reveal_license_number', $licenseNumber);
        } catch (Exception $e) {
            return back()->withInput()->with('error', $e->getMessage());
        }
    }

    /**
     * Show comprehensive organization profile, license, devices, and FBR integration.
     */
    public function show(string $id)
    {
        $org = null;
        $apiError = null;

        try {
            $org = $this->api->getOrganization($id);
        } catch (Exception $e) {
            $apiError = $e->getMessage();
        }

        if (!$org && !$apiError) {
            abort(404, 'Organization not found.');
        }

        return view('organizations.show', compact('org', 'apiError'));
    }

    /**
     * Suspend or restore access for a customer organization.
     */
    public function updateStatus(Request $request, string $id)
    {
        $validated = $request->validate([
            'status' => ['required', 'in:ACTIVE,SUSPENDED'],
            'reason' => ['nullable', 'string', 'max:500'],
        ]);

        try {
            $this->api->updateOrganizationStatus($id, $validated['status'], $validated['reason']);
            $action = $validated['status'] === 'ACTIVE' ? 'restored' : 'suspended';
            return back()->with('success', "Organization status successfully {$action}.");
        } catch (Exception $e) {
            return back()->with('error', $e->getMessage());
        }
    }
}
