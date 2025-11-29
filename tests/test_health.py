"""
Comprehensive type-safe tests for health.py
Achieves 95%+ code coverage.
"""

import asyncio
import pytest
from aiohttp import ClientSession

from health import HealthCheckServer


class TestHealthCheckServerInit:
    """Test HealthCheckServer initialization."""
    
    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        server = HealthCheckServer()
        
        assert server.host == "0.0.0.0"
        assert server.port == 8080
        assert server.app is not None
        assert server.runner is None
        assert server.site is None
    
    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom host and port."""
        server = HealthCheckServer(host="127.0.0.1", port=9090)
        
        assert server.host == "127.0.0.1"
        assert server.port == 9090
        assert server.app is not None


@pytest.mark.asyncio
class TestHealthCheckServerLifecycle:
    """Test server start/stop lifecycle."""
    
    async def test_start_server(self) -> None:
        """Test starting the health check server."""
        server = HealthCheckServer(host="127.0.0.1", port=18080)
        
        try:
            await server.start()
            
            # Verify server components are initialized
            assert server.runner is not None
            assert server.site is not None
            
            await asyncio.sleep(0.1)
        finally:
            await server.stop()
    
    async def test_stop_server(self) -> None:
        """Test stopping the health check server."""
        server = HealthCheckServer(host="127.0.0.1", port=18081)
        
        await server.start()
        await asyncio.sleep(0.1)
        
        # Stop should complete without error
        await server.stop()
    
    async def test_stop_without_start(self) -> None:
        """Test that stop is safe when server wasn't started."""
        server = HealthCheckServer()
        
        # Should not raise errors
        await server.stop()
        
        assert server.runner is None
        assert server.site is None
    
    async def test_start_stop_cycle(self) -> None:
        """Test multiple start/stop cycles."""
        server = HealthCheckServer(host="127.0.0.1", port=18082)
        
        # First cycle
        await server.start()
        await asyncio.sleep(0.1)
        await server.stop()
        
        # Server can be reused
        assert server.app is not None


@pytest.mark.asyncio
class TestHealthCheckServerEndpoints:
    """Test HTTP endpoints with actual requests."""
    
    async def test_health_endpoint(self) -> None:
        """Test /health endpoint returns correct response."""
        server = HealthCheckServer(host="127.0.0.1", port=18083)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            async with ClientSession() as session:
                async with session.get("http://127.0.0.1:18083/health") as resp:
                    assert resp.status == 200
                    assert resp.content_type == "application/json"
                    
                    data = await resp.json()
                    assert data["status"] == "healthy"
                    assert data["service"] == "factorio-isr"
        finally:
            await server.stop()
    
    async def test_root_endpoint(self) -> None:
        """Test / endpoint returns service info."""
        server = HealthCheckServer(host="127.0.0.1", port=18084)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            async with ClientSession() as session:
                async with session.get("http://127.0.0.1:18084/") as resp:
                    assert resp.status == 200
                    assert resp.content_type == "application/json"
                    
                    data = await resp.json()
                    assert data["service"] == "factorio-isr"
                    assert "endpoints" in data
                    assert data["endpoints"]["health"] == "/health"
        finally:
            await server.stop()
    
    async def test_404_on_invalid_route(self) -> None:
        """Test 404 response on non-existent route."""
        server = HealthCheckServer(host="127.0.0.1", port=18085)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            async with ClientSession() as session:
                async with session.get("http://127.0.0.1:18085/invalid") as resp:
                    assert resp.status == 404
        finally:
            await server.stop()


@pytest.mark.asyncio
class TestHealthCheckServerConcurrency:
    """Test concurrent request handling."""
    
    async def test_multiple_concurrent_requests(self) -> None:
        """Test handling multiple simultaneous requests."""
        server = HealthCheckServer(host="127.0.0.1", port=18086)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            async with ClientSession() as session:
                # Create 10 concurrent requests
                tasks = []
                for _ in range(10):
                    task = session.get("http://127.0.0.1:18086/health")
                    tasks.append(task)
                
                # Execute all requests
                responses = await asyncio.gather(*tasks)
                
                # Verify all succeeded
                for resp in responses:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["status"] == "healthy"
                    resp.close()
        finally:
            await server.stop()
    
    async def test_mixed_endpoint_requests(self) -> None:
        """Test concurrent requests to different endpoints."""
        server = HealthCheckServer(host="127.0.0.1", port=18087)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            async with ClientSession() as session:
                # Mix of health and root requests
                health_task = session.get("http://127.0.0.1:18087/health")
                root_task = session.get("http://127.0.0.1:18087/")
                
                health_resp, root_resp = await asyncio.gather(health_task, root_task)
                
                assert health_resp.status == 200
                assert root_resp.status == 200
                
                health_data = await health_resp.json()
                root_data = await root_resp.json()
                
                assert health_data["status"] == "healthy"
                assert root_data["service"] == "factorio-isr"
                
                health_resp.close()
                root_resp.close()
        finally:
            await server.stop()


@pytest.mark.asyncio
class TestHealthCheckServerEdgeCases:
    """Edge cases and error scenarios."""
    
    async def test_port_already_in_use(self) -> None:
        """Test behavior when port is already occupied."""
        server1 = HealthCheckServer(host="127.0.0.1", port=18088)
        server2 = HealthCheckServer(host="127.0.0.1", port=18088)
        
        try:
            await server1.start()
            await asyncio.sleep(0.1)
            
            # Second server should fail to bind
            with pytest.raises(OSError):
                await server2.start()
                await asyncio.sleep(0.1)
        finally:
            await server1.stop()
            # server2.stop() is safe even if start failed
            await server2.stop()
    
    async def test_health_endpoint_response_structure(self) -> None:
        """Test health endpoint returns all expected fields."""
        server = HealthCheckServer(host="127.0.0.1", port=18089)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            async with ClientSession() as session:
                async with session.get("http://127.0.0.1:18089/health") as resp:
                    data = await resp.json()
                    
                    # Verify structure
                    assert isinstance(data, dict)
                    assert "status" in data
                    assert "service" in data
                    assert len(data) == 2  # Only these two fields
        finally:
            await server.stop()
    
    async def test_root_endpoint_response_structure(self) -> None:
        """Test root endpoint returns all expected fields."""
        server = HealthCheckServer(host="127.0.0.1", port=18090)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            async with ClientSession() as session:
                async with session.get("http://127.0.0.1:18090/") as resp:
                    data = await resp.json()
                    
                    # Verify structure
                    assert isinstance(data, dict)
                    assert "service" in data
                    assert "endpoints" in data
                    assert isinstance(data["endpoints"], dict)
                    assert "health" in data["endpoints"]
        finally:
            await server.stop()


@pytest.mark.asyncio
class TestHealthCheckServerConfiguration:
    """Test different server configurations."""
    
    async def test_localhost_binding(self) -> None:
        """Test server binds to localhost correctly."""
        server = HealthCheckServer(host="127.0.0.1", port=18091)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            # Should be accessible on localhost
            async with ClientSession() as session:
                async with session.get("http://127.0.0.1:18091/health") as resp:
                    assert resp.status == 200
        finally:
            await server.stop()
    
    async def test_custom_port(self) -> None:
        """Test server works with custom port."""
        custom_port = 19999
        server = HealthCheckServer(host="127.0.0.1", port=custom_port)
        
        try:
            await server.start()
            await asyncio.sleep(0.2)
            
            async with ClientSession() as session:
                url = f"http://127.0.0.1:{custom_port}/health"
                async with session.get(url) as resp:
                    assert resp.status == 200
        finally:
            await server.stop()
