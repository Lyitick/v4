"""
Diagnostic script for Finance Bot + Mini App.
Run:  python diagnose.py
Copy the FULL output and paste it to Claude.
"""
import os
import sys
import socket
import subprocess
import json
from pathlib import Path

SEPARATOR = "=" * 60


def section(title: str):
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def safe_read(path: Path, hide_secrets=True) -> str:
    if not path.exists():
        return f"[FILE NOT FOUND: {path}]"
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if hide_secrets and text:
        lines = []
        for line in text.splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("\"'")
                if any(s in key.upper() for s in ("TOKEN", "SECRET", "PASSWORD", "KEY")):
                    lines.append(f"{key}={'*' * min(len(val), 8) if val else '<EMPTY>'}")
                elif val:
                    lines.append(f"{key}={val}")
                else:
                    lines.append(f"{key}=<EMPTY>")
            else:
                lines.append(line)
        return "\n".join(lines)
    return text


def run_cmd(cmd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = (r.stdout + r.stderr).strip()
        return out if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "(timeout)"
    except Exception as e:
        return f"(error: {e})"


def check_port(host: str, port: int) -> str:
    try:
        s = socket.create_connection((host, port), timeout=3)
        s.close()
        return "OPEN (something is listening)"
    except ConnectionRefusedError:
        return "CLOSED (nothing listening)"
    except socket.timeout:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def check_http(url: str) -> str:
    try:
        import urllib.request
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read(500).decode("utf-8", errors="replace")
            return f"HTTP {resp.status} | body: {body[:200]}"
    except Exception as e:
        return f"FAILED: {e}"


def main():
    # Find project root (where this script is or parent dirs)
    script_dir = Path(__file__).resolve().parent
    # Try to find the project root
    project_root = None
    for candidate in [script_dir, script_dir.parent, script_dir / "v4"]:
        if (candidate / "finance_bot").exists():
            project_root = candidate
            break
    if not project_root:
        project_root = script_dir

    print("FINANCE BOT DIAGNOSTIC REPORT")
    print(f"Generated on: {__import__('datetime').datetime.now().isoformat()}")
    print(f"Script location: {script_dir}")
    print(f"Project root: {project_root}")

    # ── 1. System Info ──
    section("1. SYSTEM INFO")
    print(f"OS:             {sys.platform}")
    print(f"Python:         {sys.version}")
    print(f"CWD:            {os.getcwd()}")
    print(f"Project root:   {project_root}")

    # ── 2. Project Structure ──
    section("2. PROJECT STRUCTURE")
    key_paths = {
        "finance_bot/":              project_root / "finance_bot",
        "finance_bot/.env":          project_root / "finance_bot" / ".env",
        "finance_bot/Bot/":          project_root / "finance_bot" / "Bot",
        "finance_bot/Bot/main.py":   project_root / "finance_bot" / "Bot" / "main.py",
        "finance_bot/Bot/config/settings.py": project_root / "finance_bot" / "Bot" / "config" / "settings.py",
        "finance_bot/Bot/database/": project_root / "finance_bot" / "Bot" / "database",
        "webapp/":                   project_root / "webapp",
        "webapp/backend/":           project_root / "webapp" / "backend",
        "webapp/backend/main.py":    project_root / "webapp" / "backend" / "main.py",
        "webapp/frontend/":          project_root / "webapp" / "frontend",
        "webapp/frontend/dist/":     project_root / "webapp" / "frontend" / "dist",
        "webapp/frontend/dist/index.html": project_root / "webapp" / "frontend" / "dist" / "index.html",
        "webapp/frontend/package.json": project_root / "webapp" / "frontend" / "package.json",
    }
    for label, p in key_paths.items():
        status = "EXISTS" if p.exists() else "MISSING"
        extra = ""
        if p.exists() and p.is_dir():
            try:
                count = len(list(p.iterdir()))
                extra = f" ({count} items)"
            except:
                pass
        elif p.exists() and p.is_file():
            extra = f" ({p.stat().st_size} bytes)"
        print(f"  {'OK' if p.exists() else 'XX'}  {label:50s} {status}{extra}")

    # ── 3. .env Configuration ──
    section("3. .env CONFIGURATION")
    env_path = project_root / "finance_bot" / ".env"
    print(safe_read(env_path))

    # Also check for webapp .env
    webapp_env = project_root / "webapp" / ".env"
    if webapp_env.exists():
        print(f"\nwebapp/.env:")
        print(safe_read(webapp_env))

    frontend_env = project_root / "webapp" / "frontend" / ".env"
    if frontend_env.exists():
        print(f"\nwebapp/frontend/.env:")
        print(safe_read(frontend_env))
    else:
        print(f"\nwebapp/frontend/.env: NOT FOUND (VITE_API_URL not configured)")

    # ── 4. Python Packages ──
    section("4. PYTHON PACKAGES")
    packages = ["fastapi", "uvicorn", "aiogram", "pydantic", "aiohttp"]
    for pkg in packages:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "?")
            print(f"  OK  {pkg:20s} v{ver}")
        except ImportError:
            print(f"  XX  {pkg:20s} NOT INSTALLED")

    # ── 5. Frontend Build ──
    section("5. FRONTEND BUILD STATUS")
    dist_dir = project_root / "webapp" / "frontend" / "dist"
    if dist_dir.exists():
        index_html = dist_dir / "index.html"
        assets_dir = dist_dir / "assets"
        print(f"  dist/ exists: YES")
        print(f"  index.html:   {'YES' if index_html.exists() else 'MISSING'}")
        if assets_dir.exists():
            assets = list(assets_dir.iterdir())
            print(f"  assets/:      {len(assets)} files")
            for a in assets[:10]:
                print(f"    - {a.name} ({a.stat().st_size} bytes)")
        else:
            print(f"  assets/:      MISSING")
    else:
        print("  dist/ DOES NOT EXIST!")
        print("  >>> Frontend is NOT built. Run: cd webapp/frontend && npm run build")

    # Check if node_modules exists
    node_modules = project_root / "webapp" / "frontend" / "node_modules"
    print(f"  node_modules: {'EXISTS' if node_modules.exists() else 'NOT INSTALLED (run: npm install)'}")

    # ── 6. Port Check ──
    section("6. PORT STATUS")
    for port in [8080, 8000, 3000, 5173]:
        status = check_port("127.0.0.1", port)
        print(f"  :{port}  {status}")

    # ── 7. Backend Health ──
    section("7. BACKEND API CHECK")
    for port in [8080, 8000]:
        url = f"http://127.0.0.1:{port}/api/health"
        print(f"  GET {url}")
        print(f"    -> {check_http(url)}")

    # Also try root
    for port in [8080, 8000]:
        url = f"http://127.0.0.1:{port}/"
        print(f"  GET {url}")
        print(f"    -> {check_http(url)}")

    # ── 8. Backend Routes ──
    section("8. BACKEND APP ROUTES")
    try:
        sys.path.insert(0, str(project_root))
        os.chdir(str(project_root))
        # Try to import and list routes
        from webapp.backend.main import app as fastapi_app
        routes = []
        for route in fastapi_app.routes:
            path = getattr(route, "path", "?")
            methods = getattr(route, "methods", set())
            name = getattr(route, "name", "")
            routes.append(f"  {','.join(sorted(methods)) if methods else 'MOUNT':8s} {path:45s} {name}")
        for r in sorted(routes):
            print(r)
    except Exception as e:
        print(f"  Could not inspect routes: {e}")

    # ── 9. Database Check ──
    section("9. DATABASE")
    db_candidates = [
        project_root / "finance_bot" / "Bot" / "database" / "finance.db",
        project_root / "finance_bot" / "finance.db",
        project_root / "finance.db",
    ]
    found_db = False
    for db_path in db_candidates:
        if db_path.exists():
            print(f"  Found: {db_path} ({db_path.stat().st_size} bytes)")
            found_db = True
            # Try to open and check tables
            try:
                import sqlite3
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
                print(f"  Tables ({len(tables)}): {', '.join(tables)}")

                # Check wishes table for deleted_at column
                if "wishes" in tables:
                    cursor.execute("PRAGMA table_info(wishes)")
                    cols = [row[1] for row in cursor.fetchall()]
                    print(f"  wishes columns: {', '.join(cols)}")
                    has_deleted_at = "deleted_at" in cols
                    print(f"  deleted_at column: {'YES' if has_deleted_at else 'MISSING (needs migration)'}")

                conn.close()
            except Exception as e:
                print(f"  DB error: {e}")
    if not found_db:
        print("  No database file found (will be created on first run)")

    # ── 10. WEBAPP_URL Analysis ──
    section("10. WEBAPP_URL ANALYSIS")
    env_content = safe_read(env_path, hide_secrets=False)
    webapp_url = ""
    for line in env_content.splitlines():
        if line.startswith("WEBAPP_URL="):
            webapp_url = line.split("=", 1)[1].strip().strip("\"'")

    if not webapp_url:
        print("  WEBAPP_URL is EMPTY!")
        print("  >>> The Mini App menu button in Telegram won't work.")
        print("  >>> You need a public HTTPS URL pointing to your backend.")
        print("  >>> Options:")
        print("  >>>   1. Use ngrok: ngrok http 8080")
        print("  >>>   2. Deploy to a server with HTTPS")
        print("  >>>   3. Use Cloudflare Tunnel")
    else:
        print(f"  WEBAPP_URL = {webapp_url}")
        if webapp_url.startswith("http://"):
            print("  WARNING: URL uses HTTP, Telegram requires HTTPS!")
        if "localhost" in webapp_url or "127.0.0.1" in webapp_url:
            print("  WARNING: URL is localhost — Telegram can't reach it!")
        if webapp_url.startswith("https://"):
            print("  Checking URL accessibility...")
            result = check_http(webapp_url)
            print(f"    -> {result}")

    # ── 11. Git Status ──
    section("11. GIT STATUS")
    print(run_cmd("git status --short"))
    print(f"\nBranch: {run_cmd('git branch --show-current')}")
    print(f"Last commit: {run_cmd('git log --oneline -1')}")

    # ── Summary ──
    section("SUMMARY / CHECKLIST")
    issues = []

    if not (project_root / "webapp" / "frontend" / "dist" / "index.html").exists():
        issues.append("Frontend NOT built — run: cd webapp/frontend && npm install && npm run build")

    if not webapp_url:
        issues.append("WEBAPP_URL is empty — Mini App won't open from Telegram")
    elif "localhost" in webapp_url or "127.0.0.1" in webapp_url:
        issues.append("WEBAPP_URL points to localhost — Telegram can't reach it")
    elif webapp_url.startswith("http://"):
        issues.append("WEBAPP_URL uses HTTP — Telegram requires HTTPS")

    env_path_check = project_root / "finance_bot" / ".env"
    if env_path_check.exists():
        content = env_path_check.read_text()
        if "BOT_TOKEN=" in content:
            # check if it has a value
            for line in content.splitlines():
                if line.startswith("BOT_TOKEN="):
                    val = line.split("=", 1)[1].strip()
                    if not val:
                        issues.append("BOT_TOKEN is empty in .env")

    if not (project_root / "webapp" / "frontend" / "node_modules").exists():
        issues.append("node_modules missing — run: cd webapp/frontend && npm install")

    if issues:
        print("ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("No obvious issues found.")

    print(f"\n{SEPARATOR}")
    print("END OF DIAGNOSTIC REPORT")
    print(f"{SEPARATOR}")
    print("\nCopy EVERYTHING above and paste to Claude for analysis.")


if __name__ == "__main__":
    main()
