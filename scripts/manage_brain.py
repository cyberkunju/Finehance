#!/usr/bin/env python
"""
🧠 UNIFIED FINANCIAL AI BRAIN - MAIN RUNNER

One-click script to:
1. Generate training data
2. Train the model with QLoRA
3. Run inference server

Usage:
  python run.py generate  - Generate training data
  python run.py train     - Train the model
  python run.py serve     - Start API server
  python run.py cli       - Interactive CLI
  python run.py all       - Generate + Train
"""

import os
import sys
import subprocess
from pathlib import Path

# Set base directory to ai_brain folder
# Since this script is in scripts/manage_brain.py, we need to go up one level and then into ai_brain
BASE_DIR = Path(__file__).parent.parent / "ai_brain"
if not BASE_DIR.exists():
    print(f"❌ Error: Could not find ai_brain directory at {BASE_DIR}")
    sys.exit(1)
    
os.chdir(BASE_DIR)


def run_command(cmd: str, description: str):
    """Run a command with nice output."""
    print("=" * 60)
    print(f"🚀 {description}")
    print("=" * 60)
    print(f"Command: {cmd}")
    print()
    
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode != 0:
        print(f"❌ Failed with exit code {result.returncode}")
        sys.exit(1)
    
    print(f"✅ {description} completed successfully!")
    print()


def generate_data():
    """Generate training data."""
    run_command(
        "python data/generate_training_data.py",
        "Generating Training Data"
    )


def train_model():
    """Train the model with QLoRA."""
    run_command(
        "python training/train_qlora.py",
        "Training Model with QLoRA"
    )


def serve():
    """Start the API server."""
    run_command(
        "python inference/brain_service.py --server --port 8080",
        "Starting API Server"
    )


def cli():
    """Start interactive CLI."""
    run_command(
        "python inference/brain_service.py --cli",
        "Starting Interactive CLI"
    )


def install_deps():
    """Install dependencies."""
    run_command(
        "pip install -q torch transformers datasets accelerate peft bitsandbytes trl",
        "Installing Core Dependencies"
    )
    
    # Try to install unsloth
    print("Installing Unsloth (for 2x faster training)...")
    subprocess.run(
        'pip install -q "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"',
        shell=True
    )


def check_gpu():
    """Check GPU availability."""
    import torch
    
    print("=" * 60)
    print("🔍 GPU Check")
    print("=" * 60)
    
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"✅ CUDA Available")
        print(f"   GPU: {gpu_name}")
        print(f"   VRAM: {gpu_memory:.1f} GB")
        
        if gpu_memory < 6:
            print("⚠️  Warning: Low VRAM. Training may be slow or fail.")
        elif gpu_memory < 8:
            print("ℹ️  Note: 6-8GB VRAM. Using memory-optimized settings.")
        else:
            print("✅ Sufficient VRAM for comfortable training.")
    else:
        print("❌ CUDA not available!")
        print("   Training will be very slow on CPU.")
    
    print()


def main():
    """Main entry point."""
    print()
    print("=" * 60)
    print("🧠 UNIFIED FINANCIAL AI BRAIN")
    print("=" * 60)
    print()
    
    if len(sys.argv) < 2:
        print("Usage: python run.py <command>")
        print()
        print("Commands:")
        print("  generate  - Generate training data")
        print("  train     - Train the model")
        print("  serve     - Start API server (port 8080)")
        print("  cli       - Interactive CLI")
        print("  all       - Generate data + Train model")
        print("  check     - Check GPU and dependencies")
        print("  install   - Install dependencies")
        print()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "generate":
        generate_data()
    
    elif command == "train":
        check_gpu()
        train_model()
    
    elif command == "serve":
        serve()
    
    elif command == "cli":
        cli()
    
    elif command == "all":
        check_gpu()
        generate_data()
        train_model()
    
    elif command == "check":
        check_gpu()
        print("Checking dependencies...")
        try:
            import torch
            import transformers
            import datasets
            import peft
            print("✅ Core dependencies installed")
        except ImportError as e:
            print(f"❌ Missing: {e}")
        
        try:
            import unsloth
            print("✅ Unsloth installed (2x faster training)")
        except ImportError:
            print("⚠️  Unsloth not installed (optional, but recommended)")
    
    elif command == "install":
        install_deps()
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
