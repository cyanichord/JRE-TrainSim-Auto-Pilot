#!/usr/bin/env python3
"""Project entry point that starts the auto-pilot with the bundled config."""

import os
from pathlib import Path

from auto_pilot import main


def run():
    project_dir = Path(__file__).resolve().parent
    config_path = project_dir / "conf.yaml"
    os.chdir(project_dir)
    main(str(config_path))


if __name__ == "__main__":
    run()
