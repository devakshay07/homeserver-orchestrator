from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_pr_keyboard(task_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{task_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{task_id}")
        ],
        [
            InlineKeyboardButton("🔄 Regenerate", callback_data=f"regenerate_{task_id}"),
            InlineKeyboardButton("📝 Request Changes", callback_data=f"changes_{task_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
