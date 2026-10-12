<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Http\Client\Response;
use Exception;

class FastApiClient
{
    protected string $baseUrl;
    protected string $adminKey;
    protected int $timeout;

    public function __construct()
    {
        $this->baseUrl = rtrim(config('services.fastapi.url', 'http://127.0.0.1:8000'), '/');
        $this->adminKey = config('services.fastapi.admin_key', 'dev-admin-secret-key-change-in-production');
        $this->timeout = (int) config('services.fastapi.timeout', 15);
    }

    /**
     * Build base HTTP client with standard Super Admin authorization.
     */
    protected function client()
    {
        return Http::baseUrl($this->baseUrl)
            ->timeout($this->timeout)
            ->acceptJson()
            ->withHeaders([
                'X-Admin-Key' => $this->adminKey,
                'User-Agent' => 'FBR-Invoice-Cloud-Laravel-Admin/1.0',
            ]);
    }

    /**
     * Handle HTTP response and return parsed JSON data or throw meaningful exception.
     */
    protected function handleResponse(Response $response, string $operation): array
    {
        if ($response->successful()) {
            return $response->json() ?? [];
        }

        $status = $response->status();
        $body = $response->json() ?? [];
        $errorMessage = $body['detail'] ?? ($body['error']['message'] ?? $response->body());

        Log::error("FastAPI Admin API Error [{$operation}]: HTTP {$status} - {$errorMessage}", [
            'status' => $status,
            'operation' => $operation,
        ]);

        throw new Exception("Backend API Error ({$status}): {$errorMessage}", $status);
    }

    /**
     * Get platform statistics for dashboard KPI cards.
     */
    public function getPlatformStats(): array
    {
        $response = $this->client()->get('/api/v1/admin/stats');
        return $this->handleResponse($response, 'getPlatformStats');
    }

    /**
     * List all customer organizations with optional search and status filtering.
     */
    public function getOrganizations(?string $search = null, ?string $status = null): array
    {
        $query = [];
        if ($search) {
            $query['search'] = $search;
        }
        if ($status && $status !== 'ALL') {
            $query['status'] = $status;
        }

        $response = $this->client()->get('/api/v1/admin/organizations', $query);
        return $this->handleResponse($response, 'getOrganizations');
    }

    /**
     * Get detailed information for an organization (taxpayer, permanent license, devices, masked FBR credentials).
     */
    public function getOrganization(string $id): array
    {
        $response = $this->client()->get("/api/v1/admin/organizations/{$id}");
        return $this->handleResponse($response, 'getOrganization');
    }

    /**
     * Create a new organization, provision permanent license, and generate one-time activation secret.
     */
    public function createOrganization(array $data): array
    {
        $response = $this->client()->post('/api/v1/admin/organizations', $data);
        return $this->handleResponse($response, 'createOrganization');
    }

    /**
     * Suspend or restore access for a customer organization.
     */
    public function updateOrganizationStatus(string $id, string $status, ?string $reason = null): array
    {
        $response = $this->client()->put("/api/v1/admin/organizations/{$id}/status", [
            'status' => $status,
            'reason' => $reason,
        ]);
        return $this->handleResponse($response, 'updateOrganizationStatus');
    }

    /**
     * Reissue a new one-time activation secret for an authorized device / replacement.
     */
    public function reissueActivationKey(string $id, ?string $reason = null): array
    {
        $response = $this->client()->post("/api/v1/admin/organizations/{$id}/licenses/reissue", [
            'reason' => $reason ?? 'Administrative re-issuance from Super Admin panel',
        ]);
        return $this->handleResponse($response, 'reissueActivationKey');
    }

    /**
     * Revoke a customer organization's permanent license.
     */
    public function revokeLicense(string $licenseId, ?string $reason = null): array
    {
        $response = $this->client()->put("/api/v1/admin/licenses/{$licenseId}/revoke", [
            'reason' => $reason ?? 'Revoked by Super Administrator',
        ]);
        return $this->handleResponse($response, 'revokeLicense');
    }

    /**
     * Restore a revoked permanent license.
     */
    public function restoreLicense(string $licenseId): array
    {
        $response = $this->client()->put("/api/v1/admin/licenses/{$licenseId}/restore");
        return $this->handleResponse($response, 'restoreLicense');
    }

    /**
     * Revoke an individual terminal / device installation.
     */
    public function revokeDevice(string $deviceId, ?string $reason = null): array
    {
        $response = $this->client()->put("/api/v1/admin/devices/{$deviceId}/revoke", [
            'reason' => $reason ?? 'Device revoked by platform administrator',
        ]);
        return $this->handleResponse($response, 'revokeDevice');
    }

    /**
     * Configure or rotate organization FBR credentials (encrypted at rest on backend).
     */
    public function setFBRCredentials(string $id, array $credentials): array
    {
        $response = $this->client()->post("/api/v1/admin/organizations/{$id}/fbr-credentials", $credentials);
        return $this->handleResponse($response, 'setFBRCredentials');
    }

    /**
     * Perform live test handshake with FBR adapter for this organization.
     */
    public function testFBRConnection(string $id): array
    {
        $response = $this->client()->post("/api/v1/admin/organizations/{$id}/fbr-test-connection");
        return $this->handleResponse($response, 'testFBRConnection');
    }

    /**
     * Retrieve administrative audit trail logs.
     */
    public function getAuditLogs(int $limit = 100, ?string $targetType = null): array
    {
        $query = ['limit' => $limit];
        if ($targetType && $targetType !== 'ALL') {
            $query['target_type'] = $targetType;
        }

        $response = $this->client()->get('/api/v1/admin/audit-logs', $query);
        return $this->handleResponse($response, 'getAuditLogs');
    }
}
