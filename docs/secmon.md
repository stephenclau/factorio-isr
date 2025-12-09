# Security Monitor Configuration Reference

Configure security monitoring, alert routing, and rate limits via config/secmon.yml.

## Table of Contents
- Overview
- File format
- Structure
- Field reference
- Examples
- Best practices
- Testing
- Next steps

---

## Overview
The security monitor inspects events for risky patterns, applies per‑category policies (enable/disable, auto_ban, severity), and posts alerts to a dedicated Discord channel.   
It also enforces basic rate limits for sensitive actions like mass mentions. 

---

## File format
Place the file at ./config/secmon.yml and define a top-level security section with alert routing, patterns, and rate_limits. 

```yaml

config/secmon.yml
security:
enabled: true

Discord channel (by name) for security alerts
alert_channel: "security-alerts"

Monitored categories and policies
patterns:
code_injection:
    enabled: true
    auto_ban: true
    severity: critical
path_traversal:
    enabled: true
    auto_ban: false
    severity: high
command_injection:
    enabled: true
    auto_ban: true
    severity: critical

Basic rate limits
rate_limits:
    mention_admin:
    max_events: 5
    time_window_seconds: 60
mention_everyone:
    max_events: 1
    time_window_seconds: 300
chat_message:
    max_events: 20
    time_window_seconds: 60

```

---

## Structure
- security.enabled: Master switch; disables or enables the security monitor.   
- security.alert_channel: Discord channel (by name) where alerts are posted.   
- security.patterns: Policy per category (enabled, auto_ban, severity).   
- security.rate_limits: Sliding-window limits by action key with max_events and time_window_seconds. 

---

## Field reference
- patterns.<name>.enabled: Toggle detection of a given category (e.g., code_injection).   
- patterns.<name>.auto_ban: If true, flag for automated moderation for that category.   
- patterns.<name>.severity: One of critical/high/etc., used for alert emphasis.   
- rate_limits.<key>.max_events: Maximum events within window.   
- rate_limits.<key>.time_window_seconds: Window length in seconds. 

---

## Examples
- Enable high‑severity auto_ban for code injection and command injection; keep path traversal visible but non‑banning with severity high.   
- Throttle @everyone to 1 event per 5 minutes and admin mentions to 5 per minute to reduce abuse. 

---

## Best practices
- Start with alerting first; enable auto_ban per category only after reviewing alert volume and false‑positive risk.   
- Use a dedicated alert_channel with restricted posting permissions for clarity. 

---

## Testing
- Trigger a benign event matching a monitored category and verify an alert arrives in the alert_channel.   
- Attempt repeated mentions (like @everyone) and confirm events are rate‑limited per the configured thresholds. 

---

## Next steps
- See Pattern Syntax to understand how base events are parsed before security policies apply.   
- Review Troubleshooting for Discord permission issues impacting alert delivery. 

