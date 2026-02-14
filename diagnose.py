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

    # ── 8. Webapp Code Validation ──
    section("8. WEBAPP CODE VALIDATION")
    import traceback as _tb

    # Ensure sys.path is configured like uvicorn would see it
    for p in (str(project_root), str(project_root / "finance_bot")):
        if p not in sys.path:
            sys.path.insert(0, p)
    saved_cwd = os.getcwd()
    os.chdir(str(project_root))

    modules_to_check = [
        ("Bot.config.settings",            "Bot settings (shared)"),
        ("Bot.database.get_db",            "Database singleton (shared)"),
        ("Bot.database.crud",              "Database CRUD (shared)"),
        ("webapp.backend.auth",            "Telegram auth validation"),
        ("webapp.backend.dependencies",    "FastAPI dependencies"),
        ("webapp.backend.routers.export",  "Export router (/api/export)"),
        ("webapp.backend.routers.household", "Household router (/api/household)"),
        ("webapp.backend.routers.income",  "Income router (/api/income)"),
        ("webapp.backend.routers.recurring", "Recurring router (/api/recurring)"),
        ("webapp.backend.routers.reports", "Reports router (/api/reports)"),
        ("webapp.backend.routers.savings", "Savings router (/api/savings)"),
        ("webapp.backend.routers.settings", "Settings router (/api/settings)"),
        ("webapp.backend.routers.wishlist", "Wishlist router (/api/wishlist)"),
        ("webapp.backend.main",            "FastAPI app entry point"),
    ]

    import_failures = []
    for mod_name, description in modules_to_check:
        try:
            __import__(mod_name)
            print(f"  OK  {mod_name:42s} {description}")
        except Exception as e:
            import_failures.append(mod_name)
            print(f"  XX  {mod_name:42s} FAILED: {e}")
            _tb.print_exc()
            print()

    if import_failures:
        print(f"\n  MODULES FAILED TO IMPORT: {', '.join(import_failures)}")
        print("  >>> The backend will NOT start until these are fixed.")
    else:
        print("\n  All webapp modules import successfully.")

    # ── 9. Webapp Startup Simulation ──
    section("9. WEBAPP STARTUP SIMULATION")
    app_ok = False
    health_route_found = False
    spa_route_found = False
    try:
        from webapp.backend.main import app as fastapi_app
        routes_info = []
        for route in fastapi_app.routes:
            path = getattr(route, "path", "?")
            methods = getattr(route, "methods", set())
            name = getattr(route, "name", "")
            routes_info.append((path, methods, name))

        api_routes = [r for r in routes_info if r[0].startswith("/api")]
        print(f"  FastAPI app created:  OK")
        print(f"  Total routes:         {len(routes_info)}")
        print(f"  API routes:           {len(api_routes)}")

        for path, methods, name in sorted(routes_info):
            method_str = ",".join(sorted(methods)) if methods else "MOUNT"
            print(f"    {method_str:8s} {path:45s} {name}")

        health_route_found = any(r[0] == "/api/health" for r in routes_info)
        spa_route_found = any(r[0] == "/{path:path}" for r in routes_info)
        print(f"\n  /api/health endpoint: {'FOUND' if health_route_found else 'MISSING!'}")
        spa_status = "FOUND" if spa_route_found else "MISSING (frontend will not load)"
        print(f"  SPA fallback route:   {spa_status}")
        app_ok = True
    except Exception as e:
        print(f"  FAILED to create FastAPI app: {e}")
        _tb.print_exc()
        print("\n  >>> The backend cannot start. Fix the error above first.")

    # ── 10. Webapp Dependency Check ──
    section("10. WEBAPP DEPENDENCY CHECK")
    webapp_packages = [
        ("fastapi",   True,  "Core web framework"),
        ("uvicorn",   True,  "ASGI server to run backend"),
        ("pydantic",  True,  "Data validation for API"),
        ("starlette", True,  "Required by FastAPI"),
        ("openpyxl",  False, "Excel export (/api/export/excel)"),
    ]
    missing_required = []
    missing_optional = []
    for pkg, required, desc in webapp_packages:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "?")
            print(f"  OK  {pkg:20s} v{ver:15s} {desc}")
        except ImportError:
            label = "REQUIRED" if required else "optional"
            print(f"  XX  {pkg:20s} NOT INSTALLED ({label}) — {desc}")
            if required:
                missing_required.append(pkg)
            else:
                missing_optional.append(pkg)

    if missing_required:
        print(f"\n  MISSING REQUIRED: {', '.join(missing_required)}")
        print(f"  >>> Install: pip install {' '.join(missing_required)}")
    if missing_optional:
        print(f"\n  MISSING OPTIONAL: {', '.join(missing_optional)}")
        print(f"  >>> Install for full functionality: pip install {' '.join(missing_optional)}")
    if not missing_required and not missing_optional:
        print("\n  All webapp dependencies installed.")

    # ── 11. Database Check ──
    section("11. DATABASE")
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
            try:
                import sqlite3
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
                print(f"  Tables ({len(tables)}): {', '.join(tables)}")

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

    # ── 12. WEBAPP_URL & Tunnel Check ──
    section("12. WEBAPP_URL & TUNNEL CHECK")
    env_content = safe_read(env_path, hide_secrets=False)
    webapp_url = ""
    for line in env_content.splitlines():
        if line.startswith("WEBAPP_URL="):
            webapp_url = line.split("=", 1)[1].strip().strip("\"'")

    if not webapp_url:
        print("  WEBAPP_URL is EMPTY!")
        print("  >>> The Mini App menu button in Telegram won't work.")
        print("  >>> You need a public HTTPS URL pointing to your backend (port 8080).")
        print("  >>> Options:")
        print("  >>>   1. Cloudflare Tunnel: cloudflared tunnel --url http://localhost:8080")
        print("  >>>   2. ngrok:             ngrok http 8080")
        print("  >>>   3. Deploy to a server with HTTPS")
    else:
        print(f"  WEBAPP_URL = {webapp_url}")
        if webapp_url.startswith("http://"):
            print("  WARNING: URL uses HTTP, Telegram requires HTTPS!")
        if "localhost" in webapp_url or "127.0.0.1" in webapp_url:
            print("  WARNING: URL is localhost — Telegram can't reach it!")

        if webapp_url.startswith("https://"):
            # Check the tunnel/public URL
            print("\n  Checking public URL...")
            result = check_http(webapp_url)
            print(f"    GET {webapp_url}")
            print(f"    -> {result}")

            if "FAILED" in result:
                if "Connection refused" in result or "URLError" in result:
                    print("\n  DIAGNOSIS: Tunnel or backend is not responding.")
                    print("  >>> Possible causes:")
                    print("  >>>   1. Backend (uvicorn) is not running — start it first!")
                    print("  >>>   2. Cloudflare tunnel is not running or disconnected")
                    print("  >>>   3. Tunnel URL expired (Cloudflare quick tunnels change each restart)")
                elif "timeout" in result.lower():
                    print("\n  DIAGNOSIS: Connection timeout — tunnel may be unreachable.")
                elif "SSL" in result.lower() or "certificate" in result.lower():
                    print("\n  DIAGNOSIS: SSL/certificate issue with the tunnel URL.")
            else:
                # Tunnel responded — check /api/health specifically
                health_url = webapp_url.rstrip("/") + "/api/health"
                health_result = check_http(health_url)
                print(f"\n    GET {health_url}")
                print(f"    -> {health_result}")
                if '"status"' in health_result and '"ok"' in health_result:
                    print("    Backend is HEALTHY and reachable through the tunnel!")
                else:
                    print("    Backend may not be running correctly behind the tunnel.")

    # Check local backend regardless
    print("\n  Checking local backend...")
    for port in [8080, 8000]:
        local_result = check_http(f"http://127.0.0.1:{port}/api/health")
        status = "OK" if '"status"' in local_result and '"ok"' in local_result else "FAIL"
        print(f"    localhost:{port}/api/health -> {status} ({local_result[:80]})")

    # ── 13. Process Check ──
    section("13. PROCESS CHECK (is backend running?)")
    import platform
    backend_running = False

    if platform.system() == "Windows":
        for port in [8080, 8000]:
            result = run_cmd(f'netstat -ano | findstr ":{port} "')
            if "LISTENING" in result:
                backend_running = True
                print(f"  Port {port}: LISTENING")
                for line in result.splitlines():
                    if "LISTENING" in line:
                        parts = line.split()
                        pid = parts[-1] if parts else "?"
                        proc_info = run_cmd(f'tasklist /FI "PID eq {pid}" /FO CSV /NH')
                        print(f"    PID {pid}: {proc_info.strip()}")
            else:
                print(f"  Port {port}: NOT LISTENING")
    else:
        for port in [8080, 8000]:
            result = run_cmd(f'ss -tlnp 2>/dev/null | grep ":{port} "')
            if result and result != "(no output)":
                backend_running = True
                print(f"  Port {port}: {result}")
            else:
                result2 = run_cmd(f'netstat -tlnp 2>/dev/null | grep ":{port} "')
                if result2 and result2 != "(no output)":
                    backend_running = True
                    print(f"  Port {port}: {result2}")
                else:
                    print(f"  Port {port}: NOT LISTENING")

    if backend_running:
        print(f"\n  VERDICT: Backend appears to be RUNNING")
    else:
        print(f"\n  VERDICT: Backend is NOT RUNNING!")
        print(f"  >>> You must start the backend separately from the bot.")
        print(f"  >>> On Windows:   double-click start_webapp.bat")
        print(f"  >>>               or in PyCharm use 'Bot + WebApp' run config")
        print(f"  >>> On Linux/Mac: bash webapp/run_dev.sh")
        print(f"  >>> Manual:       python -m uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8080")

    # ── 14. Git Status ──
    section("14. GIT STATUS")
    print(run_cmd("git status --short"))
    print(f"\nBranch: {run_cmd('git branch --show-current')}")
    print(f"Last commit: {run_cmd('git log --oneline -1')}")

    os.chdir(saved_cwd)

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
            for line in content.splitlines():
                if line.startswith("BOT_TOKEN="):
                    val = line.split("=", 1)[1].strip()
                    if not val:
                        issues.append("BOT_TOKEN is empty in .env")

    if not (project_root / "webapp" / "frontend" / "node_modules").exists():
        issues.append("node_modules missing — run: cd webapp/frontend && npm install")

    if not backend_running:
        issues.append("Backend is NOT running — start with: start_webapp.bat (Windows) or bash webapp/run_dev.sh (Linux)")

    if import_failures:
        issues.append(f"Webapp modules failed to import: {', '.join(import_failures)} — backend won't start")

    if missing_required:
        issues.append(f"Missing required packages: {', '.join(missing_required)} — pip install {' '.join(missing_required)}")

    if missing_optional:
        issues.append(f"Missing optional packages: {', '.join(missing_optional)} — pip install {' '.join(missing_optional)}")

    if not app_ok:
        issues.append("FastAPI app could not be created — check section 8/9 for errors")
    else:
        if not health_route_found:
            issues.append("/api/health route is missing from the backend")
        if not spa_route_found:
            issues.append("SPA fallback route missing — frontend won't load from backend")

    if issues:
        print("ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("No obvious issues found. Everything looks good!")

    print(f"\n{SEPARATOR}")
    print("END OF DIAGNOSTIC REPORT")
    print(f"{SEPARATOR}")
    print("\nCopy EVERYTHING above and paste to Claude for analysis.")


if __name__ == "__main__":
    main()
