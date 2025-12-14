# 🔍 Handler Entry Logging Implementation Guide

**Status:** Ready for surgical implementation  
**Target File:** `src/bot/commands/command_handlers.py`  
**Total Handlers:** 25  
**Pattern:** Add `logger.info("handler_invoked", handler="[ClassName]", user=interaction.user.name)` immediately after `async def execute(...)` docstring

---

## 📊 Handlers to Update (25 Total)

### 📊 Server Information (7)
- [ ] `StatusCommandHandler` - Line ~212
- [ ] `PlayersCommandHandler` - Line ~381
- [ ] `VersionCommandHandler` - Line ~421
- [ ] `SeedCommandHandler` - Line ~461
- [ ] `EvolutionCommandHandler` - Line ~501
- [ ] `AdminsCommandHandler` - Line ~623
- [ ] `HealthCommandHandler` - Line ~663

### 👥 Player Management (7)
- [ ] `KickCommandHandler` - Line ~724
- [ ] `BanCommandHandler` - Line ~773
- [ ] `UnbanCommandHandler` - Line ~822
- [ ] `MuteCommandHandler` - Line ~870
- [ ] `UnmuteCommandHandler` - Line ~918
- [ ] `PromoteCommandHandler` - Line ~966
- [ ] `DemoteCommandHandler` - Line ~1014

### 🔧 Server Management (4)
- [ ] `SaveCommandHandler` - Line ~1062
- [ ] `BroadcastCommandHandler` - Line ~1109
- [ ] `WhisperCommandHandler` - Line ~1156
- [ ] `WhitelistCommandHandler` - Line ~1203

### 🎮 Game Control (3)
- [ ] `ClockCommandHandler` - Line ~1300
- [ ] `SpeedCommandHandler` - Line ~1408
- [ ] `ResearchCommandHandler` - Line ~1464

### 🛠️ Advanced (2)
- [ ] `RconCommandHandler` - Line ~1710
- [ ] `HelpCommandHandler` - Line ~1765

### 🌍 Multi-Server (2)
- [ ] `ServersCommandHandler` - Line ~1808
- [ ] `ConnectCommandHandler` - Line ~1879

---

## 🔧 Implementation Pattern

**For each handler's `execute()` method:**

```python
async def execute(self, interaction: discord.Interaction) -> CommandResult:
    """Execute [command] command."""
    logger.info("handler_invoked", handler="[ClassName]", user=interaction.user.name)
    
    # ... rest of method ...
```

### Variant for handlers with additional parameters:

```python
async def execute(self, interaction: discord.Interaction, player: str, reason: Optional[str] = None) -> CommandResult:
    """Execute [command] command."""
    logger.info("handler_invoked", handler="[ClassName]", user=interaction.user.name, player=player)
    
    # ... rest of method ...
```

---

## 🎯 Detailed Patches

### 1️⃣ StatusCommandHandler
**Location:** Line ~212  
**Current:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute status command with explicit dependency injection."""
        # Rate limiting
```

**New:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute status command with explicit dependency injection."""
        logger.info("handler_invoked", handler="StatusCommandHandler", user=interaction.user.name)
        
        # Rate limiting
```

---

### 2️⃣ PlayersCommandHandler
**Location:** Line ~381  
**Current:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute players command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute players command."""
        logger.info("handler_invoked", handler="PlayersCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 3️⃣ VersionCommandHandler
**Location:** Line ~421  
**Current:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute version command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute version command."""
        logger.info("handler_invoked", handler="VersionCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 4️⃣ SeedCommandHandler
**Location:** Line ~461  
**Current:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute seed command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute seed command."""
        logger.info("handler_invoked", handler="SeedCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 5️⃣ EvolutionCommandHandler
**Location:** Line ~501  
**Current:**
```python
    async def execute(
        self, interaction: discord.Interaction, target: str
    ) -> CommandResult:
        """Execute evolution command for single surface or aggregate all."""
        # Rate limiting
```

**New:**
```python
    async def execute(
        self, interaction: discord.Interaction, target: str
    ) -> CommandResult:
        """Execute evolution command for single surface or aggregate all."""
        logger.info("handler_invoked", handler="EvolutionCommandHandler", user=interaction.user.name)
        
        # Rate limiting
```

---

### 6️⃣ AdminsCommandHandler
**Location:** Line ~623  
**Current:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute admins command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute admins command."""
        logger.info("handler_invoked", handler="AdminsCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 7️⃣ HealthCommandHandler
**Location:** Line ~663  
**Current:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute health command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute health command."""
        logger.info("handler_invoked", handler="HealthCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 8️⃣ KickCommandHandler
**Location:** Line ~724  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> CommandResult:
        """Execute kick command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> CommandResult:
        """Execute kick command."""
        logger.info("handler_invoked", handler="KickCommandHandler", user=interaction.user.name, player=player)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 9️⃣ BanCommandHandler
**Location:** Line ~773  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> CommandResult:
        """Execute ban command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        reason: Optional[str] = None,
    ) -> CommandResult:
        """Execute ban command."""
        logger.info("handler_invoked", handler="BanCommandHandler", user=interaction.user.name, player=player)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 🔟 UnbanCommandHandler
**Location:** Line ~822  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute unban command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute unban command."""
        logger.info("handler_invoked", handler="UnbanCommandHandler", user=interaction.user.name, player=player)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣1️⃣ MuteCommandHandler
**Location:** Line ~870  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute mute command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute mute command."""
        logger.info("handler_invoked", handler="MuteCommandHandler", user=interaction.user.name, player=player)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣2️⃣ UnmuteCommandHandler
**Location:** Line ~918  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute unmute command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute unmute command."""
        logger.info("handler_invoked", handler="UnmuteCommandHandler", user=interaction.user.name, player=player)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣3️⃣ PromoteCommandHandler
**Location:** Line ~966  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute promote command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute promote command."""
        logger.info("handler_invoked", handler="PromoteCommandHandler", user=interaction.user.name, player=player)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣4️⃣ DemoteCommandHandler
**Location:** Line ~1014  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute demote command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
    ) -> CommandResult:
        """Execute demote command."""
        logger.info("handler_invoked", handler="DemoteCommandHandler", user=interaction.user.name, player=player)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣5️⃣ SaveCommandHandler
**Location:** Line ~1062  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        name: Optional[str] = None,
    ) -> CommandResult:
        """Execute save command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        name: Optional[str] = None,
    ) -> CommandResult:
        """Execute save command."""
        logger.info("handler_invoked", handler="SaveCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣6️⃣ BroadcastCommandHandler
**Location:** Line ~1109  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> CommandResult:
        """Execute broadcast command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> CommandResult:
        """Execute broadcast command."""
        logger.info("handler_invoked", handler="BroadcastCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣7️⃣ WhisperCommandHandler
**Location:** Line ~1156  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        message: str,
    ) -> CommandResult:
        """Execute whisper command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        player: str,
        message: str,
    ) -> CommandResult:
        """Execute whisper command."""
        logger.info("handler_invoked", handler="WhisperCommandHandler", user=interaction.user.name, player=player)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣8️⃣ WhitelistCommandHandler
**Location:** Line ~1203  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        action: str,
        player: Optional[str] = None,
    ) -> CommandResult:
        """Execute whitelist command with multi-action dispatch."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        action: str,
        player: Optional[str] = None,
    ) -> CommandResult:
        """Execute whitelist command with multi-action dispatch."""
        logger.info("handler_invoked", handler="WhitelistCommandHandler", user=interaction.user.name, action=action)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 1️⃣9️⃣ ClockCommandHandler
**Location:** Line ~1300  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        value: Optional[str] = None,
    ) -> CommandResult:
        """Execute clock command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        value: Optional[str] = None,
    ) -> CommandResult:
        """Execute clock command."""
        logger.info("handler_invoked", handler="ClockCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 2️⃣0️⃣ SpeedCommandHandler
**Location:** Line ~1408  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        value: float,
    ) -> CommandResult:
        """Execute speed command."""
        # Validate range
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        value: float,
    ) -> CommandResult:
        """Execute speed command."""
        logger.info("handler_invoked", handler="SpeedCommandHandler", user=interaction.user.name, speed=value)
        
        # Validate range
```

---

### 2️⃣1️⃣ ResearchCommandHandler
**Location:** Line ~1464  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        force: Optional[str],
        action: Optional[str],
        technology: Optional[str],
    ) -> CommandResult:
        """Execute research command with multi-force support."""
        # Rate limiting
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        force: Optional[str],
        action: Optional[str],
        technology: Optional[str],
    ) -> CommandResult:
        """Execute research command with multi-force support."""
        logger.info("handler_invoked", handler="ResearchCommandHandler", user=interaction.user.name, force=force)
        
        # Rate limiting
```

---

### 2️⃣2️⃣ RconCommandHandler
**Location:** Line ~1710  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        command: str,
    ) -> CommandResult:
        """Execute raw RCON command."""
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        command: str,
    ) -> CommandResult:
        """Execute raw RCON command."""
        logger.info("handler_invoked", handler="RconCommandHandler", user=interaction.user.name)
        
        is_limited, retry = self.rate_limiter.is_rate_limited(interaction.user.id)
```

---

### 2️⃣3️⃣ HelpCommandHandler
**Location:** Line ~1765  
**Current:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute help command."""
        help_text = (
```

**New:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute help command."""
        logger.info("handler_invoked", handler="HelpCommandHandler", user=interaction.user.name)
        
        help_text = (
```

---

### 2️⃣4️⃣ ServersCommandHandler
**Location:** Line ~1808  
**Current:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute servers command."""
        if not self.server_manager:
```

**New:**
```python
    async def execute(self, interaction: discord.Interaction) -> CommandResult:
        """Execute servers command."""
        logger.info("handler_invoked", handler="ServersCommandHandler", user=interaction.user.name)
        
        if not self.server_manager:
```

---

### 2️⃣5️⃣ ConnectCommandHandler
**Location:** Line ~1879  
**Current:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        server: str,
    ) -> CommandResult:
        """Execute connect command."""
        if not self.server_manager:
```

**New:**
```python
    async def execute(
        self,
        interaction: discord.Interaction,
        server: str,
    ) -> CommandResult:
        """Execute connect command."""
        logger.info("handler_invoked", handler="ConnectCommandHandler", user=interaction.user.name, server=server)
        
        if not self.server_manager:
```

---

## ✅ Verification Checklist

After implementation:

- [ ] All 25 handlers have entry logging
- [ ] Handler names match class names exactly
- [ ] User name captured as `user=interaction.user.name`
- [ ] Additional context captured where relevant (player, action, server, etc.)
- [ ] Single blank line after logger.info call
- [ ] No logic changes, purely additive
- [ ] Tests pass (all handlers still execute correctly)
- [ ] Run sample commands to verify logs contain `handler_invoked`

---

## 🚀 Commit Message

```
🔍 Add handler entry logging across all 25 command handlers - Phase 1

- Add logger.info("handler_invoked", ...) at start of each handler's execute()
- Captures handler name, user, and context-specific parameters
- Enables complete command lifecycle traceability
- No logic changes, purely additive logging
- Closure comment: Logging Audit Report - Issue findings CRITICAL
```

---

## 💡 Next Phase

After completing Phase 1 (entry logging), Phase 2 would add:
- Exit logging in success/error paths
- Handler-level rate limit logging
- Performance metrics capture

---

**Document Version:** 1.0  
**Created:** December 14, 2025  
**Prepared by:** Principal Engineering Dev (Python ISR Project)