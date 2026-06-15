# ============================================================
# AV SHIELD — FABLE 5 AGENT PLATFORM
# do_agent.py — DigitalOcean Server Health & Self-Healing Agent
# Version: 1.0
# ============================================================

import os
import sys
import time
import json
import psutil
import logging
import subprocess
import threading
import requests
from datetime import datetime, timedelta
from config import (
    ESCALATION_PHONE, TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER,
    DO_API_TOKEN, AGENTS
)

logger = logging.getLogger("DOAgent")

# ------------------------------------------------------------
# THRESHOLDS
# ------------------------------------------------------------
CPU_ALERT_THRESHOLD    = 85      # % CPU usage
RAM_ALERT_THRESHOLD    = 85      # % RAM usage
DISK_ALERT_THRESHOLD   = 80      # % Disk usage
HEALTH_CHECK_INTERVAL  = 60      # seconds between checks
RESTART_MAX_ATTEMPTS   = 3       # max restarts before alerting Shad
ALERT_COOLDOWN         = 1800    # seconds between repeat alerts (30 min)

# ------------------------------------------------------------
# AGENT PROCESS REGISTRY
# ------------------------------------------------------------
AGENT_PROCESSES = {
    "orchestrator": {
        "cmd": ["python", "orchestrator.py"],
        "restarts": 0,
        "process": None,
        "last_restart": None,
        "status": "stopped"
    },
    "voice_agent": {
        "cmd": ["gunicorn", "voice_agent:app", "--bind", "0.0.0.0:5000", "--workers", "2"],
        "restarts": 0,
        "process": None,
        "last_restart": None,
        "status": "stopped"
    },
    "email_agent": {
        "cmd": ["python", "email_agent.py"],
        "restarts": 0,
        "process": None,
        "last_restart": None,
        "status": "stopped"
    },
}

# Alert cooldown tracker
last_alerts = {}

# ------------------------------------------------------------
# SMS ALERT TO SHAD
# ------------------------------------------------------------
def alert_shad(message: str, alert_key: str = "general") -> bool:
    """
    Send SMS alert to Shad via Twilio.
    Respects cooldown to avoid spam.
    """
    now = datetime.now()
    last = last_alerts.get(alert_key)

    if last and (now - last).seconds < ALERT_COOLDOWN:
        logger.info(f"[DO] Alert suppressed (cooldown): {alert_key}")
        return False

    if not ESCALATION_PHONE or "YOUR_" in TWILIO_ACCOUNT_SID:
        logger.warning(f"[DO] Alert not sent — Twilio not configured: {message}")
        return False

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"[AV SHIELD SERVER]\n{message}\n{now.strftime('%H:%M %b %d')}",
            from_=TWILIO_PHONE_NUMBER,
            to=ESCALATION_PHONE
        )
        last_alerts[alert_key] = now
        logger.info(f"[DO] Alert sent to Shad: {message}")
        return True
    except Exception as e:
        logger.error(f"[DO] Alert failed: {e}")
        return False

# ------------------------------------------------------------
# SERVER METRICS
# ------------------------------------------------------------
def get_server_metrics() -> dict:
    """
    Get current server health metrics.
    """
    try:
        cpu    = psutil.cpu_percent(interval=1)
        ram    = psutil.virtual_memory()
        disk   = psutil.disk_usage("/")
        net    = psutil.net_io_counters()
        uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())

        return {
            "timestamp":    datetime.now().isoformat(),
            "cpu_percent":  cpu,
            "ram_percent":  ram.percent,
            "ram_used_gb":  round(ram.used / (1024**3), 2),
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "net_sent_mb":  round(net.bytes_sent / (1024**2), 2),
            "net_recv_mb":  round(net.bytes_recv / (1024**2), 2),
            "uptime_hours": round(uptime.total_seconds() / 3600, 1),
            "status":       "healthy"
        }
    except Exception as e:
        logger.error(f"[DO] Metrics failed: {e}")
        return {"status": "error", "error": str(e)}

# ------------------------------------------------------------
# PROCESS MANAGEMENT
# ------------------------------------------------------------
def start_agent(agent_id: str) -> bool:
    """
    Start an agent process.
    """
    agent = AGENT_PROCESSES.get(agent_id)
    if not agent:
        logger.error(f"[DO] Unknown agent: {agent_id}")
        return False

    try:
        process = subprocess.Popen(
            agent["cmd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        agent["process"]      = process
        agent["status"]       = "running"
        agent["last_restart"] = datetime.now().isoformat()
        logger.info(f"[DO] Started: {agent_id} (PID: {process.pid})")
        return True

    except Exception as e:
        agent["status"] = "failed"
        logger.error(f"[DO] Start failed — {agent_id}: {e}")
        return False


def stop_agent(agent_id: str) -> bool:
    """
    Stop an agent process gracefully.
    """
    agent = AGENT_PROCESSES.get(agent_id)
    if not agent or not agent.get("process"):
        return False

    try:
        agent["process"].terminate()
        agent["process"].wait(timeout=10)
        agent["status"] = "stopped"
        logger.info(f"[DO] Stopped: {agent_id}")
        return True
    except Exception as e:
        agent["process"].kill()
        agent["status"] = "killed"
        logger.warning(f"[DO] Force killed: {agent_id} — {e}")
        return True


def restart_agent(agent_id: str) -> bool:
    """
    Restart a crashed agent.
    Tracks restart count — alerts Shad after max attempts.
    """
    agent = AGENT_PROCESSES.get(agent_id)
    if not agent:
        return False

    agent["restarts"] += 1

    if agent["restarts"] > RESTART_MAX_ATTEMPTS:
        alert_shad(
            f"⚠️ Agent {agent_id} crashed {agent['restarts']} times.\n"
            f"Auto-restart disabled. Manual intervention needed.",
            alert_key=f"crash_{agent_id}"
        )
        agent["status"] = "failed"
        logger.error(f"[DO] {agent_id} exceeded restart limit")
        return False

    logger.warning(f"[DO] Restarting {agent_id} (attempt {agent['restarts']})")
    stop_agent(agent_id)
    time.sleep(3)
    success = start_agent(agent_id)

    if success:
        alert_shad(
            f"🔄 {agent_id} restarted automatically.\n"
            f"Restart #{agent['restarts']} of {RESTART_MAX_ATTEMPTS}.",
            alert_key=f"restart_{agent_id}"
        )
    return success


def check_agent_health(agent_id: str) -> str:
    """
    Check if an agent process is still running.
    Returns: running | crashed | stopped
    """
    agent = AGENT_PROCESSES.get(agent_id)
    if not agent or not agent.get("process"):
        return "stopped"

    poll = agent["process"].poll()
    if poll is None:
        return "running"
    else:
        agent["status"] = "crashed"
        return "crashed"

# ------------------------------------------------------------
# SSL CERTIFICATE CHECK
# ------------------------------------------------------------
def check_ssl_cert(domain: str = "avsurveillance.com") -> dict:
    """
    Check SSL certificate expiry.
    Alert Shad if expiring within 14 days.
    """
    try:
        import ssl
        import socket

        ctx = ssl.create_default_context()
        with ctx.wrap_socket(
            socket.socket(), server_hostname=domain
        ) as s:
            s.settimeout(10)
            s.connect((domain, 443))
            cert = s.getpeercert()

        expiry = datetime.strptime(
            cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
        )
        days_left = (expiry - datetime.now()).days

        if days_left < 14:
            alert_shad(
                f"⚠️ SSL cert for {domain} expires in {days_left} days!\n"
                f"Renew immediately.",
                alert_key="ssl_expiry"
            )

        return {
            "domain":    domain,
            "days_left": days_left,
            "expiry":    expiry.isoformat(),
            "status":    "ok" if days_left >= 14 else "expiring"
        }

    except Exception as e:
        logger.error(f"[DO] SSL check failed: {e}")
        return {"domain": domain, "status": "error", "error": str(e)}

# ------------------------------------------------------------
# DIGITALOCEAN API — DROPLET MONITORING
# ------------------------------------------------------------
def get_droplet_info() -> dict:
    """
    Get droplet info from DigitalOcean API.
    """
    if not DO_API_TOKEN or "YOUR_" in DO_API_TOKEN:
        return {"status": "api_key_not_set"}

    try:
        response = requests.get(
            "https://api.digitalocean.com/v2/droplets",
            headers={"Authorization": f"Bearer {DO_API_TOKEN}"}
        )

        if response.status_code == 200:
            droplets = response.json().get("droplets", [])
            if droplets:
                d = droplets[0]
                return {
                    "name":    d.get("name"),
                    "status":  d.get("status"),
                    "region":  d.get("region", {}).get("name"),
                    "size":    d.get("size_slug"),
                    "ip":      d.get("networks", {}).get("v4", [{}])[0].get("ip_address"),
                    "created": d.get("created_at")
                }
        return {"status": "error", "code": response.status_code}

    except Exception as e:
        return {"status": "error", "error": str(e)}

# ------------------------------------------------------------
# GITHUB AUTO-DEPLOY
# ------------------------------------------------------------
def pull_latest_code() -> bool:
    """
    Pull latest code from GitHub.
    Called when orchestrator detects a new deployment.
    """
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        if result.returncode == 0:
            logger.info(f"[DO] Code updated: {result.stdout.strip()}")

            if "Already up to date" not in result.stdout:
                # New code — restart all agents
                logger.info("[DO] New code detected — restarting agents")
                for agent_id in AGENT_PROCESSES:
                    restart_agent(agent_id)
                alert_shad(
                    "🚀 New code deployed from GitHub.\n"
                    "All agents restarted.",
                    alert_key="deployment"
                )
            return True

        else:
            logger.error(f"[DO] Git pull failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"[DO] Deploy failed: {e}")
        return False

# ------------------------------------------------------------
# MAIN HEALTH MONITOR LOOP
# ------------------------------------------------------------
class DOAgent:
    def __init__(self):
        self.running       = True
        self.check_count   = 0
        self.alerts_sent   = 0
        self.start_time    = datetime.now()

    def run(self):
        """
        Main monitoring loop.
        Runs every 60 seconds.
        """
        logger.info("[DO] DigitalOcean Agent online — monitoring started")
        alert_shad(
            "✅ AV Shield platform starting up.\n"
            "All agents initializing.",
            alert_key="startup"
        )

        # Start all agent processes
        self._start_all_agents()

        while self.running:
            try:
                self.check_count += 1
                self._run_health_check()

                # Every 10 minutes — pull latest code
                if self.check_count % 10 == 0:
                    pull_latest_code()

                # Every hour — SSL check
                if self.check_count % 60 == 0:
                    check_ssl_cert()

                time.sleep(HEALTH_CHECK_INTERVAL)

            except KeyboardInterrupt:
                logger.info("[DO] Shutting down...")
                self._stop_all_agents()
                break
            except Exception as e:
                logger.error(f"[DO] Health check error: {e}")
                time.sleep(HEALTH_CHECK_INTERVAL)

    def _start_all_agents(self):
        """
        Start all agent processes on boot.
        """
        for agent_id in AGENT_PROCESSES:
            success = start_agent(agent_id)
            if success:
                logger.info(f"[DO] ✅ {agent_id} started")
            else:
                logger.error(f"[DO] ❌ {agent_id} failed to start")
        time.sleep(5)  # Give agents time to initialize

    def _stop_all_agents(self):
        """
        Gracefully stop all agents.
        """
        for agent_id in AGENT_PROCESSES:
            stop_agent(agent_id)

    def _run_health_check(self):
        """
        Full health check — server + agents.
        """
        # 1 — Server metrics
        metrics = get_server_metrics()

        # CPU alert
        if metrics.get("cpu_percent", 0) > CPU_ALERT_THRESHOLD:
            alert_shad(
                f"⚠️ HIGH CPU: {metrics['cpu_percent']}%\n"
                f"Server may be overloaded.",
                alert_key="cpu_high"
            )

        # RAM alert
        if metrics.get("ram_percent", 0) > RAM_ALERT_THRESHOLD:
            alert_shad(
                f"⚠️ HIGH RAM: {metrics['ram_percent']}%\n"
                f"Used: {metrics.get('ram_used_gb')}GB / "
                f"{metrics.get('ram_total_gb')}GB",
                alert_key="ram_high"
            )

        # Disk alert
        if metrics.get("disk_percent", 0) > DISK_ALERT_THRESHOLD:
            alert_shad(
                f"⚠️ DISK ALMOST FULL: {metrics['disk_percent']}%\n"
                f"Free: {metrics.get('disk_free_gb')}GB remaining.",
                alert_key="disk_high"
            )

        # 2 — Agent process health
        for agent_id in AGENT_PROCESSES:
            status = check_agent_health(agent_id)
            if status == "crashed":
                logger.warning(f"[DO] {agent_id} crashed — auto-restarting")
                restart_agent(agent_id)

        # Log health check
        logger.info(
            f"[DO] Health check #{self.check_count} — "
            f"CPU: {metrics.get('cpu_percent')}% | "
            f"RAM: {metrics.get('ram_percent')}% | "
            f"Disk: {metrics.get('disk_percent')}%"
        )

    def get_status_report(self) -> dict:
        """
        Full platform status report.
        """
        metrics  = get_server_metrics()
        droplet  = get_droplet_info()
        uptime   = (datetime.now() - self.start_time).total_seconds() / 3600

        agent_statuses = {
            agent_id: check_agent_health(agent_id)
            for agent_id in AGENT_PROCESSES
        }

        return {
            "timestamp":      datetime.now().isoformat(),
            "platform":       "AV Shield — Fable 5",
            "uptime_hours":   round(uptime, 1),
            "health_checks":  self.check_count,
            "alerts_sent":    self.alerts_sent,
            "server":         metrics,
            "droplet":        droplet,
            "agents":         agent_statuses,
            "overall_status": "healthy" if all(
                v == "running" for v in agent_statuses.values()
            ) else "degraded"
        }


# ------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        # python do_agent.py status
        agent = DOAgent()
        report = agent.get_status_report()
        print(json.dumps(report, indent=2))

    elif len(sys.argv) > 1 and sys.argv[1] == "metrics":
        # python do_agent.py metrics
        metrics = get_server_metrics()
        print(json.dumps(metrics, indent=2))

    else:
        # Full run — starts all agents + monitors
        agent = DOAgent()
        agent.run()
