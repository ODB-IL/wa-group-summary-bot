"""
Setup API endpoints for WhatsApp bot configuration.
This module provides web UI and API endpoints for managing groups.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from api.deps import get_db_async_session
from models.group import Group
from whatsapp.client import WhatsAppClient

router = APIRouter()


class GroupUpdate(BaseModel):
    """Model for group update request."""
    group_jid: str
    managed: bool


class GroupResponse(BaseModel):
    """Model for group response."""
    group_jid: str
    group_name: str
    managed: bool


@router.get("/setup", response_class=HTMLResponse)
async def setup_page():
    """
    Serve the setup wizard HTML page.
    This is the main entry point for clients to configure their bot.
    """
    import os
    from pathlib import Path
    
    # Read the HTML file
    html_path = Path(__file__).parent / "setup-wizard.html"
    
    if not html_path.exists():
        # Fallback: return inline HTML if file not found
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Setup Not Found</title></head>
        <body>
            <h1>Setup page not found</h1>
            <p>Please ensure setup-wizard.html is in the deployment directory.</p>
        </body>
        </html>
        """, status_code=500)
    
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)


@router.get("/whatsapp-qr", response_class=HTMLResponse)
async def whatsapp_qr_iframe():
    """
    Proxy endpoint for WhatsApp Web QR code.
    Returns an iframe-friendly page that embeds the WhatsApp Web interface.
    """
    from config import Settings
    
    settings = Settings()
    whatsapp_url = settings.whatsapp_host
    
    # Create a simple HTML page that embeds WhatsApp Web
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                overflow: hidden;
                background: #f9fafb;
            }}
            iframe {{
                width: 100%;
                height: 100vh;
                border: none;
            }}
            .loading {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                text-align: center;
                color: #6b7280;
            }}
        </style>
    </head>
    <body>
        <div class="loading">
            <p>Loading WhatsApp Web...</p>
        </div>
        <iframe src="{whatsapp_url}" onload="document.querySelector('.loading').style.display='none'"></iframe>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)


@router.get("/api/groups", response_model=List[GroupResponse])
async def list_groups(
    session: AsyncSession = Depends(get_db_async_session)
):
    """
    List all WhatsApp groups the bot is part of.
    Returns group JID, name, and managed status.
    """
    try:
        statement = select(Group).order_by(Group.group_name)
        result = await session.execute(statement)
        groups = result.scalars().all()
        
        return [
            GroupResponse(
                group_jid=group.group_jid,
                group_name=group.group_name,
                managed=group.managed
            )
            for group in groups
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch groups: {str(e)}")


@router.post("/api/groups/update")
async def update_groups(
    updates: List[GroupUpdate],
    session: AsyncSession = Depends(get_db_async_session)
):
    """
    Update managed status for multiple groups.
    Enables or disables bot responses for specific groups.
    """
    try:
        for update in updates:
            statement = select(Group).where(Group.group_jid == update.group_jid)
            result = await session.execute(statement)
            group = result.scalar_one_or_none()
            
            if group:
                group.managed = update.managed
                session.add(group)
        
        await session.commit()
        
        return {"status": "success", "updated": len(updates)}
    
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update groups: {str(e)}")


@router.get("/api/whatsapp/status")
async def whatsapp_status():
    """
    Check WhatsApp connection status.
    Returns whether the bot is connected to WhatsApp Web.
    """
    try:
        client = WhatsAppClient()
        
        # Try to get client info to verify connection
        try:
            info = await client.get_client_info()
            connected = info is not None
        except Exception:
            connected = False
        
        return {
            "connected": connected,
            "timestamp": None  # Could add timestamp if needed
        }
    
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


@router.post("/api/groups/{group_jid}/toggle")
async def toggle_group(
    group_jid: str,
    session: AsyncSession = Depends(get_db_async_session)
):
    """
    Toggle managed status for a single group.
    Convenience endpoint for enabling/disabling individual groups.
    """
    try:
        statement = select(Group).where(Group.group_jid == group_jid)
        result = await session.execute(statement)
        group = result.scalar_one_or_none()
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Toggle the managed status
        group.managed = not group.managed
        session.add(group)
        await session.commit()
        
        return {
            "group_jid": group.group_jid,
            "group_name": group.group_name,
            "managed": group.managed
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to toggle group: {str(e)}")
