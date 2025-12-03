#!/usr/bin/env python3
"""
PyDeployer VERSION NOYEAU MINIMAL —  outil CI/CD en Python.

But du script :
 - cloner un repo
 - build (augmenter version + commit)
 - lancer les tests
 - déployer (push)
 - rollback si besoin

Tout est fait en Python, pas besoin d’outils externes lourds.
"""

import logging #enregistrer les activite du pipeline pour des raisons de securite
import subprocess # excuter des commandes git et sys depuis python3
import sys # exit le programme en cas d'erreur , FAIL FAST  
from pathlib import Path
from datetime import datetime
import yaml # pour excuter la configuration pipeline yml
from colorama import Fore, Style, init

# >>> SNS ADDED
import boto3
from botocore.exceptions import BotoCoreError, ClientError
# <<< SNS ADDED

# Active les couleurs dans le terminal (pratique pour les messages)
init(autoreset=True)

# On définit les dossiers utilisés par l’outil
BASE_DIR = Path(__file__).parent     # dossier où vit ce script
LOG_DIR = BASE_DIR / "logs"          # on met les logs ici
LOG_DIR.mkdir(exist_ok=True)         # crée le dossier si pas là

CLONED_DIR = BASE_DIR / "cloned_projects"  # où mettre les repos clonés
CLONED_DIR.mkdir(exist_ok=True) #sinon on cree un nouveau repo

# Config de logging : format, fichier de log, affichage écran
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = LOG_DIR / f"pydeployer_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"), #display outputs dans les fichiers logs
        logging.StreamHandler(sys.stdout), #display outputs dans CLI
    ],
)
logger = logging.getLogger("PyDeployer")

# Petites fonctions juste pour afficher plus joliment
def info(msg): print(Fore.CYAN + msg + Style.RESET_ALL)
def success(msg): print(Fore.GREEN + msg + Style.RESET_ALL)
def warn(msg): print(Fore.YELLOW + msg + Style.RESET_ALL)
def error(msg): print(Fore.RED + msg + Style.RESET_ALL)

# >>> SNS ADDED
def send_sns_alert(message, config):
    """Send error message to SNS topic if configured."""
    if "aws" not in config:
        return  # SNS non configuré = on ignore

    topic_arn = config["aws"].get("sns_topic_arn")
    region = config["aws"].get("region", "eu-west-3")

    if not topic_arn:
        return

    try:
        sns = boto3.client("sns", region_name=region)
        sns.publish(
            TopicArn=topic_arn,
            Subject="🚨 PyDeployer Pipeline Error",
            Message=message
        )
        success("SNS alert sent ✔")
    except (BotoCoreError, ClientError) as e:
        error(f"SNS ERROR: {e}")
# <<< SNS ADDED


def run_cmd(cmd, cwd=None):
    """
    Exécute une commande (git, tests, etc.)
    - Si ça marche → log
    - Si ça plante → on affiche l’erreur et on stoppe tout
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,  # on récupère stdout et stderr
            check=True            # si exit code != 0 → exception
        )
        if result.stdout:
            logger.info(result.stdout.strip())
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        logger.error(e.stderr)  # pour garder une trace
        error(f" Command failed: {' '.join(cmd)}")

        # >>> SNS ADDED
        # Envoi automatique de l'erreur à SNS
        full_msg = f"Command failed: {' '.join(cmd)}\nError: {e.stderr}"
        send_sns_alert(full_msg, load_config())
        # <<< SNS ADDED

        sys.exit(1)


def load_config():
    """
    charge pipeline.yml (fichier obligatoire pour faire tourner l’outil).
    Si le fichier n'existe pas → on arrête tout.
    """
    cfg_path = BASE_DIR / "pipeline.yml"
    if not cfg_path.exists():
        error(" pipeline.yml not found!")
        sys.exit(1)
    with open(cfg_path, "r") as f:
        return yaml.safe_load(f) or {}

def clean_old_logs():
    """
    juste du ménage : on garde les 10 derniers logs.
    c’est suffisant et évite d’encombrer le dossier.
    """
    logs = sorted(LOG_DIR.glob("pydeployer_*.log"),
                  key=lambda p: p.stat().st_mtime,
                  reverse=True)
    for old in logs[10:]:
        old.unlink(missing_ok=True)

# -------------------------------
#       CI/CD STAGES
# -------------------------------

def stage_clone(config):
    """Clone un repo ou le met à jour s’il est déjà là."""
    info("=== CLONE ===")

    repo_url = config["repo"]["url"]
    target_name = config["repo"]["target"]
    target_dir = CLONED_DIR / target_name

    # Si le dossier existe déjà → juste un pull
    if target_dir.exists():
        info(" if repo already exists → pulling updates...")
        run_cmd(["git", "pull"], cwd=target_dir)
    else:
        info(f"cloning {repo_url} in {target_dir} ...")
        run_cmd(["git", "clone", repo_url, str(target_dir)])

    success("Clone completed.")

def stage_build(config):
    """Gère la version (augmentation simple) puis commit."""
    info("=== BUILD ===")

    target_dir = CLONED_DIR / config["repo"]["target"]
    version_file = target_dir / "VERSION"

    # si VERSION existe → on l'incrémente
    # sinon → première version : 1
    if version_file.exists():
        version = int(version_file.read_text().strip()) + 1
    else:
        version = 1

    version_file.write_text(str(version))

    # commit Git des changements
    run_cmd(["git", "add", "."], cwd=target_dir)
    try:
        run_cmd(["git", "commit", "-m", f"Build version {version}"], cwd=target_dir)
    except SystemExit:
        # souvent git dit "nothing to commit" si rien n’a changé.
        warn(" No changes to commit (clean repo).")

    success(f" Build done. Version = {version}")

def stage_test(config):
    """Exécute la commande de test fournie dans la config."""
    info("=== TEST ===")

    target_dir = CLONED_DIR / config["repo"]["target"]
    test_command = config["test"]["command"]

    info(f"Running tests: {test_command}")
    run_cmd(test_command.split(), cwd=target_dir)

    success(" All tests passed BRAVOOOO ")

def stage_deploy(config):
    """push sur la branche de déploiement."""
    info("=== DEPLOY ===")

    target_dir = CLONED_DIR / config["repo"]["target"]
    branch = config["deploy"]["branch"]

    # rebase avant de pousser comme des SAFE measures → évite les conflits bêtes
    run_cmd(["git", "pull", "origin", branch, "--rebase"], cwd=target_dir)
    run_cmd(["git", "push", "origin", branch], cwd=target_dir)

    success(f"Deployed on branch '{branch}'")

def stage_rollback(config):
    """
    revert du dernier commit.
    on utilise revert (et pas reset) pour un rollback "propre"
    qui laisse l’historique correct.
    """
    info("=== ROLLBACK ===")

    target_dir = CLONED_DIR / config["repo"]["target"]

    run_cmd(["git", "revert", "--no-edit", "HEAD"], cwd=target_dir)
    run_cmd(["git", "push", "origin", "HEAD"], cwd=target_dir)

    success(" Rollback finished.")

# -------------------------------
#      MAIN SCRIPT (CLI)
# -------------------------------
if __name__ == "__main__":
    import argparse

    clean_old_logs()  # petit ménage

    parser = argparse.ArgumentParser(description="PyDeployer - CI/CD Tool")
    parser.add_argument("stage", choices=["clone", "build", "test", "deploy", "rollback"])
    args = parser.parse_args()

    config = load_config()  # on lit pipeline.yml

    # table qui relie "clone", "build", etc. → aux vraies fonctions
    stages = {
        "clone": stage_clone,
        "build": stage_build,
        "test": stage_test,
        "deploy": stage_deploy,
        "rollback": stage_rollback,
    }

    # on lance l’étape demandée en CLI
    try:
        stages[args.stage](config)

    except Exception as e:
        # >>> SNS ADDED
        send_sns_alert(f"Unexpected error during stage '{args.stage}': {e}", config)
        # <<< SNS ADDED

        raise
