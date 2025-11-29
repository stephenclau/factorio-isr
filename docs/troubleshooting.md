# 🚧 Troubleshooting Guide

Common issues and solutions for Factorio ISR deployments.

## No Events Appearing in Discord

1. **Check log file path**
   - Make sure the log file exists and is readable by the container.
   - Example: `ls -la /path/to/factorio/console.log`
2. **Check webhook URL**
   - Test manually by sending a message:
   ```bash
   curl -X POST "YOUR_WEBHOOK_URL" -H "Content-Type: application/json" -d '{"content": "Test message"}'
   ```
3. **Check application logs**
   - `docker logs factorio-isr`
   - Look for "log_tailing_active", "message_sent"
4. **Check file permissions**
   - Execute: `docker exec factorio-isr cat /factorio/log/console.log`

## Events Parsed But Not Sent

1. **Discord rate limiting**
   - Look for `rate_limited` in logs.
   - Default: Max 1 message per 0.5 seconds.
2. **Network connectivity**
   - Try: `docker exec factorio-isr curl -I https://discord.com`

## Health Check Failing

- Test the health endpoint:
   ```bash
   curl http://localhost:8080/health
   docker exec factorio-isr curl http://localhost:8080/health
   ```

## Container Won't Start

- Check logs: `docker compose logs factorio-isr`
- Inspect configuration and file permissions.

## High Resource Usage

- Monitor: `docker stats factorio-isr`
- Check log file growth and rotation.
- Tune CPU/memory limits in Docker Compose or Swarm.

## Troubleshooting References

- [Configuration Guide](configuration.md)
- [Docker Deployment](docker-deployment.md)
- [Support / Issues](https://github.com/stephenclau/factorio-isr/issues)
