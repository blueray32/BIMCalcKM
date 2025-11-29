# AWS SES Setup Guide for BIMCalc Email Distribution

This guide will help you configure AWS Simple Email Service (SES) for automated email reports in BIMCalc.

## Prerequisites

- AWS Account with billing enabled
- Access to AWS Console
- A verified email address or domain

## Step-by-Step Setup

### 1. Access AWS SES Console

1. Log into [AWS Console](https://console.aws.amazon.com/)
2. Navigate to **SES (Simple Email Service)**
3. Choose your preferred region (e.g., `us-east-1`, `eu-west-1`)
   - **Important**: Note this region, you'll need it later

### 2. Verify Your Sender Email/Domain

#### Option A: Verify an Email Address (Quick - for testing)

1. In SES Console, go to **Verified identities**
2. Click **Create identity**
3. Select **Email address**
4. Enter your email (e.g., `noreply@yourdomain.com`)
5. Click **Create identity**
6. Check your email inbox and click the verification link
7. Wait for status to show **Verified**

#### Option B: Verify a Domain (Recommended - for production)

1. In SES Console, go to **Verified identities**
2. Click **Create identity**
3. Select **Domain**
4. Enter your domain (e.g., `yourdomain.com`)
5. Enable **DKIM signing** (recommended)
6. Click **Create identity**
7. Add the DNS records shown to your domain's DNS settings
8. Wait for verification (can take up to 72 hours)

### 3. Request Production Access (If sending to external recipients)

By default, SES is in "Sandbox mode" - you can only send to verified addresses.

1. In SES Console, click **Account dashboard**
2. Under **Sending statistics**, click **Request production access**
3. Fill out the form:
   - **Mail type**: Transactional
   - **Website URL**: Your BIMCalc instance URL
   - **Use case description**: 
     ```
     Automated construction project reports and cost analytics for BIMCalc users.
     Weekly summary reports sent to project stakeholders with cost breakdowns and analytics.
     ```
4. Submit request
5. Wait for approval (usually 24-48 hours)

**Note**: While in sandbox mode, you can still test by sending to verified email addresses.

### 4. Create SMTP Credentials

1. In SES Console, go to **SMTP settings** (left sidebar)
2. Note the **SMTP endpoint** for your region:
   - `us-east-1`: `email-smtp.us-east-1.amazonaws.com`
   - `us-west-2`: `email-smtp.us-west-2.amazonaws.com`
   - `eu-west-1`: `email-smtp.eu-west-1.amazonaws.com`
   - [Full list](https://docs.aws.amazon.com/ses/latest/dg/smtp-connect.html)
3. Click **Create SMTP credentials**
4. Enter a username (e.g., `bimcalc-smtp-user`)
5. Click **Create user**
6. **IMPORTANT**: Download or copy the credentials:
   - **SMTP Username**: `AKIA...` (20 characters)
   - **SMTP Password**: (long string - save this securely!)
7. **You cannot retrieve the password later**, so save it now!

### 5. Configure BIMCalc Server

#### On your server (via SSH):

```bash
cd /opt/bimcalc

# Copy the example env file
cp .env.production.example .env.production

# Edit the file with your credentials
nano .env.production
```

#### Update these values:

```bash
# Replace with your region's SMTP endpoint
SMTP_HOST=email-smtp.us-east-1.amazonaws.com

# Always 587 for TLS
SMTP_PORT=587

# Paste your SMTP username from Step 4
SMTP_USERNAME=AKIA1234567890EXAMPLE

# Paste your SMTP password from Step 4
SMTP_PASSWORD=A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0

# Always true for AWS SES
SMTP_USE_TLS=true

# Your verified email from Step 2
FROM_EMAIL=noreply@yourdomain.com

# Display name for sender
FROM_NAME=BIMCalc Reports
```

Save and exit (`Ctrl+X`, then `Y`, then `Enter`)

### 6. Update Docker Compose

```bash
# Edit docker-compose.prod.yml
nano docker-compose.prod.yml
```

Add to the `app` service environment section:

```yaml
env_file: .env.production
```

Or add individual variables under `environment:`:

```yaml
environment:
  # ... existing variables ...
  SMTP_HOST: ${SMTP_HOST}
  SMTP_PORT: ${SMTP_PORT}
  SMTP_USERNAME: ${SMTP_USERNAME}
  SMTP_PASSWORD: ${SMTP_PASSWORD}
  SMTP_USE_TLS: ${SMTP_USE_TLS}
  FROM_EMAIL: ${FROM_EMAIL}
  FROM_NAME: ${FROM_NAME}
```

### 7. Restart Services

```bash
# Recreate containers with new environment
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker

# Check logs to verify
docker logs bimcalc-app --tail 20
docker logs bimcalc-worker --tail 20
```

### 8. Test Email Sending

```bash
# Test email functionality
docker exec bimcalc-app python -c "
import asyncio
from bimcalc.notifications.email import EmailService
import os

async def test_email():
    service = EmailService(
        smtp_host=os.getenv('SMTP_HOST'),
        smtp_port=int(os.getenv('SMTP_PORT', 587)),
        username=os.getenv('SMTP_USERNAME'),
        password=os.getenv('SMTP_PASSWORD'),
        from_email=os.getenv('FROM_EMAIL')
    )
    
    # Replace with your verified email
    await service.send_test_email('your.email@example.com')
    print('✅ Test email sent successfully!')

asyncio.run(test_email())
"
```

## Troubleshooting

### Error: "Email address not verified"
- **Solution**: Verify the FROM_EMAIL address in SES Console (Step 2)

### Error: "Message rejected: Email address is not verified"
- **Cause**: SES is in sandbox mode, recipient not verified
- **Solution**: Either verify recipient email OR request production access (Step 3)

### Error: "Invalid SMTP credentials"
- **Solution**: Double-check SMTP_USERNAME and SMTP_PASSWORD, recreate if needed

### Error: "Connection timeout"
- **Solution**: Check SMTP_HOST matches your AWS region

### Emails go to spam
- **Solution**: Set up SPF, DKIM, and DMARC DNS records for your domain
- **Guide**: [AWS SES Email Authentication](https://docs.aws.amazon.com/ses/latest/dg/email-authentication-methods.html)

## Cost Information

- **First 62,000 emails/month**: Free when sent from EC2
- **Additional emails**: $0.10 per 1,000 emails
- [Full pricing](https://aws.amazon.com/ses/pricing/)

## Security Best Practices

1. **Never commit `.env.production`** to version control
2. **Use IAM roles** instead of SMTP credentials when possible
3. **Rotate credentials** every 90 days
4. **Set up CloudWatch alarms** for bounce/complaint metrics
5. **Monitor sending quotas** in SES Console

## Next Steps

Once configured:
1. Navigate to BIMCalc Reports page
2. Create a new report template
3. Schedule automated weekly reports
4. Reports will be sent via email using AWS SES!

## Support

- [AWS SES Documentation](https://docs.aws.amazon.com/ses/)
- [AWS SES FAQ](https://aws.amazon.com/ses/faqs/)
- [AWS Support](https://console.aws.amazon.com/support/)
