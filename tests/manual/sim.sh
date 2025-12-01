#!/bin/bash
set -e  # Exit on any error

# Player chat
echo "2025-11-30 23:25:00 [CHAT] Alice: Testing chat!" >> ../logs/console.log

# Player join
echo "2025-11-30 23:25:05 [JOIN] Bob joined the game" >> ../logs/console.log

# Player leave  
echo "2025-11-30 23:25:10 [LEAVE] Bob left the game" >> ../logs/console.log

# Death
echo "2025-11-30 23:25:15 Charlie was killed by a biter." >> ./logs/console.log

# Research complete
echo "2025-11-30 23:25:20 Technology 'Advanced electronics' has been completed." >> ../logs/console.log

# Rocket launch
echo "2025-11-30 23:25:25 [ROCKET] Rocket launched!" >> ../logs/console.log
