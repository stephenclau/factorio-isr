---
layout: default
title: Mentions Guide
---

# Mentions Configuration Reference

Complete guide to mapping in‑game @tokens to Discord mentions using config/mentions.yml.

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
Mentions map simple in‑game tokens like @board or @ops to actual Discord mentions for roles or users during Discord message rendering.   
This document describes how to define role mention aliases in config/mentions.yml and how the bot resolves them at send time. 

---

## File format
Mentions are defined in YAML under a top-level mentions section with a roles map of Discord role names to alias lists.   
Place the file at ./config/mentions.yml. 

```yaml

config/mentions.yml
mentions:
    roles:
        admins:
        - "admins"
        board of directors:
        - "board-of-directors"
        - "board"
        ```
---

## Structure
- mentions: Root key for all mention configuration. 
- roles: Map of Discord role display names to a list of in‑game alias tokens. 
- Aliases: Each string under a role is an acceptable @token players can type in Factorio chat. 

---

## Field reference
- Role key (e.g., "board of directors"): Must match the Discord role’s display name; spaces are allowed.   
- Aliases (e.g., "board", "board-of-directors"): Tokens typed as @board or @board-of-directors in-game will resolve to that role mention if present. 

---

## Examples
- @board or @board-of-directors in chat will resolve to the “board of directors” role mention if the bot can find that role by name.   
- @ops will resolve to the “operations” role mention when the role exists and aliases include "ops". 

---

## Best practices
- Prefer short, memorable aliases like "ops", "board", "chiefs".   
- Use hyphens for multiword aliases (e.g., "board-of-directors") and keep role names human-readable (spaces in role keys are fine). 

---

## Testing
- Type a chat line in Factorio like: “@ops help at oil.” The parser will attach a mentions list, and the bot will append the resolved Discord mentions.   
- Check logs for mentions_detected and mention_resolved_to_role entries to confirm mapping. 

---

## Next steps
- See Pattern Syntax for how chat events are parsed and routed to Discord.   
- See Troubleshooting for diagnosing mention resolution and permissions. 
