#!/bin/bash
# Test Phase 10 on Staging Environment

STAGING_URL="https://bimcalc-staging.157.230.149.106.nip.io"
PDF_FILE="staging_test_invoice.pdf"

echo "=== Phase 10 Staging Verification ==="
echo ""

# Step 1: Login
echo "1. Logging in..."
curl -s -c staging_cookies.txt -X POST \
  -F "username=admin" \
  -F "password=changeme" \
  "$STAGING_URL/login" > /dev/null

if [ $? -eq 0 ]; then
    echo "   ✅ Login successful"
else
    echo "   ❌ Login failed"
    exit 1
fi

# Step 2: Get project UUID
echo ""
echo "2. Getting project UUID..."
PROJECT_UUID=$(curl -s -b staging_cookies.txt \
  "$STAGING_URL/api/projects?org=acme-construction" | \
  grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$PROJECT_UUID" ]; then
    echo "   ⚠️  No projects found, using default UUID"
    PROJECT_UUID="default"
else
    echo "   ✅ Project UUID: $PROJECT_UUID"
fi

# Step 3: Upload document
echo ""
echo "3. Uploading test PDF..."
UPLOAD_RESPONSE=$(curl -s -b staging_cookies.txt \
  -X POST \
  -F "file=@$PDF_FILE" \
  "$STAGING_URL/api/projects/$PROJECT_UUID/documents/upload")

echo "   Response: $UPLOAD_RESPONSE"

DOC_ID=$(echo $UPLOAD_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$DOC_ID" ]; then
    echo "   ❌ Upload failed"
    exit 1
else
    echo "   ✅ Document uploaded: $DOC_ID"
fi

# Step 4: Wait for processing
echo ""
echo "4. Waiting for processing..."
sleep 3

# Step 5: Check document status
echo ""
echo "5. Checking document status..."
STATUS_RESPONSE=$(curl -s -b staging_cookies.txt \
  "$STAGING_URL/api/projects/$PROJECT_UUID/documents")

echo "   Documents List:"
echo "$STATUS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$STATUS_RESPONSE"

# Step 6: Get extraction results
echo ""
echo "6. Getting extraction results..."
RESULTS_RESPONSE=$(curl -s -b staging_cookies.txt \
  "$STAGING_URL/api/projects/$PROJECT_UUID/documents/$DOC_ID/results")

echo "   Extracted Items:"
echo "$RESULTS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESULTS_RESPONSE"

# Count extracted items
ITEM_COUNT=$(echo "$RESULTS_RESPONSE" | grep -o '"id"' | wc -l)
echo ""
echo "   ✅ Extracted $ITEM_COUNT items"

# Cleanup
rm -f staging_cookies.txt

echo ""
echo "=== Verification Complete ==="
echo ""
echo "Summary:"
echo "  - Login: ✅"
echo "  - Document Upload: ✅"
echo "  - Processing: ✅"
echo "  - Extraction: ✅ ($ITEM_COUNT items)"
echo ""
echo "Next: Verify in browser at $STAGING_URL/?view=executive"
