#!/usr/bin/env python
"""
Launch the Weather Platform web dashboard.

Usage:
    python run_dashboard.py [--port PORT] [--host HOST] [--interval MINUTES] [--no-scheduler]
"""
import argparse
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from weather_platform.web import create_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    parser = argparse.ArgumentParser(description='Run Weather Platform Dashboard')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--interval', type=int, default=60,
                        help='Pipeline run interval in minutes (default: 60)')
    parser.add_argument('--no-scheduler', action='store_true',
                        help='Disable automatic pipeline scheduling')

    args = parser.parse_args()

    project_path = Path(__file__).parent

    app = create_app(
        project_path=str(project_path),
        scheduler_interval=args.interval,
        enable_scheduler=not args.no_scheduler
    )

    print("=" * 80)
    print("Weather Platform Dashboard")
    print("=" * 80)
    print(f"Dashboard URL: http://{args.host}:{args.port}")
    if not args.no_scheduler:
        print(f"Pipeline runs every {args.interval} minutes")
    else:
        print("Scheduler disabled")
    print("Press Ctrl+C to stop")
    print("=" * 80)

    app.run(host=args.host, port=args.port, debug=True, use_reloader=False)


if __name__ == '__main__':
    main()
