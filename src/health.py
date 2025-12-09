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

"""
Health check HTTP server for container orchestration.

Provides /health endpoint for Docker healthchecks and monitoring.
"""
import asyncio
from typing import Optional

from aiohttp import web
import structlog

logger = structlog.get_logger()


class HealthCheckServer:
    """Simple HTTP server for health checks."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Initialize health check server.
        
        Args:
            host: Host to bind to (default: 0.0.0.0)
            port: Port to bind to (default: 8080)
        """
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Configure HTTP routes."""
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/", self.root_handler)
    
    async def health_handler(self, request: web.Request) -> web.Response:
        """
        Health check endpoint.
        
        Returns:
            200 OK with status info
        """
        return web.json_response({
            "status": "healthy",
            "service": "factorio-isr"
        })
    
    async def root_handler(self, request: web.Request) -> web.Response:
        """
        Root endpoint.
        
        Returns:
            200 OK with service info
        """
        return web.json_response({
            "service": "factorio-isr",
            "endpoints": {
                "health": "/health"
            }
        })
    
    async def start(self) -> None:
        """Start the health check server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(
            self.runner,
            self.host,
            self.port
        )
        await self.site.start()
        
        logger.info(
            "health_server_started",
            host=self.host,
            port=self.port
        )
    
    async def stop(self) -> None:
        """Stop the health check server."""
        # Use assertions - these should never be None if start() was called
        if self.site is not None:
            await self.site.stop()
        
        if self.runner is not None:
            await self.runner.cleanup()
        
        logger.info("health_server_stopped")
