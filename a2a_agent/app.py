import os
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import base64

# Your imports
from gemini_agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService
from google.genai.types import Content, Part

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Cymbal Bank AI Agent API",
    description="Financial Assistant powered by Gemini",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ADK services
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()
memory_service = InMemoryMemoryService()

# Create runner
runner = Runner(
    app_name="cymbal_bank_ai_agent",
    agent=root_agent,
    session_service=session_service,
    artifact_service=artifact_service,
    memory_service=memory_service,
)

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    user_id: str = "user-001"
    session_id: Optional[str] = None
    skill: str = "chat"  # "chat" or "backend_services"

class ChatResponse(BaseModel):
    response: str
    session_id: str
    skill_used: str
    artifacts: Optional[List[Dict[str, Any]]] = None  # For graphs/images

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "cymbal-bank-ai-agent",
        "version": "1.0.0"
    }

@app.get("/debug/artifacts/{user_id}/{session_id}")
async def debug_artifacts(user_id: str, session_id: str):
    """Debug endpoint to check what artifacts exist for a session"""
    try:
        artifacts = await artifact_service.list_artifact_keys(
            app_name="cymbal_bank_ai_agent",
            user_id=user_id,
            session_id=session_id,
        )
        return {
            "artifacts": artifacts,
            "count": len(artifacts)
        }
    except Exception as e:
        return {
            "error": str(e),
            "artifacts": [],
            "count": 0
        }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Generate session ID if not provided
        if not request.session_id:
            import uuid
            request.session_id = str(uuid.uuid4())
        
        logger.info(f"Processing {request.skill} request for user {request.user_id}, session: {request.session_id}")
        logger.info(f"Request message: {request.message[:100]}...")
        
        # Create or get session
        session = await runner.session_service.get_session(
            app_name="cymbal_bank_ai_agent",
            user_id=request.user_id,
            session_id=request.session_id,
        )
        
        if not session:
            session = await runner.session_service.create_session(
                app_name="cymbal_bank_ai_agent",
                user_id=request.user_id,
                session_id=request.session_id,
                state={"user_id": request.user_id}
            )
        
        # Create user message
        user_content = Content(role="user", parts=[Part(text=request.message)])
        
        # Process through runner
        response_text = ""
        artifacts = []
        
        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=request.session_id,
            new_message=user_content,
        ):
            # Check for artifacts in event actions
            if hasattr(event, 'actions') and event.actions and hasattr(event.actions, 'artifact_delta') and event.actions.artifact_delta:
                logger.info(f"Found artifact_delta: {event.actions.artifact_delta}")
                for artifact_name, version in event.actions.artifact_delta.items():
                    if artifact_name.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        logger.info(f"Loading artifact: {artifact_name}")
                        # Load the artifact
                        artifact = await artifact_service.load_artifact(
                            app_name="cymbal_bank_ai_agent",
                            user_id=request.user_id,
                            session_id=request.session_id,
                            filename=artifact_name
                        )
                        if artifact and hasattr(artifact, 'inline_data'):
                            # Convert to base64 for frontend
                            image_base64 = base64.b64encode(artifact.inline_data.data).decode('utf-8')
                            artifacts.append({
                                "type": "image",
                                "name": artifact_name,
                                "data": f"data:image/png;base64,{image_base64}",
                                "mime_type": "image/png"
                            })
                            logger.info(f"Successfully loaded artifact: {artifact_name}")
                        else:
                            logger.warning(f"Could not load artifact: {artifact_name}")
            
            # Check for artifacts (graphs/images) in event.artifacts
            if hasattr(event, 'artifacts') and event.artifacts:
                logger.info(f"Found event.artifacts: {event.artifacts}")
                for artifact_name, artifact_data in event.artifacts.items():
                    if artifact_name.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        # Load the artifact
                        artifact = await artifact_service.load_artifact(
                            app_name="cymbal_bank_ai_agent",
                            user_id=request.user_id,
                            session_id=request.session_id,
                            filename=artifact_name
                        )
                        if artifact and hasattr(artifact, 'inline_data'):
                            # Convert to base64 for frontend
                            image_base64 = base64.b64encode(artifact.inline_data.data).decode('utf-8')
                            artifacts.append({
                                "type": "image",
                                "name": artifact_name,
                                "data": f"data:image/png;base64,{image_base64}",
                                "mime_type": "image/png"
                            })
            
            if event.is_final_response() and event.content and event.content.parts:
                response_text = event.content.parts[0].text
                
                # Check for artifacts in final session after completion
                session = await runner.session_service.get_session(
                    app_name="cymbal_bank_ai_agent",
                    user_id=request.user_id,
                    session_id=request.session_id,
                )
                
                # List all artifacts for this session
                try:
                    available_artifacts = await artifact_service.list_artifact_keys(
                        app_name="cymbal_bank_ai_agent",
                        user_id=request.user_id,
                        session_id=request.session_id,
                    )
                    logger.info(f"Available artifacts: {available_artifacts}")
                    
                    for artifact_name in available_artifacts:
                        if artifact_name.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            # Check if we haven't already added this artifact
                            if not any(a['name'] == artifact_name for a in artifacts):
                                artifact = await artifact_service.load_artifact(
                                    app_name="cymbal_bank_ai_agent",
                                    user_id=request.user_id,
                                    session_id=request.session_id,
                                    filename=artifact_name
                                )
                                if artifact and hasattr(artifact, 'inline_data'):
                                    image_base64 = base64.b64encode(artifact.inline_data.data).decode('utf-8')
                                    artifacts.append({
                                        "type": "image",
                                        "name": artifact_name,
                                        "data": f"data:image/png;base64,{image_base64}",
                                        "mime_type": "image/png"
                                    })
                                    logger.info(f"Added artifact from session: {artifact_name}")
                except Exception as e:
                    logger.error(f"Error listing artifacts: {e}")
                
                break
        
        logger.info(f"Final response - Found {len(artifacts)} artifacts")
        if artifacts:
            logger.info(f"Artifact names: {[a['name'] for a in artifacts]}")
        
        return ChatResponse(
            response=response_text,
            session_id=request.session_id,
            skill_used=request.skill,
            artifacts=artifacts if artifacts else None
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "message": "Cymbal Bank AI Agent API",
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
