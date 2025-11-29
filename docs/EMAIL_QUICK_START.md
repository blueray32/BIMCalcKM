# AWS SES Quick Start for BIMCalc

## ✅ What's Already Done

- ✅ SMTP environment variables configured in docker-compose
- ✅ Email service code deployed and ready
- ✅ Worker configured to process email jobs
- ✅ `.env.production.example` template created
- ✅ Full setup guide available at `AWS_SES_SETUP.md`

## 🚀 Quick Setup (5-10 minutes)

### Step 1: Get AWS SES Credentials

1. **Log into AWS Console** → Navigate to **SES (Simple Email Service)**
2. **Verify your email**:
   - Go to "Verified identities"
   - Click "Create identity" → Email address
   - Enter your email → Click verification link in inbox
3. **Create SMTP credentials**:
   - Go to "SMTP settings"
   - Click "Create SMTP credentials"
   - **Download the credentials** (you can't retrieve them later!)
   - Note your region's SMTP endpoint (e.g., `email-smtp.us-east-1.amazonaws.com`)

### Step 2: Configure on Server

SSH into your server:
```bash
ssh root@157.230.149.106
cd /opt/bimcalc
```

Copy and edit the env file:
```bash
cp .env.production.example .env.production
nano .env.production
```

Update these 5 lines:
```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com  # Your AWS region
SMTP_USERNAME=AKIA1234567890EXAMPLE           # From AWS SMTP credentials
SMTP_PASSWORD=A1b2C3...long_password_here      # From AWS SMTP credentials  
FROM_EMAIL=your.verified@email.com            # Must be verified in SES
FROM_NAME=BIMCalc Reports
```

Save (`Ctrl+X`, `Y`, `Enter`)

### Step 3: Restart Services

```bash
# Recreate containers with new env vars
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker

# Verify services started
docker ps | grep bimcalc
```

### Step 4: Test (Optional)

```bash
# Quick test email
docker exec bimcalc-worker python -c "
import asyncio, os
from bimcalc.notifications.email import EmailService

async def test():
    svc = EmailService(
        smtp_host=os.get env('SMTP_HOST'),
        smtp_port=int(os.getenv('SMTP_PORT', 587)),
        username=os.getenv('SMTP_USERNAME'),
        password=os.getenv('SMTP_PASSWORD'),
        from_email=os.getenv('FROM_EMAIL')
    )
    # Test simple email
    print('Sending test email...')
    await svc.send_weekly_report(
        project={'project_id': 'test', 'display_name': 'Test Project'},
        cost_summary={'total_cost': 50000, 'items_priced': 10},
        recipient_emails=['YOUR.EMAIL@example.com']  # Change this!
    )
    print('✅ Email sent!')

asyncio.run(test())
"
```

## 📊 Using Email Reports

Once configured:

1. **Navigate to BIMCalc** → Reports page
2. **Create a report template** with your preferred format
3. **Schedule automated emails**:
   - Weekly project summaries
   - Cost alerts
   - Analytics reports
4. **Reports sent automatically** via ARQ worker!

## 🔧 Troubleshooting

**"Email address not verified"**
→ Go to AWS SES Console → Verified identities → Verify your FROM_EMAIL

**"Invalid credentials"**
→ Double-check SMTP_USERNAME and SMTP_PASSWORD in .env.production

**Emails go to spam**
→ Set up SPF/DKIM records for your domain (see full guide)

**"Sandbox mode" errors**
→ Request production access in AWS SES Console (takes 24-48 hours)

## 📚 Full Documentation

- Detailed setup: `/opt/bimcalc/AWS_SES_SETUP.md`
- Environment template: `/opt/bimcalc/.env.production.example`
- AWS SES Docs: https://docs.aws.amazon.com/ses/

## 💰 Cost

- **Free**: First 62,000 emails/month (when sent from EC2)
- **Paid**: $0.10 per 1,000 additional emails

---

## 🎯 Summary

**You need:**
1. AWS SES SMTP credentials (5 min to create)
2. Verified email address (instant if you have access to inbox)
3. Update `.env.production` on server (2 min)
4. Restart Docker containers (1 min)

**Then you get:**
- ✅ Automated weekly project reports
- ✅ Cost alert emails  
- ✅ Custom report distribution
- ✅ Professional email delivery via AWS

Ready to set it up? Follow Step 1 above! 🚀
