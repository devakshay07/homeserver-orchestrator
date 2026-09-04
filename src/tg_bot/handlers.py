import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import structlog
from textwrap import dedent

from task_queue.sqlite_queue import SQLiteQueue
from task_queue.models import TaskStatus
from config.settings import settings

logger = structlog.get_logger("telegram")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    await update.effective_message.reply_text(
        "👋 Welcome to HomeServer Orchestrator!\n\n"

        "Send `/build <idea>` to generate a new project.\n"
        "Use `/help` for a list of all commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    text = dedent("""
    🤖 *HomeServer Commands*
    
    `/build <idea>` - Generate a new project
    `/status [task_id]` - Current task status
    `/queue` - List pending tasks
    `/logs [task_id]` - Tail generation logs
    `/pr [task_id]` - Show PR status
    
    `/approve <task_id>` - Merge PR
    `/reject <task_id>` - Close PR, reject task
    `/regenerate <task_id>` - Re-run from spec
    
    `/history [n]` - Last N completed tasks
    `/memory search <query>` - Semantic memory search
    `/cron ...` - Scheduler control
    `/settings` - Show current config
    `/help` - Show this menu
    """)
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def build_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not context.args:
        if update.effective_message:
            await update.effective_message.reply_text("Usage: `/build <idea>`", parse_mode="Markdown")
        return

    idea = " ".join(context.args)
    status_msg = await update.effective_message.reply_text("🤔 Analyzing your request...")
    
    triage_agent = context.bot_data.get('triage_agent')
    if triage_agent:
        analysis = await triage_agent.analyze_request(idea)
        if analysis.get("needs_clarification"):
            question = analysis.get("clarification_question", "Could you provide more details about this project?")
            await status_msg.edit_text(f"❓ **Clarification Needed:**\n\n{question}", parse_mode="Markdown")
            return
            
        tasks_to_queue = analysis.get("tasks", [idea])
    else:
        tasks_to_queue = [idea]
        
    db_queue = context.bot_data['db_queue']
    
    if len(tasks_to_queue) == 1:
        task = db_queue.enqueue({"type": "build", "idea": tasks_to_queue[0]})
        logger.info("New build task queued", task_id=task.id, idea=tasks_to_queue[0])
        await status_msg.edit_text(f"✅ Task queued successfully!\n\n*ID:* `{task.id}`", parse_mode="MarkdownV2")
    else:
        queued_ids = []
        for t_idea in tasks_to_queue:
            t = db_queue.enqueue({"type": "build", "idea": t_idea})
            queued_ids.append(t.id)
            logger.info("New build sub-task queued", task_id=t.id, idea=t_idea)
            
        msg = "✅ Splitting request into multiple tasks:\n\n"
        for i, t_id in enumerate(queued_ids):
            msg += f"• `{t_id[:8]}`: {tasks_to_queue[i][:30]}...\n"
            
        await status_msg.edit_text(msg, parse_mode="Markdown")
async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
        
    try:
        tasks = context.bot_data['db_queue'].list_tasks(limit=10)
        pending_or_progress = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.AWAITING_APPROVAL)]
        
        if not pending_or_progress:
            await update.effective_message.reply_text("The queue is currently empty.")
            return
            
        response = "📋 Current Queue:\n\n"
        for t in pending_or_progress:
            idea = t.payload.get("idea", "Unknown")[:30].replace("_", " ").replace("*", " ") + "..."
            response += f"- {t.id[:8]}: {t.status.value} - {idea}\n"
            
        await update.effective_message.reply_text(response)
    except Exception as e:
        logger.error(f"Queue command failed: {e}")
        await update.effective_message.reply_text("Failed to load queue. Check server logs.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    
    if not context.args:
        tasks = context.bot_data['db_queue'].list_tasks(limit=1)
        if not tasks:
            await update.effective_message.reply_text("No recent tasks found.")
            return
        task = tasks[0]
    else:
        task_id = context.args[0]
        task = context.bot_data['db_queue'].get_task(task_id)
        if not task:
            await update.effective_message.reply_text(f"Task `{task_id}` not found.", parse_mode="Markdown")
            return
            
    idea = task.payload.get("idea", "Unknown")
    response = dedent(f"""
    📊 *Task Status*
    *ID:* `{task.id}`
    *Status:* {task.status.value}
    *Attempts:* {task.attempts}
    *Idea:* {idea}
    *Created:* {task.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
    """)
    await update.effective_message.reply_text(response, parse_mode="Markdown")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    action, _, task_id = data.partition("_")
    if action not in ("approve", "reject", "regenerate", "changes"): return
    
    task = context.bot_data['db_queue'].get_task(task_id)
    if not task:
        await query.edit_message_text(f"{query.message.text}\n\n⚠️ Error: Task {task_id} not found.")
        return
        
    if task.status != TaskStatus.AWAITING_APPROVAL:
        await query.edit_message_text(f"{query.message.text}\n\n⚠️ Error: Task is not awaiting approval. Current status: {task.status.value}")
        return
        
    from gh_client.pr_manager import PRManager
    pr_manager = PRManager()
    
    repo_name = task.payload.get('repo_name')
    pr_url = task.payload.get('pr_url')
    pr_number = None
    if pr_url:
        try: pr_number = int(pr_url.split('/')[-1])
        except: pass
        
    if action == "approve":
        if repo_name and pr_number:
            try:
                await pr_manager.merge_pr(repo_name, pr_number)
                task.status = TaskStatus.DONE
                context.bot_data['db_queue'].update_task(task)
                await query.edit_message_text(f"{query.message.text}\n\n✅ PR Merged! Task {task_id} is DONE.")
            except Exception as e:
                await query.edit_message_text(f"{query.message.text}\n\n⚠️ Error merging PR: {e}")
        else:
            await query.edit_message_text(f"{query.message.text}\n\n⚠️ Error: No repo/PR info in task.")
            
    elif action == "reject":
        if repo_name and pr_number:
            try:
                await pr_manager.close_pr(repo_name, pr_number)
            except Exception as e:
                import structlog
                structlog.get_logger("handlers").warning("PR close failed (reject)", error=str(e), repo=repo_name, pr=pr_number)
        task.status = TaskStatus.REJECTED
        context.bot_data['db_queue'].update_task(task)
        await query.edit_message_text(f"{query.message.text}\n\n❌ Task {task_id} REJECTED.")
        
    elif action == "regenerate":
        if repo_name and pr_number:
            try:
                await pr_manager.close_pr(repo_name, pr_number)
            except Exception as e:
                import structlog
                structlog.get_logger("handlers").warning("PR close failed (regenerate)", error=str(e), repo=repo_name, pr=pr_number)
        task.status = TaskStatus.PENDING
        task.attempts = 0
        context.bot_data['db_queue'].update_task(task)
        await query.edit_message_text(f"{query.message.text}\n\n🔄 Task {task_id} queued for regeneration.")
        
    elif action == "changes":
        await query.edit_message_text(f"{query.message.text}\n\n📝 Changes requested. (Not implemented in UI yet)")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    await update.effective_message.reply_text("Logs tailing not yet implemented in UI. Please check data/logs/generation.log on the server.")

async def pr_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    if not context.args:
        await update.effective_message.reply_text("Usage: `/pr <task_id>`", parse_mode="Markdown")
        return
    task = context.bot_data['db_queue'].get_task(context.args[0])
    if not task:
        await update.effective_message.reply_text("Task not found.")
        return
    pr_url = task.payload.get('pr_url')
    if pr_url:
        await update.effective_message.reply_text(f"PR URL: {pr_url}")
    else:
        await update.effective_message.reply_text("No PR created for this task yet.")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    limit = 5
    if context.args:
        try: limit = int(context.args[0])
        except: pass
    tasks = context.bot_data['db_queue'].list_tasks(limit=limit)
    completed = [t for t in tasks if t.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.REJECTED)]
    if not completed:
        await update.effective_message.reply_text("No completed tasks found.")
        return
    res = "📜 *History*\n\n"

    for t in completed:
        res += f"• `{t.id[:8]}`: {t.status.value}\n"
    await update.effective_message.reply_text(res, parse_mode="Markdown")

async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    if not context.args or context.args[0] != "search" or len(context.args) < 2:
        await update.effective_message.reply_text("Usage: `/memory search <query>`", parse_mode="Markdown")
        return
    query = " ".join(context.args[1:])
    from memory.retriever import Retriever
    retriever = Retriever()
    results = await retriever.search_prompts(query, 1)
    if results:
        await update.effective_message.reply_text(f"🧠 *Memory Result:*\n\n{results}")

    else:
        await update.effective_message.reply_text("No memory matches found.")


async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    if not context.args:
        await update.effective_message.reply_text("Usage: `/approve <task_id>`", parse_mode="Markdown")
        return
    task_id = context.args[0]
    task = context.bot_data['db_queue'].get_task(task_id)
    if not task:
        await update.effective_message.reply_text("Task not found.")
        return
    if task.status != TaskStatus.AWAITING_APPROVAL:
        await update.effective_message.reply_text("Task is not awaiting approval.")
        return
        
    repo_name = task.payload.get('repo_name')
    pr_url = task.payload.get('pr_url')
    pr_number = None
    if pr_url:
        try: pr_number = int(pr_url.split('/')[-1])
        except: pass
        
    if repo_name and pr_number:
        from gh_client.pr_manager import PRManager
        pr_manager = PRManager()
        try:
            await pr_manager.merge_pr(repo_name, pr_number)
            task.status = TaskStatus.DONE
            context.bot_data['db_queue'].update_task(task)
            await update.effective_message.reply_text(f"✅ PR Merged! Task {task_id} is DONE.")
        except Exception as e:
            await update.effective_message.reply_text(f"⚠️ Error merging PR: {e}")
    else:
        await update.effective_message.reply_text("Missing PR details.")

async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    if not context.args:
        await update.effective_message.reply_text("Usage: `/reject <task_id>`", parse_mode="Markdown")
        return
    task_id = context.args[0]
    task = context.bot_data['db_queue'].get_task(task_id)
    if not task:
        await update.effective_message.reply_text("Task not found.")
        return
        
    repo_name = task.payload.get('repo_name')
    pr_url = task.payload.get('pr_url')
    pr_number = None
    if pr_url:
        try: pr_number = int(pr_url.split('/')[-1])
        except: pass
        
    if repo_name and pr_number:
        from gh_client.pr_manager import PRManager
        pr_manager = PRManager()
        try:
            await pr_manager.close_pr(repo_name, pr_number)
        except Exception as e:
            import structlog
            structlog.get_logger("handlers").warning("PR close failed (/reject)", error=str(e), repo=repo_name, pr=pr_number)
        
    task.status = TaskStatus.REJECTED
    context.bot_data['db_queue'].update_task(task)
    await update.effective_message.reply_text(f"❌ Task {task_id} REJECTED.")

async def regenerate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    if not context.args:
        await update.effective_message.reply_text("Usage: `/regenerate <task_id>`", parse_mode="Markdown")
        return
    task_id = context.args[0]
    task = context.bot_data['db_queue'].get_task(task_id)
    if not task:
        await update.effective_message.reply_text("Task not found.")
        return
        
    repo_name = task.payload.get('repo_name')
    pr_url = task.payload.get('pr_url')
    pr_number = None
    if pr_url:
        try: pr_number = int(pr_url.split('/')[-1])
        except: pass
        
    if repo_name and pr_number and task.status == TaskStatus.AWAITING_APPROVAL:
        from gh_client.pr_manager import PRManager
        pr_manager = PRManager()
        try:
            await pr_manager.close_pr(repo_name, pr_number)
        except Exception as e:
            import structlog
            structlog.get_logger("handlers").warning("PR close failed (/regenerate)", error=str(e), repo=repo_name, pr=pr_number)
        
    task.status = TaskStatus.PENDING
    task.attempts = 0
    context.bot_data['db_queue'].update_task(task)
    await update.effective_message.reply_text(f"🔄 Task {task_id} queued for regeneration.")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    # Mask secrets
    safe_settings = {
        "OWNER_TELEGRAM_ID": settings.owner_telegram_id,
        "GEMINI_KEYS_COUNT": len(settings.gemini_keys),
        "GITHUB_APP_ID": settings.github_app_id,
        "GITHUB_OWNER": settings.github_owner,
        "TIMEZONE": settings.timezone,
        "LOG_LEVEL": settings.log_level,
        "MAX_RETRIES": settings.max_retries,
    }
    res = "⚙️ *Current Settings*\n\n"

    for k, v in safe_settings.items():
        res += f"*{k}:* `{v}`\n"
    await update.effective_message.reply_text(res, parse_mode="Markdown")


async def pending_notifications_command(update, context):
    from tg_bot.notifier import DEAD_LETTER_PATH
    import json
    if not DEAD_LETTER_PATH.exists():
        await update.effective_message.reply_text("No pending notifications.", parse_mode="Markdown")
        return
        
    with open(DEAD_LETTER_PATH, "r") as f:
        lines = f.readlines()
        
    if not lines:
        await update.effective_message.reply_text("No pending notifications.", parse_mode="Markdown")
        return
        
    await update.effective_message.reply_text(f"Resending {len(lines)} failed notifications...")
    DEAD_LETTER_PATH.unlink()
    
    notifier = context.bot_data['notifier']
    
    try:
        for i, line in enumerate(lines):
            payload = json.loads(line)
            if payload.get("type") == "message":
                await notifier.send_message(payload.get("text"), payload.get("parse_mode", "Markdown"))
            elif payload.get("type") == "pr_notification":
                await notifier.send_pr_notification(payload.get("text"), payload.get("task_id"))
    except Exception:
        with open(DEAD_LETTER_PATH, "a") as f:
            for remaining_line in lines[i:]:
                f.write(remaining_line)
        raise


async def stats_command(update, context):
    import shutil
    from task_queue.models import TaskStatus
    
    stat = shutil.disk_usage("data/")
    free_gb = stat.free / (1024 ** 3)
    used_pct = (stat.used / stat.total) * 100
    
    db_queue = context.bot_data['db_queue']
    worker = context.bot_data['worker']
    cron_manager = context.bot_data['cron_manager']
    
    tasks = db_queue.list_tasks(limit=200)
    pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
    done    = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    failed  = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    
    is_running = False
    if hasattr(worker, '_running'):
        is_running = worker._running
        
    num_jobs = 0
    if cron_manager and hasattr(cron_manager, 'scheduler'):
        num_jobs = len(context.bot_data['cron_manager'].scheduler.get_jobs())

    msg = (
        f"📊 *HomeServer Stats*\n\n"
        f"💾 Disk: `{free_gb:.1f}` GB free (`{used_pct:.0f}%` used)\n"
        f"📋 Tasks: `{pending}` pending | `{done}` done | `{failed}` failed\n"
        f"⚙️ Worker: `{'running' if is_running else 'stopped'}`\n"
        f"📅 Cron jobs: `{num_jobs}`"
    )
    await update.effective_message.reply_text(msg, parse_mode="Markdown")


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_message.voice:
        return
        
    status_msg = await update.effective_message.reply_text("🎤 Listening...")
    
    try:
        # Download the voice note
        voice_file = await update.effective_message.voice.get_file()
        file_bytes = await voice_file.download_as_bytearray()
        
        # Use Gemini to transcribe
        triage_agent = context.bot_data.get('triage_agent')
        if not triage_agent:
            await status_msg.edit_text("❌ TriageAgent not initialized.")
            return
            
        media_data = {
            "mime_type": "audio/ogg",
            "data": file_bytes
        }
        
        transcript = await triage_agent.client.generate_content(settings.gemini_model_spec, "Transcribe this audio precisely. Return only the transcription text.", media_data=media_data)
        
        await status_msg.edit_text(f"🗣️ *Transcript:* _{transcript}_\n\n🤔 Analyzing request...", parse_mode="Markdown")
        
        # Proceed with triage exactly like build_command
        idea = transcript
        analysis = await triage_agent.analyze_request(idea)
        
        if analysis.get("needs_clarification"):
            question = analysis.get("clarification_question", "Could you provide more details?")
            await status_msg.edit_text(f"🗣️ *Transcript:* _{transcript}_\n\n❓ **Clarification Needed:**\n\n{question}", parse_mode="Markdown")
            return
            
        tasks_to_queue = analysis.get("tasks", [idea])
        db_queue = context.bot_data['db_queue']
        
        if len(tasks_to_queue) == 1:
            task = db_queue.enqueue({"type": "build", "idea": tasks_to_queue[0]})
            logger.info("New build task queued via voice", task_id=task.id)
            await status_msg.edit_text(f"🗣️ *Transcript:* _{transcript}_\n\n✅ Task queued successfully!\n\n*ID:* `{task.id}`", parse_mode="Markdown")
        else:
            queued_ids = []
            for t_idea in tasks_to_queue:
                t = db_queue.enqueue({"type": "build", "idea": t_idea})
                queued_ids.append(t.id)
                
            msg = f"🗣️ *Transcript:* _{transcript}_\n\n✅ Splitting request into multiple tasks:\n\n"
            for i, t_id in enumerate(queued_ids):
                msg += f"• `{t_id[:8]}`: {tasks_to_queue[i][:30]}...\n"
            await status_msg.edit_text(msg, parse_mode="Markdown")
            
    except Exception as e:
        logger.error("Voice command failed", error=str(e))
        await status_msg.edit_text(f"❌ Failed to process voice note: {str(e)}")

def register_handlers(app) -> None:
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("build", build_command))
    app.add_handler(MessageHandler(filters.VOICE, voice_command))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cron", cron_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("pr", pr_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("reject", reject_command))
    app.add_handler(CommandHandler("regenerate", regenerate_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("pending_notifications", pending_notifications_command))
    app.add_handler(CommandHandler("stats", stats_command))


from scheduler.job_builder import JobBuilder


async def cron_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message: return
    
    args = context.args
    if not args:
        await update.effective_message.reply_text(
            "Usage:\n" \
            "`/cron list`\n" \
            "`/cron remove <job_id>`\n" \
            "`/cron daily HH:MM <idea>`\n" \
            "`/cron weekly <day> HH:MM <idea>`",
            parse_mode="Markdown"
        )
        return

    cmd = args[0].lower()
    
    if cmd == "list":
        jobs = context.bot_data['cron_manager'].get_jobs()
        if not jobs:
            await update.effective_message.reply_text("No scheduled jobs.")
            return
        res = "📅 *Scheduled Jobs*\n\n"

        for j in jobs:
            next_run = j.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if j.next_run_time else "Paused"
            res += f"• `{j.id}`: next run at {next_run}\n"
        await update.effective_message.reply_text(res, parse_mode="Markdown")
        
    elif cmd == "remove":
        if len(args) < 2:
            await update.effective_message.reply_text("Provide a job ID.")
            return
        if context.bot_data['cron_manager'].remove_job(args[1]):
            await update.effective_message.reply_text("Job removed.")
        else:
            await update.effective_message.reply_text("Failed to remove job.")
            
    elif cmd == "daily":
        if len(args) < 3:
            await update.effective_message.reply_text("Format: `/cron daily HH:MM <idea>`")
            return
        time_str = args[1]
        idea = " ".join(args[2:])
        try:
            job_id = JobBuilder.add_daily_job(time_str, idea)
            await update.effective_message.reply_text(f"✅ Daily job added with ID: `{job_id}`", parse_mode="Markdown")
        except Exception as e:
            await update.effective_message.reply_text(f"Error: {e}")
            
    elif cmd == "weekly":
        if len(args) < 4:
            await update.effective_message.reply_text("Format: `/cron weekly <day> HH:MM <idea>`")
            return
        day = args[1]
        time_str = args[2]
        idea = " ".join(args[3:])
        try:
            job_id = JobBuilder.add_weekly_job(day, time_str, idea)
            await update.effective_message.reply_text(f"✅ Weekly job added with ID: `{job_id}`", parse_mode="Markdown")
        except Exception as e:
            await update.effective_message.reply_text(f"Error: {e}")
