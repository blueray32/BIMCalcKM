import sys
import os
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass, field

# Mock the DashboardMetrics dataclass structure
@dataclass
class MockMetrics:
    avg_confidence: float = 85.0
    high_confidence_percentage: float = 90.0
    avg_risk_score: float = 12.5
    risk_distribution: dict = field(default_factory=lambda: {"High": 5, "Medium": 10, "Low": 85})
    classification_distribution: list = field(default_factory=list)
    total_cost_net: float = 1000.0
    total_cost_gross: float = 1200.0
    high_risk_cost: float = 100.0
    currency: str = "EUR"
    total_labor_hours: float = 50.0
    total_labor_cost: float = 2500.0
    total_installed_cost: float = 3500.0
    blended_labor_rate: float = 50.0
    total_items: int = 100
    matched_items: int = 80
    auto_approved_count: int = 60
    pending_review: int = 10
    high_urgency_count: int = 2
    advisory_count: int = 5
    high_confidence_count: int = 90
    health_score: float = 95.0
    health_status: str = "Healthy"
    total_pending_review: int = 10
    match_percentage: float = 80.0
    auto_approval_rate: float = 60.0
    recent_matches: int = 150
    recent_approvals: int = 120
    recent_ingestions: int = 200

    def __post_init__(self):
        # Ensure we are in the project root
        if not os.path.exists("bimcalc/web/templates"):
            print("Error: Run this script from the project root.")
            sys.exit(1)

def test_render():
    env = Environment(loader=FileSystemLoader("bimcalc/web/templates"))
    
    # Add 'format' filter if it's used in the template (it is: "%.0f"|format(...))
    # Jinja2 has a built-in 'format' filter, but sometimes it's used as a method on strings.
    # The template uses "%.0f"|format(val), which is standard Jinja2.
    
    try:
        template = env.get_template("dashboard_executive.html")
        metrics = MockMetrics()

        # Mock request object
        class MockRequest:
            def url_for(self, endpoint, **values):
                return f"/{endpoint}"
            
            @property
            def path(self):
                return "/dashboard"

            @property
            def url(self):
                return "http://localhost/dashboard"

        output = template.render(metrics=metrics, request=MockRequest())
        print("✅ Successfully rendered dashboard_executive.html")
        
        # Verify the specific fix
        expected_snippet = 'style="--risk-high: 5; flex: var(--risk-high); background: #f56565;"'
        if expected_snippet in output:
             print("✅ Verified: CSS variables are correctly rendered in the output.")
        else:
             print("⚠️ Warning: Expected CSS variable pattern not found in output.")
             # Print the relevant section for debugging
             start_idx = output.find("Risk Profile")
             if start_idx != -1:
                 print("Context snippet:")
                 print(output[start_idx:start_idx+1000])
             
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_render()
