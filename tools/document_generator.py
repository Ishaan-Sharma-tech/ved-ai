"""
Document Generator tool — generate PDF files.
"""

import os
import uuid
import logging
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from core.config import get_workspace

logger = logging.getLogger("aether.tools.document_generator")

TOOL_NAME = "document_generator"
TOOL_DESCRIPTION = "Generate clean formatted PDF documents."

async def run(**kwargs) -> str:
    title = kwargs.get("title", "Document")
    body = kwargs.get("body", "")
    filename = kwargs.get("filename") or kwargs.get("file") or None
    
    ws = get_workspace()
        
    if not filename:
        filename = f"report_{uuid.uuid4().hex[:8]}.pdf"
    elif not filename.endswith(".pdf"):
        filename += ".pdf"
        
    filepath = ws / filename
    
    try:
        # ReportLab requires a string path, not a pathlib.Path object on Windows
        doc = SimpleDocTemplate(str(filepath), pagesize=letter)
        styles = getSampleStyleSheet()
        flowables = []
        
        # Add title
        if title:
            flowables.append(Paragraph(title, styles['Title']))
            flowables.append(Spacer(1, 12))
            
        # Add body parsing simple newlines
        for paragraph in body.split('\n\n'):
            if paragraph.strip():
                # Replace single newlines with br tag for reportlab
                p_text = paragraph.strip().replace('\n', '<br/>')
                flowables.append(Paragraph(p_text, styles['Normal']))
                flowables.append(Spacer(1, 12))
                
        doc.build(flowables)
        return f"PDF document generated successfully and saved to {filepath}"
    except Exception as e:
        logger.error(f"PDF built failed: {e}")
        return f"Failed to generate PDF: {e}"
