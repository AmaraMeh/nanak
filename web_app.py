import asyncio
import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from main import ELearningBot

# Créer application FastAPI
app = FastAPI(title="eLearning Bot Service", version="1.0")

bot_instance: ELearningBot | None = None
bot_task: asyncio.Task | None = None

logger = logging.getLogger("web_app")
logging.basicConfig(level=logging.INFO)

@app.on_event("startup")
async def startup_event():
    global bot_instance, bot_task
    if bot_instance is None:
        logger.info("🚀 Démarrage du bot eLearning...")
        bot_instance = ELearningBot()
        # Lancer le bot en tâche asynchrone
        bot_task = asyncio.create_task(bot_instance.start())
        logger.info("✅ Bot async task démarrée - Prêt à recevoir des commandes")

@app.on_event("shutdown")
async def shutdown_event():
    global bot_instance, bot_task
    if bot_instance:
        bot_instance.stop()
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except Exception:
            pass
    logger.info("Arrêt propre terminé")

@app.get("/health")
async def health():
    if not bot_instance:
        return JSONResponse({"status": "starting", "message": "Bot instance not yet created"}, status_code=503)
    
    if not bot_instance.running:
        return JSONResponse({"status": "stopped", "message": "Bot is not running"}, status_code=503)
    
    try:
        stats = bot_instance.monitor.get_summary_stats()
        return {
            "status": "ok", 
            "message": "Bot is running and ready",
            "scans": stats.get("total_scans", 0), 
            "notifications": stats.get("total_notifications", 0),
            "initial_scan_completed": bot_instance.initial_scan_completed_at is not None
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Health check failed: {str(e)}"}, status_code=503)

@app.get("/stats")
async def stats():
    if not bot_instance:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    return bot_instance.monitor.get_summary_stats()

@app.get("/courses")
async def courses():
    if not bot_instance:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    return {"courses": bot_instance.list_courses()}

@app.post("/scan")
async def trigger_scan():
    if not bot_instance:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    bot_instance.trigger_manual_scan()
    return {"status": "scan_triggered"}

@app.get("/")
async def root():
    return PlainTextResponse("eLearning bot en fonctionnement. Endpoints: /health /stats /courses /scan")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
