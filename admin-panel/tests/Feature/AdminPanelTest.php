<?php

namespace Tests\Feature;

use Tests\TestCase;
use App\Models\User;
use App\Services\FastApiClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Mockery;

class AdminPanelTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        
        // Seed default admin user
        $this->seed();
    }

    public function test_guest_is_redirected_to_login()
    {
        $response = $this->get('/dashboard');
        $response->assertRedirect('/login');
    }

    public function test_super_admin_can_login_successfully()
    {
        $response = $this->post('/login', [
            'email' => 'superadmin@fbrinvoicecloud.com',
            'password' => 'SuperAdmin@Secure2026!',
        ]);

        $response->assertRedirect('/dashboard');
        $this->assertAuthenticated();
    }

    public function test_invalid_login_is_rejected()
    {
        $response = $this->post('/login', [
            'email' => 'superadmin@fbrinvoicecloud.com',
            'password' => 'wrong-password',
        ]);

        $response->assertSessionHasErrors('email');
        $this->assertGuest();
    }

    public function test_authenticated_admin_can_view_dashboard_with_mocked_fastapi()
    {
        $admin = User::first();
        $this->actingAs($admin);

        $mockApi = Mockery::mock(FastApiClient::class);
        $mockApi->shouldReceive('getPlatformStats')->once()->andReturn([
            'total_organizations' => 4,
            'active_organizations' => 4,
            'suspended_organizations' => 0,
            'total_licenses' => 4,
            'active_licenses' => 4,
            'revoked_licenses' => 0,
            'total_devices' => 2,
            'active_devices' => 2,
            'invoices_total' => 150,
            'invoices_submitted' => 148,
            'invoices_failed' => 2,
            'fbr_healthy' => true,
        ]);
        $mockApi->shouldReceive('getAuditLogs')->with(8)->once()->andReturn([]);

        $this->app->instance(FastApiClient::class, $mockApi);

        $response = $this->get('/dashboard');
        $response->assertStatus(200);
        $response->assertSee('Platform Operations Overview', false);
        $response->assertSee('PERMANENT LICENSES');
    }

    public function test_organizations_index_displays_list()
    {
        $admin = User::first();
        $this->actingAs($admin);

        $mockApi = Mockery::mock(FastApiClient::class);
        $mockApi->shouldReceive('getOrganizations')->with(null, 'ALL')->once()->andReturn([
            [
                'id' => 'org-123',
                'name' => 'ABC Distribution Pvt Ltd',
                'slug' => 'abc-dist',
                'ntn' => '1234567-8',
                'province' => 'Sindh',
                'status' => 'ACTIVE',
                'license_number' => 'LIC-ABCD-PERM-DEMO01',
                'max_devices' => 5,
                'active_devices_count' => 1,
            ]
        ]);

        $this->app->instance(FastApiClient::class, $mockApi);

        $response = $this->get('/organizations');
        $response->assertStatus(200);
        $response->assertSee('ABC Distribution Pvt Ltd');
        $response->assertSee('LIC-ABCD-PERM-DEMO01');
    }
}
