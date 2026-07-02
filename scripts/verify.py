import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANAGE = ROOT / "manage.py"

QUICK_TEST_LABELS = [
    "app.tests.MediaThumbnailTests",
    "app.tests.PwaTests",
    "app.tests.CaddyPerformanceConfigTests",
    "app.tests.RateLimitTests",
    "app.tests.ChatEnhancementTests",
    "app.tests.FileShareTests",
]


def run_step(label, command, env):
    print(f"\n==> {label}")
    print(" ".join(str(part) for part in command))
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def default_env():
    env = os.environ.copy()
    env.setdefault("USE_SQLITE", "True")
    env.setdefault("USE_LOCAL_CACHE", "True")
    env.setdefault("DEBUG", "True")
    env.setdefault("SECRET_KEY", "local-verify-secret")
    env.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1")
    env.setdefault("CSRF_TRUSTED_ORIGINS", "")
    env.setdefault("OPENWEATHER_API_KEY", "dummy-for-tests")
    return env


def js_files():
    js_root = ROOT / "app" / "static" / "app" / "js"
    return sorted(js_root.glob("*.js"))


def main():
    parser = argparse.ArgumentParser(description="Run the standard MyTools quality checks.")
    parser.add_argument(
        "--test-label",
        action="append",
        default=[],
        help="Optional Django test label. Can be passed multiple times. Defaults to the full test suite.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run the focused security/media/PWA test set instead of the full Django test suite.",
    )
    parser.add_argument("--skip-js", action="store_true", help="Skip JavaScript syntax checks.")
    parser.add_argument("--skip-static", action="store_true", help="Skip collectstatic dry-run.")
    args = parser.parse_args()

    if args.quick and args.test_label:
        parser.error("--quick cannot be combined with --test-label.")

    env = default_env()
    python = sys.executable

    run_step("Django system check", [python, MANAGE, "check"], env)
    run_step("Migration drift check", [python, MANAGE, "makemigrations", "--check", "--dry-run"], env)

    test_labels = QUICK_TEST_LABELS if args.quick else args.test_label
    test_command = [python, MANAGE, "test", *(test_labels or [])]
    run_step("Django tests", test_command, env)

    if not args.skip_static:
        run_step("Staticfiles dry-run", [python, MANAGE, "collectstatic", "--noinput", "--dry-run", "--verbosity", "0"], env)

    node = shutil.which("node")
    if args.skip_js:
        print("\n==> JavaScript syntax checks skipped")
    elif node:
        for path in js_files():
            run_step(f"JavaScript syntax: {path.relative_to(ROOT)}", [node, "--check", path], env)
    else:
        print("\n==> JavaScript syntax checks skipped because node was not found")

    print("\nAll quality checks passed.")


if __name__ == "__main__":
    main()
