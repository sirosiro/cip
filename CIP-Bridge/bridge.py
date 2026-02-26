#!/usr/bin/env python3
# CIP-Bridge: Fractal AI Orchestrator
# Licensed under the MIT License. See LICENSE file in the project root for full license information.
# Copyright (c) 2026 Kouichi Shiroma

import sys
import os

# パッケージパスを通す
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from cip_bridge.entry import main

if __name__ == "__main__":
    main()