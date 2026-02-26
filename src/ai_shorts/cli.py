"""
CLI Entry Point — command-line interface for the AI Shorts pipeline.

Provides a user-friendly CLI with Rich console output.

Usage:
    ai-shorts run              # Full pipeline
    ai-shorts run --mode test  # Test pipeline (story → voice → avatar only)
    ai-shorts run --video-mode slideshow  # Slideshow mode (no avatar)
    ai-shorts setup            # Validate configuration
    ai-shorts serve            # Start FastAPI server
    ai-shorts batch            # Process topics from JSON file
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv).

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    parser = argparse.ArgumentParser(
        prog="ai-shorts",
        description="🤖 AI YouTube Shorts — Automated Video Generation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ai-shorts run              Run the full pipeline
  ai-shorts run --mode test  Run simplified test pipeline
  ai-shorts setup            Validate your configuration
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run the video generation pipeline")
    run_parser.add_argument(
        "--mode",
        choices=["full", "test"],
        default="full",
        help="Pipeline mode: 'full' (all steps) or 'test' (story → voice → avatar only)",
    )
    run_parser.add_argument(
        "--video-mode",
        choices=["avatar", "slideshow"],
        default="avatar",
        help="Video style: 'avatar' (talking head) or 'slideshow' (image-based)",
    )
    run_parser.add_argument(
        "--schedule",
        default="",
        help="Schedule publish time (ISO 8601, e.g. '2026-02-26T21:00:00+05:30')",
    )
    run_parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment file (default: .env)",
    )

    # Setup command
    subparsers.add_parser("setup", help="Validate configuration and dependencies")

    # Serve command (FastAPI)
    serve_parser = subparsers.add_parser("serve", help="Start the FastAPI REST API")
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)",
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Server host (default: 0.0.0.0)",
    )

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Process topics from a JSON file")
    batch_parser.add_argument(
        "--input",
        required=True,
        help="Path to JSON file with topics",
    )
    batch_parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment file",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "setup":
        return _cmd_setup()
    elif args.command == "run":
        return _cmd_run(mode=args.mode, env_file=args.env_file)
    elif args.command == "serve":
        return _cmd_serve(host=args.host, port=args.port)
    elif args.command == "batch":
        return _cmd_batch(input_file=args.input, env_file=args.env_file)

    return 0


def _cmd_setup() -> int:
    """Validate configuration and print status."""
    from ai_shorts.core.config import Settings
    from ai_shorts.core.gpu import get_gpu_info
    from ai_shorts.core.logging import setup_logging

    setup_logging()

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
    except ImportError:
        console = None  # type: ignore[assignment]

    try:
        settings = Settings()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return 1

    if console:
        table = Table(title="🔧 Configuration Status")
        table.add_column("Setting", style="cyan")
        table.add_column("Status", style="green")

        table.add_row("Google Sheet URL", "✅" if settings.google.sheet_url else "❌ Not set")
        table.add_row(
            "Service Account", "✅" if settings.google.service_account_file else "❌ Not set"
        )
        table.add_row("YouTube OAuth", "✅" if settings.youtube.refresh_token else "❌ Not set")
        table.add_row("Telegram Bot", "✅" if settings.telegram.is_configured else "⚠️  Not set")
        table.add_row("Avatar Image", "✅" if settings.avatar_image_path else "❌ Not set")
        table.add_row("Ollama Host", settings.ollama.host)
        table.add_row("Ollama Model", settings.ollama.model)

        console.print(table)
    else:
        print("Google Sheet URL:", "✅" if settings.google.sheet_url else "❌")
        print("Ollama:", settings.ollama.host)

    gpu = get_gpu_info()
    if gpu:
        print(f"\n🖥️  GPU: {gpu.name} ({gpu.total_gb}GB)")
    else:
        print("\n⚠️  No GPU detected")

    print("\n✅ Configuration validated!")
    return 0


def _cmd_serve(host: str, port: int) -> int:
    """Start the FastAPI REST API server."""
    try:
        import uvicorn

        from ai_shorts.presentation.api import create_app

        app = create_app()
        print(f"🚀 Starting AI Shorts API on http://{host}:{port}")
        print(f"   📖 Docs: http://{host}:{port}/docs")
        uvicorn.run(app, host=host, port=port)
        return 0
    except ImportError:
        print("❌ FastAPI/uvicorn not installed. Run: pip install fastapi uvicorn")
        return 1
    except Exception as e:
        print(f"❌ Server error: {e}")
        return 1


def _cmd_batch(input_file: str, env_file: str) -> int:
    """Process multiple topics from a JSON file."""
    import json
    from pathlib import Path

    from ai_shorts.application.pipeline import PipelineOrchestrator
    from ai_shorts.core.config import Settings
    from ai_shorts.core.container import Container
    from ai_shorts.core.logging import setup_logging

    setup_logging()

    input_path = Path(input_file)
    if not input_path.exists():
        print(f"❌ File not found: {input_file}")
        return 1

    try:
        with open(input_path, encoding="utf-8") as f:
            topics = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return 1

    settings = Settings(_env_file=env_file)
    container = Container(settings)
    orchestrator = PipelineOrchestrator(container)

    total = len(topics)
    success = 0

    for i, item in enumerate(topics, 1):
        topic = item.get("topic", item.get("kural", ""))
        print(f"\n[{i}/{total}] Processing: {topic[:50]}...")

        try:
            result = orchestrator.run(mode="full")
            if result and result.success:
                success += 1
                print("   ✅ Done!")
            else:
                print(f"   ❌ Failed: {result.error if result else 'No result'}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    print(f"\n📊 Batch complete: {success}/{total} succeeded")
    return 0 if success == total else 1


def _cmd_run(mode: str, env_file: str) -> int:
    """Run the pipeline."""
    from ai_shorts.application.pipeline import PipelineOrchestrator
    from ai_shorts.core.config import Settings
    from ai_shorts.core.container import Container
    from ai_shorts.core.logging import setup_logging

    setup_logging()

    try:
        settings = Settings(_env_file=env_file)
        container = Container(settings)
        orchestrator = PipelineOrchestrator(container)
        result = orchestrator.run(mode=mode)

        if result is None:
            print("ℹ️  No pending topics. Add topics to your Google Sheet.")
            return 0

        if result.success:
            print("\n✅ Pipeline completed successfully!")
            print(f"   ⏱️  Total time: {result.total_duration_seconds:.1f}s")
            for output in result.outputs:
                print(f"   🎬 Video: {output.local_path}")
                if output.youtube_url:
                    print(f"   📺 YouTube: {output.youtube_url}")
            return 0
        else:
            print(f"\n❌ Pipeline failed: {result.error}")
            return 1

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
