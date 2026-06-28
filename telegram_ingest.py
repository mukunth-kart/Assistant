import os
import tempfile
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

import config
import database
import brain

# Helper to ensure DB is initialized
database.init_db()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text tasks sent via Telegram."""
    user_message = update.message.text
    if not user_message:
        return
    
    # Save the user's chat_id in settings for proactive reminders
    database.save_setting("last_chat_id", update.message.chat_id)
    
    # Notify user we are processing
    status_msg = await update.message.reply_text("🧠 Analyzing task details...")
    
    try:
        # Pass to Groq brain for structured parsing (now returns a list of tasks)
        extracted_tasks = brain.parse_input(user_message)
        
        saved_details = []
        for task in extracted_tasks:
            database.insert_flexible_task(
                title=task.title,
                duration_minutes=task.duration_minutes,
                priority_score=task.priority_score,
                deadline=task.deadline
            )
            saved_details.append(
                f"📌 **{task.title}** (⏱️ {task.duration_minutes}m, 🔥 {task.priority_score}/10, 📅 {task.deadline or 'None'})"
            )
        
        # Format response
        success_message = f"✅ **{len(extracted_tasks)} Task(s) Saved!**\n\n" + "\n".join(saved_details)
        await status_msg.edit_text(success_message, parse_mode="Markdown")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to parse task: {str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles voice messages, transcribes them using Groq Whisper, and saves as tasks."""
    voice = update.message.voice
    if not voice:
        return
    
    # Save the user's chat_id in settings for proactive reminders
    database.save_setting("last_chat_id", update.message.chat_id)
    
    status_msg = await update.message.reply_text("🎙️ Downloading voice message...")
    
    try:
        # Download voice file
        file_info = await context.bot.get_file(voice.file_id)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_voice:
            temp_path = temp_voice.name
            
        await file_info.download_to_drive(temp_path)
        await status_msg.edit_text("⚡ Transcribing audio with Groq Whisper...")
        
        # Transcribe audio using Groq client
        client = brain.get_client()
        with open(temp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3"
            )
            
        transcribed_text = transcription.text
        await status_msg.edit_text(f"📝 *Transcribed:* \"{transcribed_text}\"\n\n🧠 Analyzing task details...")
        
        # Parse tasks using LLM brain (now returns a list of tasks)
        extracted_tasks = brain.parse_input(transcribed_text)
        
        saved_details = []
        for task in extracted_tasks:
            database.insert_flexible_task(
                title=task.title,
                duration_minutes=task.duration_minutes,
                priority_score=task.priority_score,
                deadline=task.deadline
            )
            saved_details.append(
                f"📌 **{task.title}** (⏱️ {task.duration_minutes}m, 🔥 {task.priority_score}/10, 📅 {task.deadline or 'None'})"
            )
        
        # Format response
        success_message = (
            f"✅ **{len(extracted_tasks)} Voice Task(s) Saved!**\n\n"
            f"📝 *Transcribed:* \"{transcribed_text}\"\n\n"
            + "\n".join(saved_details)
        )
        await status_msg.edit_text(success_message, parse_mode="Markdown")
        
        # Clean up temp file
        try:
            os.remove(temp_path)
        except OSError:
            pass
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to process voice task: {str(e)}")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all incomplete flexible tasks with numbers."""
    database.save_setting("last_chat_id", update.message.chat_id)
    tasks = database.get_pending_flexible_tasks()
    if not tasks:
        await update.message.reply_text("🎉 You have no pending flexible tasks!")
        return
        
    lines = ["📋 **Pending Flexible Tasks:**"]
    for i, t in enumerate(tasks, 1):
        lines.append(f"{i}. **{t['title']}** (⏱️ {t['duration_minutes']}m, 🔥 Priority: {t['priority_score']})")
    
    lines.append("\n💡 To complete a task, reply with `/done <number>` (e.g. `/done 1`).")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def done_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marks a task as completed based on its list position."""
    database.save_setting("last_chat_id", update.message.chat_id)
    if not context.args:
        await update.message.reply_text("❌ Please specify the task number. Usage: `/done <number>`")
        return
        
    try:
        index = int(context.args[0]) - 1
        tasks = database.get_pending_flexible_tasks()
        if index < 0 or index >= len(tasks):
            await update.message.reply_text("❌ Invalid task number. Use `/tasks` to see list.")
            return
            
        target_task = tasks[index]
        database.complete_flexible_task(target_task["id"])
        await update.message.reply_text(f"✅ Marked task as complete: **{target_task['title']}**", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error completing task: {e}")

def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set. Cannot run bot.")
        return
        
    print("Starting Telegram Ingestion Bot...")
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("tasks", list_tasks))
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(CommandHandler("done", done_task))
    application.add_handler(CommandHandler("complete", done_task))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Run the bot polling
    application.run_polling()

if __name__ == "__main__":
    main()
