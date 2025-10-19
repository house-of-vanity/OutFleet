pub mod admin;
pub mod user;
pub mod types;

// Re-export main handler functions for easier access
pub use admin::*;
pub use user::*;
pub use types::*;

use teloxide::{prelude::*, types::CallbackQuery};
use crate::database::DatabaseManager;

/// Handle bot commands
pub async fn handle_command(
    bot: Bot,
    msg: Message,
    cmd: Command,
    db: DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let chat_id = msg.chat.id;
    let from = &msg.from.ok_or("No user info")?;
    let telegram_id = from.id.0 as i64;
    let user_repo = crate::database::repository::UserRepository::new(db.connection());

    match cmd {
        Command::Start => {
            handle_start(bot, chat_id, telegram_id, from, &user_repo, &db).await?;
        }
        Command::Requests => {
            // Check if user is admin
            if user_repo.is_telegram_id_admin(telegram_id).await.unwrap_or(false) {
                // Create a fake callback query for admin requests
                // This is a workaround since the admin_requests function expects a callback query
                // In practice, we could refactor this to not need a callback query
                tracing::info!("Admin {} requested to view requests", telegram_id);
                
                let message = "📋 Use the inline keyboard to view recent requests.";
                let keyboard = teloxide::types::InlineKeyboardMarkup::new(vec![
                    vec![teloxide::types::InlineKeyboardButton::callback("📋 Recent Requests", "admin_requests")],
                ]);
                
                bot.send_message(chat_id, message)
                    .reply_markup(keyboard)
                    .await?;
            } else {
                let lang = get_user_language(from);
                let l10n = super::localization::LocalizationService::new();
                bot.send_message(chat_id, l10n.get(lang, "unauthorized")).await?;
            }
        }
        Command::Stats => {
            // Check if user is admin
            if user_repo.is_telegram_id_admin(telegram_id).await.unwrap_or(false) {
                handle_stats(bot, chat_id, &db).await?;
            } else {
                let lang = get_user_language(from);
                let l10n = super::localization::LocalizationService::new();
                bot.send_message(chat_id, l10n.get(lang, "unauthorized")).await?;
            }
        }
        Command::Broadcast { message } => {
            // Check if user is admin
            if user_repo.is_telegram_id_admin(telegram_id).await.unwrap_or(false) {
                handle_broadcast(bot, chat_id, message, &user_repo).await?;
            } else {
                let lang = get_user_language(from);
                let l10n = super::localization::LocalizationService::new();
                bot.send_message(chat_id, l10n.get(lang, "unauthorized")).await?;
            }
        }
    }

    Ok(())
}

/// Handle regular messages (fallback)
pub async fn handle_message(
    bot: Bot,
    msg: Message,
    db: DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let chat_id = msg.chat.id;
    let from = msg.from.as_ref().ok_or("No user info")?;
    let telegram_id = from.id.0 as i64;
    let user_repo = crate::database::repository::UserRepository::new(db.connection());

    // For non-command messages, just show the start menu
    handle_start(bot, chat_id, telegram_id, from, &user_repo, &db).await?;

    Ok(())
}

/// Handle callback queries from inline keyboards
pub async fn handle_callback_query(
    bot: Bot,
    q: CallbackQuery,
    db: DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    if let Some(data) = &q.data {
        if let Some(callback_data) = CallbackData::parse(data) {
            match callback_data {
                CallbackData::RequestAccess => {
                    handle_request_access(bot, &q, &db).await?;
                }
                CallbackData::MyConfigs => {
                    handle_my_configs_edit(bot, &q, &db).await?;
                }
                CallbackData::Support => {
                    handle_support(bot, &q).await?;
                }
                CallbackData::AdminRequests => {
                    handle_admin_requests_edit(bot, &q, &db).await?;
                }
                CallbackData::ApproveRequest(request_id) => {
                    handle_approve_request(bot, &q, &request_id, &db).await?;
                }
                CallbackData::DeclineRequest(request_id) => {
                    handle_decline_request(bot, &q, &request_id, &db).await?;
                }
                CallbackData::ViewRequest(request_id) => {
                    handle_view_request(bot, &q, &request_id, &db).await?;
                }
                CallbackData::ShowServerConfigs(encoded_server_name) => {
                    handle_show_server_configs(bot, &q, &encoded_server_name, &db).await?;
                }
                CallbackData::SelectServerAccess(request_id) => {
                    handle_select_server_access(bot, &q, &request_id, &db).await?;
                }
                CallbackData::ToggleServer(request_id, server_id) => {
                    handle_toggle_server(bot, &q, &request_id, &server_id, &db).await?;
                }
                CallbackData::ApplyServerAccess(request_id) => {
                    handle_apply_server_access(bot, &q, &request_id, &db).await?;
                }
                CallbackData::Back => {
                    // Back to main menu - edit the existing message
                    handle_start_edit(bot, &q, &db).await?;
                }
                CallbackData::BackToConfigs => {
                    handle_my_configs_edit(bot, &q, &db).await?;
                }
                CallbackData::BackToRequests => {
                    handle_admin_requests_edit(bot, &q, &db).await?;
                }
            }
        } else {
            tracing::warn!("Unknown callback data: {}", data);
            bot.answer_callback_query(q.id.clone()).await?;
        }
    }

    Ok(())
}