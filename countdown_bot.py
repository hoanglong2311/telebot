import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, time
import pytz
from aiohttp import web
import asyncio

# Dictionary to store user-specific target dates and water info
user_dates = {}
user_water_info = {}
user_water_counts = {}

# Define Vietnam timezone
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

# Global variable for the bot application
_bot_app = None

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
/sethealth - Set height and weight for water tracking
/water - Log 250ml water intake

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

*Water Tracking:*
• Set your height and weight using `/sethealth HEIGHT WEIGHT`
• Use `/water` each time you drink 250ml
• Receive reminders every 2 hours
• Daily target based on your weight
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

async def sethealth(update: Update, context) -> None:
    """Set user's height and weight for water calculation"""
    try:
        if len(context.args) == 2:
            height = float(context.args[0])
            weight = float(context.args[1])
            
            if 100 <= height <= 250 and 30 <= weight <= 200:
                user_id = update.effective_user.id
                # Calculate daily water target (in ml) - basic formula
                daily_water = weight * 35  # 35ml per kg of body weight
                
                user_water_info[user_id] = {
                    'height': height,
                    'weight': weight,
                    'daily_target': daily_water
                }
                user_water_counts[user_id] = 0  # Reset daily count
                
                await update.message.reply_text(
                    f"Health info set!\nHeight: {height}cm\nWeight: {weight}kg\n"
                    f"Daily water target: {daily_water}ml 💧\n"
                    f"You will receive water reminders every 2 hours."
                )
            else:
                await update.message.reply_text("Please enter valid height (100-250 cm) and weight (30-200 kg)")
        else:
            await update.message.reply_text("Please provide height and weight\nExample: /sethealth 170 65")
    except ValueError:
        await update.message.reply_text("Invalid format! Use: /sethealth HEIGHT WEIGHT\nExample: /sethealth 170 65")

async def water(update: Update, context) -> None:
    """Log water intake"""
    user_id = update.effective_user.id
    if user_id not in user_water_info:
        await update.message.reply_text("Please set your health info first using /sethealth HEIGHT WEIGHT")
        return

    user_water_counts[user_id] = user_water_counts.get(user_id, 0) + 250  # Add 250ml
    target = user_water_info[user_id]['daily_target']
    current = user_water_counts[user_id]
    
    await update.message.reply_text(
        f"Added 250ml of water! 💧\n"
        f"Progress: {current}/{target}ml ({(current/target*100):.1f}%)"
    )

async def water_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send water reminders to users"""
    for user_id, info in user_water_info.items():
        try:
            current = user_water_counts.get(user_id, 0)
            target = info['daily_target']
            
            if current < target:
                remaining = target - current
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"💧 Water Reminder!\n"
                         f"You've had {current}ml today\n"
                         f"Still need {remaining}ml to reach your goal\n"
                         f"Use /water to log 250ml"
                )
        except Exception as e:
            logging.error(f"Failed to send water reminder to user {user_id}: {str(e)}")

async def setup_webhook():
    """Set up webhook for the bot"""
    external_url = os.getenv('RENDER_EXTERNAL_URL')
    token = os.getenv('BOT_TOKEN')
    
    if not external_url:
        logging.error("RENDER_EXTERNAL_URL environment variable not set")
        return
    
    # Remove any existing https:// from the URL to prevent doubles
    external_url = external_url.replace('https://', '').replace('http://', '')
    webhook_url = f"https://{external_url}/webhook"  # Add /webhook path
    logging.info(f"Setting webhook to: {webhook_url}")
    
    try:
        # Delete any existing webhook
        await _bot_app.bot.delete_webhook(drop_pending_updates=True)
        
        # Set the new webhook
        success = await _bot_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            secret_token=token  # Use token as secret
        )
        
        if success:
            logging.info("Webhook setup successful")
        else:
            logging.error("Failed to set webhook")
            raise ValueError("Webhook setup failed")
            
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}")
        raise

async def handle_webhook(request):
    """Handle incoming webhook updates"""
    token = os.getenv("BOT_TOKEN")
    
    # Verify secret token
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != token:
        return web.Response(status=403)
    
    data = await request.json()
    update = Update.de_json(data, _bot_app.bot)
    await _bot_app.process_update(update)
    return web.Response()

async def web_app():
    """Create web application for health check and webhook"""
    app = web.Application()
    app.router.add_get('/', lambda request: web.Response(text='Bot is alive!'))
    app.router.add_post(
        '/webhook',  # Change to a fixed path
        handle_webhook,
        name='webhook'
    )
    return app

async def run_web():
    """Run web server"""
    app = await web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', '8080'))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

async def run_bot():
    """Run the telegram bot"""
    global _bot_app
    
    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    
    # Get token from environment variable
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("No BOT_TOKEN environment variable found!")
    
    # Create the Application instance
    if _bot_app is None:
        _bot_app = Application.builder().token(token).build()
        
        # Add command handlers
        _bot_app.add_handler(CommandHandler("start", start))
        _bot_app.add_handler(CommandHandler("setdate", setdate))
        _bot_app.add_handler(CommandHandler("countdown", countdown))
        _bot_app.add_handler(CommandHandler("help", help_command))
        _bot_app.add_handler(CommandHandler("sethealth", sethealth))
        _bot_app.add_handler(CommandHandler("water", water))

        # Set up the daily reminder job
        job_queue = _bot_app.job_queue
        vietnam_time = time(10, 50)
        utc_time = time((vietnam_time.hour - 7) % 24, vietnam_time.minute)
        
        job_queue.run_daily(
            daily_reminder,
            time=utc_time,
            days=(0, 1, 2, 3, 4, 5, 6)
        )

        # Add water reminder job
        job_queue.run_repeating(
            water_reminder,
            interval=7200,  # 2 hours in seconds
            first=300  # Start first reminder after 5 minutes
        )

    try:
        # Initialize and start the bot
        await _bot_app.initialize()
        await _bot_app.start()
        await setup_webhook()
        
        # Keep the application running
        stop_signal = asyncio.Future()
        await stop_signal
        
    except Exception as e:
        logging.error(f"Bot error: {e}")
    finally:
        if _bot_app and _bot_app.running:
            await _bot_app.stop()
            await _bot_app.shutdown()

async def main():
    """Main function to run both web server and bot"""
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
    # Run the application
    asyncio.run(main())