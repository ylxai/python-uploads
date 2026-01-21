from __future__ import annotations

from .config import build_config, parse_args, resolve_args_interactive
from .errors import ConfigError
from .watcher import run_watch


def main() -> None:
    try:
        args = parse_args()
        args = resolve_args_interactive(args)
        cfg = build_config(args)
        run_watch(cfg)
    except ConfigError as e:
        # Keep CLI behavior: exit with a clear message.
        raise SystemExit(str(e))
