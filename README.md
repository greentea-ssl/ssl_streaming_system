# SSL Streaming System

A real-time event streaming and visualization system for RoboCup SSL (Small Size League) matches, featuring game event processing, audio announcements, and field visualization.

This system is designed for use with the RoboCup SSL Game Controller:
https://github.com/RoboCup-SSL/ssl-game-controller

## Overview

This system connects to the RoboCup SSL Game Controller, processes game events, and provides:

1. **Orchestrator** - Core component that receives referee messages, detects events, and publishes to other modules
2. **Audio Playback** - ⚠️ (Work in Progress, currently not functional) Announces game events with configurable audio
3. **Placement Visualization** - Web-based interface showing the ball placement positions on the field

## System Architecture

```
SSL Game Controller (external) ──► EventListener ──► Orchestrator ──► ZMQ Publisher
                                                         │
                                     ┌───────────────────┴───────────────────┐
                                     ▼                                       ▼
                      AudioPlayback (WIP, not functional)          ZMQ-WebSocket Bridge
                                                                            │
                                                                            ▼
                                                                    Web Visualization
```

## Requirements

- Python 3.12+
- Poetry
- Docker and Docker Compose (recommended for deployment)
- ZeroMQ

## Installation

### Using Docker (Recommended)

```bash
# Clone the repository
git clone --recursive git@github.com:greentea-ssl/ssl_streaming_system.git
cd ssl-streaming-system

# Build and start the containers
docker-compose up -d
```

### Manual Setup

```bash
# Clone the repository 
git clone --recursive git@github.com:greentea-ssl/ssl_streaming_system.git
cd ssl-streaming-system

# Install dependencies using Poetry
pip install poetry
poetry install --no-root

# Compile Protobuf files
bash ./compile_proto.bash

# Set required environment variables
export GC_MULTICAST_GROUP=224.5.23.1
export GC_MULTICAST_PORT=10003
export PYTHONPATH="${PYTHONPATH}:$(pwd)/proto"

# Run the system
python -m orchestrator --orchestrator-config config/config_orchestrator.yaml --priority-config config/config_priority.yaml

# In a separate terminal, run the field visualization
cd placement_visualizer
bash ./start_viz.sh
# Then access the visualization at http://localhost:8080 in your browser
```

## Components

### Orchestrator

The core event processing engine that:
- Connects to the SSL Game Controller via multicast
- Processes game events based on rules
- Publishes events to other modules via ZeroMQ
⚠️ **Note: The implementation is in progress thus the published contents are incomplete

#### Configuration Files:
- `config/config_orchestrator.yaml` - Publisher settings
- `config/config_priority.yaml` - Event priority definitions

### Audio Playback (Work in Progress)

⚠️ **Note: This component is currently not functional and under development.**

Designed to subscribe to the orchestrator and play audio announcements for game events.

#### Configuration:
- `config/config_audio.yaml` - Audio mapping and settings

### Placement Visualization

A web interface showing real-time ball placement on the field:

- Configurable field dimensions (default RoboCup SSL: 12000 × 9000 mm)
- Real-time display of ball placement positions
- Event history tracking (Only placement)
- Coordinate display
