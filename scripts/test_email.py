import asyncio
import os
import sys
import logging

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.intelligence.notifications import get_email_notifier

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_email():
    print("📧 Testing Email Notification...")
    
    notifier = get_email_notifier()
    
    # Mock data
    item_data = {
        "id": "test-item-id",
        "family": "Test Family",
        "type_name": "Test Type",
        "project_id": "TEST-PROJ"
    }
    
    changes = [
        {"field": "width_mm", "old": "100", "new": "150"},
        {"field": "material", "old": "Steel", "new": "Concrete"}
    ]
    
    recipients = ["test@example.com"]
    
    print("   Sending revision alert...")
    try:
        await notifier.send_revision_alert(recipients, item_data, changes)
        print("   ✅ Email send initiated (check logs for success/warning)")
    except Exception as e:
        print(f"   ❌ Email send failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_email())
