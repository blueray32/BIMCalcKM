import sys
import structlog

# Configure structlog to be silent during verification
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(file=open("/dev/null", "w")),
)

print("Verifying app import...")
try:
    from bimcalc.web.app_enhanced import app

    print("SUCCESS: App imported successfully.")
    # Print registered routes to verify inclusions
    print(f"Registered routes: {len(app.routes)}")
    sys.exit(0)
except Exception as e:
    print(f"FAILURE: App import failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
