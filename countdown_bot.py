import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, time
import pytz
from aiohttp import web
import asyncio

# Dictionary to store user-specific target dates
user_dates = {}

# Define Vietnam timezone
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

async def start(update: Update, context) -> None:
    await update.message.reply_text("Hello! Use /setdate YYYY-MM-DD to set your target date, then /countdown to check remaining days.\n\nType /help for detailed instructions.")

async def setdate(update: Update, context) -> None:
    try:
        if context.args:
            date_str = context.args[0]
            # Parse the date without timezone first
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            # Store as naive datetime (without timezone) for simplicity
            user_id = update.effective_user.id
            user_dates[user_id] = target_date
            await update.message.reply_text(f"Target date set to {date_str}! You will receive daily reminders at 10:50 AM.")
        else:
            await update.message.reply_text("Please provide a date in YYYY-MM-DD format\nExample: /setdate 2025-12-31")
    except ValueError:
        await update.message.reply_text("Invalid date format! Please use YYYY-MM-DD\nExample: /setdate 2025-12-31")

async def countdown(update: Update, context) -> None:
    user_id = update.effective_user.id
    if user_id not in user_dates:
        await update.message.reply_text("Please set your target date first using /setdate YYYY-MM-DD")
        return

    now = datetime.now()
    target_date = user_dates[user_id]
    remaining = target_date - now

    if remaining.days >= 0:
        await update.message.reply_text(f"{remaining.days} days remaining until {target_date.strftime('%Y-%m-%d')} 🎉")
    else:
        await update.message.reply_text("The target date has passed!")

async def help_command(update: Update, context) -> None:
    help_text = """
🤖 *Countdown Bot Guide* 🤖

*Available Commands:*
/start - Start the bot
/help - Show this help message
/setdate - Set your target date
/countdown - Check remaining days

*How to use:*
1️⃣ Set your target date using:
   `/setdate YYYY-MM-DD`
   Example: `/setdate 2025-12-31`

2️⃣ Check remaining days using:
   `/countdown`

*Date Format:*
• Use YYYY-MM-DD format
• Year must be 4 digits
• Month must be 2 digits (01-12)
• Day must be 2 digits (01-31)

*Examples:*
✅ Correct: 2024-05-01
❌ Wrong: 2024-5-1
❌ Wrong: 01-05-2024

*Daily Reminders:*
• You will receive automatic reminders at 10:50 AM (Vietnam time)
• Reminders will show your remaining days
• Reminders continue until the target date is reached

*Note:*
• Each user can set their own target date
• The bot will remember your date until restart
• Make sure you haven't blocked the bot to receive reminders
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send daily reminders to all users who have set a target date"""
    now = datetime.now(VN_TIMEZONE)
    
    for user_id, target_date in user_dates.items():
        try:
            # Convert target_date to aware datetime with Vietnam timezone
            target_date_aware = VN_TIMEZONE.localize(target_date)
            remaining = target_date_aware - now
            
            if remaining.days >= 0:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🔔 Daily Reminder:\n{remaining.days} days remaining until {target_date.strftime('%Y-%m-%d')} 🎉"
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🔔 The target date has passed!"
                )
        except Exception as e:
            logging.error(f"Failed to send reminder to user {user_id}: {str(e)}")

async def web_app():
    """Create web application for health check"""
    app = web.Application()
    app.router.add_get('/', lambda request: web.Response(text='Bot is alive!'))
    return app

async def run_web():
    app = await web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    # Get port from environment variable
    port = int(os.environ.get('PORT', '8080'))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

async def run_bot():
    """Run the telegram bot"""
    # Configure logging
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("No BOT_TOKEN environment variable found!")
        
    application = Application.builder().token(token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setdate", setdate))
    application.add_handler(CommandHandler("countdown", countdown))
    application.add_handler(CommandHandler("help", help_command))

    # Set up the daily job
    job_queue = application.job_queue
    vietnam_time = time(10, 50)
    utc_time = time((vietnam_time.hour - 7) % 24, vietnam_time.minute)
    
    job_queue.run_daily(
        daily_reminder,
        time=utc_time,
        days=(0, 1, 2, 3, 4, 5, 6)
    )

    # Start the bot without polling
    await application.initialize()
    await application.start()
    
    try:
        # Run the bot in the background
        await application.updater.start_polling()
        # Keep the bot running
        await application.updater.running
    finally:
        await application.stop()

async def main():
    try:
        # Run both web server and bot
        await asyncio.gather(
            run_web(),
            run_bot()
        )
    except Exception as e:
        logging.error(f"Error: {e}")
        raise

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Run the application
    asyncio.run(main())