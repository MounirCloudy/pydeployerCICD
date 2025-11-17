#!/usr/bin/env python3
"""
PyDeployer — Python-only CI/CD automation tool.

Features:
 - Clone into cloned_projects/<target>
 - Build (increment version + commit)
 - Test
 - Deploy
 - Rollback safely
 - Minimal YAML configuration
 - Full logging + colored output

Author: MESSADI Mounir (Université Paris-Saclay)
"""

import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import yaml
from colorama import Fore, Style, init

# === Initialize colored output ===
init(autoreset=True)

# === Paths ===
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

CLONED_DIR = BASE_DIR / "cloned_projects"
CLONED_DIR.mkdir(exist_ok=True)

# === Logging setup ===
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = LOG_DIR / f"pydeployer_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("PyDeployer")

# === Colored console helpers ===
def info(msg): print(Fore.CYAN + msg + Style.RESET_ALL)
def success(msg): print(Fore.GREEN + msg + Style.RESET_ALL)
def warn(msg): print(Fore.YELLOW + msg + Style.RESET_ALL)
def error(msg): print(Fore.RED + msg + Style.RESET_ALL)

# === Run system command ===
def run_cmd(cmd, cwd=None):
    """Run a system command with logging and error handling."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=True
        )
        if result.stdout:
            logger.info(result.stdout.strip())
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(e.stderr)
        error(f" Command failed: {' '.join(cmd)}")
        sys.exit(1)

# === Load minimal config ===
def load_config():
    cfg_path = BASE_DIR / "pipeline.yml"
    if not cfg_path.exists():
        error(" pipeline.yml not found!")
        sys.exit(1)
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f) or {}

# === Clean old logs ===
def clean_old_logs():
    logs = sorted(LOG_DIR.glob("pydeployer_*.log"),
                  key=lambda p: p.stat().st_mtime,
                  reverse=True)
    for old in logs[10:]:
        old.unlink(missing_ok=True)

# === CI/CD STAGES ===

def stage_clone(config):
    """Clone or update the repository."""
    info("=== CLONE ===")

    repo_url = config["repo"]["url"]
    target_name = config["repo"]["target"]
    target_dir = CLONED_DIR / target_name

    if target_dir.exists():
        info(f" Repository already exists → pulling latest changes...")
        run_cmd(["git", "pull"], cwd=target_dir)
    else:
        info(f"📥 Cloning {repo_url} into {target_dir} ...")
        run_cmd(["git", "clone", repo_url, str(target_dir)])

    success("Clone completed.")

def stage_build(config):
    """Increment version + commit changes."""
    info("=== BUILD ===")

    target_dir = CLONED_DIR / config["repo"]["target"]
    version_file = target_dir / "VERSION"

    # Create or increment version
    if version_file.exists():
        version = int(version_file.read_text().strip()) + 1
    else:
        version = 1

    version_file.write_text(str(version))

    # Git commit
    run_cmd(["git", "add", "."], cwd=target_dir)
    try:
        run_cmd(["git", "commit", "-m", f"Build version {version}"], cwd=target_dir)
    except SystemExit:
        warn(" No changes to commit (repository clean).")

    success(f" Build completed. Version = {version}")

def stage_test(config):
    """Run test command."""
    info("=== TEST ===")

    target_dir = CLONED_DIR / config["repo"]["target"]
    test_command = config["test"]["command"]

    info(f"Running tests: {test_command}")
    run_cmd(test_command.split(), cwd=target_dir)

    success(" All tests passed.")
    
def stage_deploy(config):
    """Push changes to GitHub."""
    info("=== DEPLOY ===")

    target_dir = CLONED_DIR / config["repo"]["target"]
    branch = config["deploy"]["branch"]

    run_cmd(["git", "pull", "origin", branch, "--rebase"], cwd=target_dir)
    run_cmd(["git", "push", "origin", branch], cwd=target_dir)

    success(f"Deploy completed on branch '{branch}'.")

def stage_rollback(config):
    """Undo last commit safely using revert."""
    info("=== ROLLBACK ===")

    target_dir = CLONED_DIR / config["repo"]["target"]

    run_cmd(["git", "revert", "--no-edit", "HEAD"], cwd=target_dir)
    run_cmd(["git", "push", "origin", "HEAD"], cwd=target_dir)

    success(" Rollback completed.")

# === MAIN CLI ===
if __name__ == "__main__":
    import argparse

    clean_old_logs()

    parser = argparse.ArgumentParser(description="PyDeployer - Python CI/CD Tool")
    parser.add_argument("stage", choices=["clone", "build", "test", "deploy", "rollback"])
    args = parser.parse_args()

    config = load_config()

    stages = {
        "clone": stage_clone,
        "build": stage_build,
        "test": stage_test,
        "deploy": stage_deploy,
        "rollback": stage_rollback,
    }

    stages[args.stage](config)
