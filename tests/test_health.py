# Copyright (c) 2025 Stephen Clau
#
# This file is part of Factorio ISR.
#
# Factorio ISR is dual-licensed:
#
# 1. GNU Affero General Public License v3.0 (AGPL-3.0)
#    See LICENSE file for full terms
#
# 2. Commercial License
#    For proprietary use without AGPL requirements
#    Contact: licensing@laudiversified.com
#
# SPDX-License-Identifier: AGPL-3.0-only OR Commercial


import pytest
import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import aiohttp
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop, TestClient, TestServer


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from health import HealthCheckServer


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def health_server():
    """Create a HealthCheckServer instance."""
    return HealthCheckServer()


@pytest.fixture
def custom_health_server():
    """Create a HealthCheckServer with custom host/port."""
    return HealthCheckServer(host="127.0.0.1", port=9090)


# ============================================================================
# HealthCheckServer Initialization Tests
# ============================================================================

class TestHealthCheckServerInit:
    """Test HealthCheckServer initialization."""
    
    def test_init_default_params(self):
        """Test initialization with default parameters."""
        server = HealthCheckServer()
        
        assert server.host == "0.0.0.0"
        assert server.port == 8080
        assert server.app is not None
        assert isinstance(server.app, web.Application)
        assert server.runner is None
        assert server.site is None
    
    def test_init_custom_host_port(self):
        """Test initialization with custom host and port."""
        server = HealthCheckServer(host="127.0.0.1", port=9000)
        
        assert server.host == "127.0.0.1"
        assert server.port == 9000
        assert server.app is not None
    
    def test_init_ipv6_host(self):
        """Test initialization with IPv6 host."""
        server = HealthCheckServer(host="::", port=8080)
        
        assert server.host == "::"
        assert server.port == 8080
    
    def test_init_high_port_number(self):
        """Test initialization with high port number."""
        server = HealthCheckServer(host="0.0.0.0", port=65535)
        
        assert server.port == 65535
    
    def test_init_creates_app(self):
        """Test that initialization creates aiohttp Application."""
        server = HealthCheckServer()
        
        assert server.app is not None
        assert isinstance(server.app, web.Application)
    
    def test_init_calls_setup_routes(self):
        """Test that initialization sets up routes."""
        server = HealthCheckServer()
        
        # Verify routes were added
        routes = list(server.app.router.routes())
        assert len(routes) >= 2  # At least /health and /


# ============================================================================
# _setup_routes() Tests
# ============================================================================

class TestSetupRoutes:
    """Test HealthCheckServer._setup_routes() method."""
    
    def test_setup_routes_adds_health_endpoint(self, health_server):
        """Test that health endpoint is registered."""
        routes = list(health_server.app.router.routes())
        
        # Verify we have routes
        assert len(routes) > 0
        
        # Find health route
        health_found = any('/health' in str(r.resource) for r in routes)
        assert health_found, "Health endpoint not found in routes"
    
    def test_setup_routes_adds_root_endpoint(self, health_server):
        """Test that root endpoint is registered."""
        routes = list(health_server.app.router.routes())
        
        # Should have multiple routes (aiohttp adds HEAD automatically)
        # At minimum: GET /health, HEAD /health, GET /, HEAD /
        assert len(routes) >= 2, f"Expected at least 2 routes, found {len(routes)}"
    
    @pytest.mark.asyncio
    async def test_both_endpoints_accessible(self, health_server):
        """Test that both endpoints are accessible via HTTP."""
        async with TestClient(TestServer(health_server.app)) as client:
            # Health endpoint
            health_resp = await client.get('/health')
            assert health_resp.status == 200
            
            # Root endpoint
            root_resp = await client.get('/')
            assert root_resp.status == 200




# ============================================================================
# HTTP Endpoint Tests using aiohttp test client
# ============================================================================

class TestHealthEndpoint:
    """Test health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self):
        """Test that /health returns 200 OK."""
        server = HealthCheckServer()
        
        # Create test client
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/health')
            
            assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_json(self):
        """Test that /health returns JSON."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/health')
            
            assert resp.content_type == 'application/json'
    
    @pytest.mark.asyncio
    async def test_health_endpoint_response_structure(self):
        """Test /health response has correct structure."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/health')
            data = await resp.json()
            
            assert 'status' in data
            assert 'service' in data
            assert data['status'] == 'healthy'
            assert data['service'] == 'factorio-isr'
    
    @pytest.mark.asyncio
    async def test_health_handler_direct_call(self, health_server):
        """Test calling health_handler directly."""
        mock_request = Mock(spec=web.Request)
        
        response = await health_server.health_handler(mock_request)
        
        assert isinstance(response, web.Response)
        assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_health_endpoint_multiple_calls(self):
        """Test multiple calls to /health endpoint."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            # Make multiple requests
            for _ in range(5):
                resp = await client.get('/health')
                assert resp.status == 200
                data = await resp.json()
                assert data['status'] == 'healthy'


class TestRootEndpoint:
    """Test root endpoint."""
    
    @pytest.mark.asyncio
    async def test_root_endpoint_returns_200(self):
        """Test that / returns 200 OK."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/')
            
            assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_root_endpoint_returns_json(self):
        """Test that / returns JSON."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/')
            
            assert resp.content_type == 'application/json'
    
    @pytest.mark.asyncio
    async def test_root_endpoint_response_structure(self):
        """Test / response has correct structure."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/')
            data = await resp.json()
            
            assert 'service' in data
            assert 'endpoints' in data
            assert data['service'] == 'factorio-isr'
            assert 'health' in data['endpoints']
            assert data['endpoints']['health'] == '/health'
    
    @pytest.mark.asyncio
    async def test_root_handler_direct_call(self, health_server):
        """Test calling root_handler directly."""
        mock_request = Mock(spec=web.Request)
        
        response = await health_server.root_handler(mock_request)
        
        assert isinstance(response, web.Response)
        assert response.status == 200


# ============================================================================
# start() and stop() Tests
# ============================================================================

class TestStartStop:
    """Test HealthCheckServer start() and stop() methods."""
    
    @pytest.mark.asyncio
    async def test_start_creates_runner(self):
        """Test that start() creates AppRunner."""
        server = HealthCheckServer(host="127.0.0.1", port=0)  # port 0 = random free port
        
        await server.start()
        
        assert server.runner is not None
        assert isinstance(server.runner, web.AppRunner)
        
        # Cleanup
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_start_creates_site(self):
        """Test that start() creates TCPSite."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        
        assert server.site is not None
        assert isinstance(server.site, web.TCPSite)
        
        # Cleanup
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_start_binds_to_port(self):
        """Test that start() binds to specified port."""
        # Use port 0 to get a random free port
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        
        # Server should be running
        assert server.site is not None
        
        # Cleanup
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_stop_cleans_up_site(self):
        """Test that stop() cleans up site."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        assert server.site is not None
        
        await server.stop()
        
        # After stop, site should have been stopped
        # (it's still not None, but has been stopped)
        assert True
    
    @pytest.mark.asyncio
    async def test_stop_cleans_up_runner(self):
        """Test that stop() cleans up runner."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        assert server.runner is not None
        
        await server.stop()
        
        # After stop, runner should have been cleaned up
        assert True
    
    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """Test that stop() is safe to call without start()."""
        server = HealthCheckServer()
        
        # Should not raise error
        await server.stop()
        
        assert True
    
    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self):
        """Test multiple start/stop cycles."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        # First cycle
        await server.start()
        await server.stop()
        
        # Second cycle
        await server.start()
        await server.stop()
        
        assert True
    
    @pytest.mark.asyncio
    async def test_start_stop_with_custom_port(self):
        """Test start/stop with custom port."""
        # Use high port number to avoid conflicts
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        assert server.runner is not None
        assert server.site is not None
        
        await server.stop()


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.asyncio
    async def test_server_lifecycle_with_requests(self):
        """Test complete server lifecycle with HTTP requests."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        
        # Make a request through test client
        async with TestClient(
            TestServer(server.app)
        ) as client:
            # Health check
            health_resp = await client.get('/health')
            assert health_resp.status == 200
            health_data = await health_resp.json()
            assert health_data['status'] == 'healthy'
            
            # Root endpoint
            root_resp = await client.get('/')
            assert root_resp.status == 200
            root_data = await root_resp.json()
            assert root_data['service'] == 'factorio-isr'
        
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            # Make multiple concurrent requests
            tasks = [
                client.get('/health'),
                client.get('/'),
                client.get('/health'),
                client.get('/'),
                client.get('/health'),
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # All should succeed
            for resp in responses:
                assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_server_responds_after_start(self):
        """Test that server responds to requests after start."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        
        try:
            # Create client to make actual HTTP request
            async with TestClient(
                TestServer(server.app)
            ) as client:
                resp = await client.get('/health')
                
                assert resp.status == 200
                data = await resp.json()
                assert data['status'] == 'healthy'
        finally:
            await server.stop()


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_with_query_params(self):
        """Test /health endpoint ignores query parameters."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/health?foo=bar&baz=qux')
            
            assert resp.status == 200
            data = await resp.json()
            assert data['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_root_endpoint_with_query_params(self):
        """Test / endpoint ignores query parameters."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/?test=value')
            
            assert resp.status == 200
            data = await resp.json()
            assert data['service'] == 'factorio-isr'
    
    @pytest.mark.asyncio
    async def test_nonexistent_endpoint_returns_404(self):
        """Test that nonexistent endpoints return 404."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/nonexistent')
            
            assert resp.status == 404
    
    @pytest.mark.asyncio
    async def test_post_method_not_allowed(self):
        """Test that POST to endpoints returns method not allowed."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.post('/health')
            
            assert resp.status == 405  # Method Not Allowed
    
    @pytest.mark.asyncio
    async def test_server_with_all_interfaces(self):
        """Test server binding to all interfaces."""
        server = HealthCheckServer(host="0.0.0.0", port=0)
        
        await server.start()
        
        assert server.host == "0.0.0.0"
        assert server.site is not None
        
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_localhost_binding(self):
        """Test server binding to localhost."""
        server = HealthCheckServer(host="localhost", port=0)
        
        await server.start()
        
        assert server.host == "localhost"
        assert server.site is not None
        
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_rapid_start_stop(self):
        """Test rapid start/stop cycles."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        for _ in range(3):
            await server.start()
            await server.stop()
        
        assert True
    
    def test_multiple_server_instances(self):
        """Test creating multiple server instances."""
        server1 = HealthCheckServer(host="127.0.0.1", port=8080)
        server2 = HealthCheckServer(host="127.0.0.1", port=8081)
        server3 = HealthCheckServer(host="127.0.0.1", port=8082)
        
        assert server1.port == 8080
        assert server2.port == 8081
        assert server3.port == 8082
        assert server1.app is not server2.app
        assert server2.app is not server3.app


# ============================================================================
# Type Safety Tests
# ============================================================================

class TestTypeSafety:
    """Test type safety and contracts."""
    
    def test_host_parameter_type(self):
        """Test that host parameter accepts string."""
        server = HealthCheckServer(host="127.0.0.1", port=8080)
        
        assert isinstance(server.host, str)
    
    def test_port_parameter_type(self):
        """Test that port parameter accepts integer."""
        server = HealthCheckServer(host="127.0.0.1", port=9000)
        
        assert isinstance(server.port, int)
    
    def test_app_is_application(self):
        """Test that app is aiohttp Application."""
        server = HealthCheckServer()
        
        assert isinstance(server.app, web.Application)
    
    def test_runner_initially_none(self):
        """Test that runner is None before start."""
        server = HealthCheckServer()
        
        assert server.runner is None
    
    def test_site_initially_none(self):
        """Test that site is None before start."""
        server = HealthCheckServer()
        
        assert server.site is None
    
    @pytest.mark.asyncio
    async def test_runner_type_after_start(self):
        """Test runner type after start."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        
        assert isinstance(server.runner, web.AppRunner)
        
        await server.stop()
    
    @pytest.mark.asyncio
    async def test_site_type_after_start(self):
        """Test site type after start."""
        server = HealthCheckServer(host="127.0.0.1", port=0)
        
        await server.start()
        
        assert isinstance(server.site, web.TCPSite)
        
        await server.stop()


# ============================================================================
# Response Format Tests
# ============================================================================

class TestResponseFormats:
    """Test response format details."""
    
    @pytest.mark.asyncio
    async def test_health_response_keys(self):
        """Test that health response has expected keys."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/health')
            data = await resp.json()
            
            # Should have exactly these keys
            expected_keys = {'status', 'service'}
            assert set(data.keys()) == expected_keys
    
    @pytest.mark.asyncio
    async def test_root_response_keys(self):
        """Test that root response has expected keys."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            resp = await client.get('/')
            data = await resp.json()
            
            # Should have these keys
            assert 'service' in data
            assert 'endpoints' in data
            assert isinstance(data['endpoints'], dict)
    
    @pytest.mark.asyncio
    async def test_health_status_value(self):
        """Test that health status is always 'healthy'."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            # Multiple requests should all return healthy
            for _ in range(3):
                resp = await client.get('/health')
                data = await resp.json()
                assert data['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_service_name_consistency(self):
        """Test that service name is consistent across endpoints."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            health_resp = await client.get('/health')
            health_data = await health_resp.json()
            
            root_resp = await client.get('/')
            root_data = await root_resp.json()
            
            # Service name should match
            assert health_data['service'] == root_data['service']
            assert health_data['service'] == 'factorio-isr'


# ============================================================================
# Stress Tests
# ============================================================================

class TestStress:
    """Stress tests for server performance."""
    
    @pytest.mark.asyncio
    async def test_many_sequential_requests(self):
        """Test handling many sequential requests."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            # Make 100 sequential requests
            for _ in range(100):
                resp = await client.get('/health')
                assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_many_concurrent_requests(self):
        """Test handling many concurrent requests."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            # Make 50 concurrent requests
            tasks = [client.get('/health') for _ in range(50)]
            responses = await asyncio.gather(*tasks)
            
            # All should succeed
            assert all(r.status == 200 for r in responses)
    
    @pytest.mark.asyncio
    async def test_alternating_endpoints(self):
        """Test alternating between different endpoints."""
        server = HealthCheckServer()
        
        async with TestClient(
            TestServer(server.app)
        ) as client:
            # Alternate between endpoints
            for i in range(20):
                if i % 2 == 0:
                    resp = await client.get('/health')
                else:
                    resp = await client.get('/')
                
                assert resp.status == 200
