# بدلاً من السطر ده في آخر الكود:
# app.run_polling()

# استخدم ده:
import asyncio
from aiohttp import web

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", bot_start))
    app.add_handler(CommandHandler("help", bot_help))
    app.add_handler(CommandHandler("stats", bot_stats))
    app.add_handler(CommandHandler("tokenonly", bot_tokenonly))
    app.add_handler(CommandHandler("fullinfo", bot_fullinfo))
    app.add_handler(CommandHandler("cancel", bot_cancel))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    await set_commands(app)
    
    PORT = int(os.environ.get('PORT', 8443))
    DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'your-domain.railway.app')
    
    await app.bot.set_webhook(f"https://{DOMAIN}/webhook")
    await app.run_webhook(listen="0.0.0.0", port=PORT)

if __name__ == "__main__":
    asyncio.run(main())
