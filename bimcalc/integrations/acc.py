"""Autodesk Construction Cloud (ACC) Integration.

Handles OAuth2 flow and file listing/downloading from ACC/BIM360.
"""

import os
from typing import List, Dict, Any
from pydantic import BaseModel

class ACCFile(BaseModel):
    id: str
    name: str
    folder_id: str
    project_id: str
    version: int
    last_modified: str

class ACCClient:
    """Client for interacting with Autodesk Construction Cloud."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = "https://developer.api.autodesk.com"
        
    def get_auth_url(self) -> str:
        """Generate the OAuth2 authorization URL."""
        # Scopes: data:read for reading files
        return (
            f"{self.base_url}/authentication/v2/authorize"
            f"?response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&scope=data:read"
        )
        
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        # Mock implementation for now
        return {
            "access_token": "mock_access_token_" + code,
            "refresh_token": "mock_refresh_token",
            "expires_in": 3600
        }
        
    async def list_projects(self, token: str) -> List[Dict[str, Any]]:
        """List accessible projects."""
        # Mock data
        return [
            {"id": "b.12345", "name": "Sample Project A"},
            {"id": "b.67890", "name": "Hospital Construction B"},
        ]
        
    async def list_files(self, token: str, project_id: str, folder_id: str = None) -> List[ACCFile]:
        """List files in a project folder."""
        # Mock data
        return [
            ACCFile(
                id="urn:adsk.wipp:dm.lineage:123",
                name="Architectural_Schedule.rvt",
                folder_id="folder1",
                project_id=project_id,
                version=1,
                last_modified="2025-11-29T10:00:00Z"
            ),
            ACCFile(
                id="urn:adsk.wipp:dm.lineage:456",
                name="MEP_Quantities.csv",
                folder_id="folder1",
                project_id=project_id,
                version=2,
                last_modified="2025-11-28T15:30:00Z"
            ),
        ]

# Singleton instance
_acc_client = None

def get_acc_client() -> ACCClient:
    global _acc_client
    if not _acc_client:
        _acc_client = ACCClient(
            client_id=os.environ.get("ACC_CLIENT_ID", "mock_id"),
            client_secret=os.environ.get("ACC_CLIENT_SECRET", "mock_secret"),
            redirect_uri=os.environ.get("ACC_REDIRECT_URI", "http://localhost:8001/api/integrations/acc/callback")
        )
    return _acc_client
