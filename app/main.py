from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import asyncio
from app.services.reminder_service import reminder_loop
from app.config import settings
from app.database import create_tables
from app.routers import auth, doctors, patients, appointments, departments, prescriptions, billing, chatbot, analytics,agent

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Hospital Management System with Groq AI Chatbot",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router)
app.include_router(doctors.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(departments.router)
app.include_router(prescriptions.router)
app.include_router(billing.router)
app.include_router(chatbot.router)
app.include_router(analytics.router)
app.include_router(agent.router)
  
# Serve frontend static files using absolute path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/favicon.ico", include_in_schema=False)
    def serve_favicon():
        return FileResponse(os.path.join(FRONTEND_DIR, "favicon.ico"))

    @app.get("/login")
    def serve_login():
        return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

    @app.get("/admin")
    def serve_admin():
        return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))
    
    @app.get("/admin-login")
    def serve_admin_login():
        return FileResponse(os.path.join(FRONTEND_DIR, "admin-login.html"))
    @app.get("/agent")
    def serve_agent():
        return FileResponse(os.path.join(FRONTEND_DIR, "agent.html"))
    
    @app.get("/portal")
    def serve_portal():
        return FileResponse(os.path.join(FRONTEND_DIR, "portal.html"))

    @app.get("/doctor")
    def serve_doctor():
        return FileResponse(os.path.join(FRONTEND_DIR, "doctor.html"))


@app.on_event("startup")
async def startup():
    create_tables()
    app.state.reminder_task = asyncio.create_task(reminder_loop())
    print(f"\n✅  {settings.APP_NAME} started successfully!")
    print(f"🌐  Patient Portal : http://localhost:8000/")
    print(f"🛡️   Admin Dashboard: http://localhost:8000/admin")
    print(f"👨‍⚕️  Doctor Portal  : http://localhost:8000/doctor")
    print(f"📖  API Docs       : http://localhost:8000/api/docs\n")


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": settings.APP_NAME}