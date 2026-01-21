#!/usr/bin/env python3
"""Hafiportrait Photographer Workflow (Standalone).

This file is kept as a stable entrypoint for photographers. The implementation
lives in the `hafiportrait_workflow` package to keep the code modular and easier
to debug/maintain.

SIMPLE mode behavior is unchanged.
"""

from __future__ import annotations

from hafiportrait_workflow.runner import main


if __name__ == "__main__":
    main()
