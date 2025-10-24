pub mod admin;
pub mod types;
pub mod user;

// Re-export main handler functions for easier access
pub use admin::*;
pub use types::*;
pub use user::*;

use crate::config::AppConfig;
use crate::database::DatabaseManager;
use teloxide::{prelude::*, types::CallbackQuery};

/// Handle bot commands
pub async fn handle_command(
    bot: Bot,
    msg: Message,
    cmd: Command,
    db: DatabaseManager,
    app_config: AppConfig,
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
            if user_repo
                .is_telegram_id_admin(telegram_id)
                .await
                .unwrap_or(false)
            {
                // Create a fake callback query for admin requests
                // This is a workaround since the admin_requests function expects a callback query
                // In practice, we could refactor this to not need a callback query
                tracing::info!("Admin {} requested to view requests", telegram_id);

                let message = "📋 Use the inline keyboard to view recent requests.";
                let keyboard = teloxide::types::InlineKeyboardMarkup::new(vec![vec![
                    teloxide::types::InlineKeyboardButton::callback(
                        "📋 Recent Requests",
                        "admin_requests",
                    ),
                ]]);

                bot.send_message(chat_id, message)
                    .reply_markup(keyboard)
                    .await?;
            } else {
                let lang = get_user_language(from);
                let l10n = super::localization::LocalizationService::new();
                bot.send_message(chat_id, l10n.get(lang, "unauthorized"))
                    .await?;
            }
        }
        Command::Stats => {
            // Check if user is admin
            if user_repo
                .is_telegram_id_admin(telegram_id)
                .await
                .unwrap_or(false)
            {
                handle_stats(bot, chat_id, &db).await?;
            } else {
                let lang = get_user_language(from);
                let l10n = super::localization::LocalizationService::new();
                bot.send_message(chat_id, l10n.get(lang, "unauthorized"))
                    .await?;
            }
        }
        Command::Broadcast { message } => {
            // Check if user is admin
            if user_repo
                .is_telegram_id_admin(telegram_id)
                .await
                .unwrap_or(false)
            {
                handle_broadcast(bot, chat_id, message, &user_repo).await?;
            } else {
                let lang = get_user_language(from);
                let l10n = super::localization::LocalizationService::new();
                bot.send_message(chat_id, l10n.get(lang, "unauthorized"))
                    .await?;
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
    _app_config: AppConfig,
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
    app_config: AppConfig,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // Wrap all callback handling in a try-catch to send main menu on any error
    let result = async {
        if let Some(data) = &q.data {
            if let Some(callback_data) = CallbackData::parse(data) {
                match callback_data {
                    CallbackData::RequestAccess => {
                        handle_request_access(bot.clone(), &q, &db).await?;
                    }
                    CallbackData::MyConfigs => {
                        handle_my_configs_edit(bot.clone(), &q, &db).await?;
                    }
                    CallbackData::SubscriptionLink => {
                        handle_subscription_link(bot.clone(), &q, &db, &app_config).await?;
                    }
                    CallbackData::Support => {
                        handle_support(bot.clone(), &q).await?;
                    }
                    CallbackData::AdminRequests => {
                        handle_admin_requests_edit(bot.clone(), &q, &db).await?;
                    }
                    CallbackData::RequestList(page) => {
                        handle_request_list(bot.clone(), &q, &db, page).await?;
                    }
                    CallbackData::ApproveRequest(request_id) => {
                        handle_approve_request(bot.clone(), &q, &request_id, &db).await?;
                    }
                    CallbackData::DeclineRequest(request_id) => {
                        handle_decline_request(bot.clone(), &q, &request_id, &db).await?;
                    }
                    CallbackData::ViewRequest(request_id) => {
                        handle_view_request(bot.clone(), &q, &request_id, &db).await?;
                    }
                    CallbackData::ShowServerConfigs(encoded_server_name) => {
                        handle_show_server_configs(bot.clone(), &q, &encoded_server_name, &db).await?;
                    }
                    CallbackData::SelectServerAccess(request_id) => {
                        // The request_id is now the full UUID from the mapping
                        let short_id = types::generate_short_request_id(&request_id);
                        handle_select_server_access(bot.clone(), &q, &short_id, &db).await?;
                    }
                    CallbackData::ToggleServer(request_id, server_id) => {
                        // Both IDs are now full UUIDs from the mapping
                        let short_request_id = types::generate_short_request_id(&request_id);
                        let short_server_id = types::generate_short_server_id(&server_id);
                        handle_toggle_server(bot.clone(), &q, &short_request_id, &short_server_id, &db).await?;
                    }
                    CallbackData::ApplyServerAccess(request_id) => {
                        // The request_id is now the full UUID from the mapping
                        let short_id = types::generate_short_request_id(&request_id);
                        handle_apply_server_access(bot.clone(), &q, &short_id, &db).await?;
                    }
                    CallbackData::Back => {
                        // Back to main menu - edit the existing message
                        handle_start_edit(bot.clone(), &q, &db).await?;
                    }
                    CallbackData::BackToConfigs => {
                        handle_my_configs_edit(bot.clone(), &q, &db).await?;
                    }
                    CallbackData::BackToRequests => {
                        handle_admin_requests_edit(bot.clone(), &q, &db).await?;
                    }
                    CallbackData::ManageUsers => {
                        handle_manage_users(bot.clone(), &q, &db).await?;
                    }
                    CallbackData::UserList(page) => {
                        handle_user_list(bot.clone(), &q, &db, page).await?;
                    }
                    CallbackData::UserDetails(user_id) => {
                        handle_user_details(bot.clone(), &q, &db, &user_id).await?;
                    }
                    CallbackData::UserManageAccess(user_id) => {
                        handle_user_manage_access(bot.clone(), &q, &db, &user_id).await?;
                    }
                    CallbackData::UserToggleServer(user_id, server_id) => {
                        handle_user_toggle_server(bot.clone(), &q, &db, &user_id, &server_id).await?;
                    }
                    CallbackData::UserApplyAccess(user_id) => {
                        handle_user_apply_access(bot.clone(), &q, &db, &user_id).await?;
                    }
                    CallbackData::BackToUsers(page) => {
                        handle_user_list(bot.clone(), &q, &db, page).await?;
                    }
                    CallbackData::BackToMenu => {
                        handle_start_edit(bot.clone(), &q, &db).await?;
                    }
                }
            } else {
                tracing::warn!("Unknown callback data: {}", data);
                return Err("Invalid callback data".into());
            }
        }
        Ok::<(), Box<dyn std::error::Error + Send + Sync>>(())
    }.await;

    // If any error occurred, send main menu and answer callback query
    if let Err(e) = result {
        tracing::warn!("Error handling callback query '{}': {}", q.data.as_deref().unwrap_or("None"), e);
        
        // Answer the callback query first to remove loading state
        let _ = bot.answer_callback_query(q.id.clone()).await;
        
        // Try to send main menu
        if let Some(message) = q.message {
            let chat_id = message.chat().id;
            let from = &q.from;
            let telegram_id = from.id.0 as i64;
            let user_repo = crate::database::repository::UserRepository::new(db.connection());
            
            // Try to send main menu - if this fails too, just log it
            if let Err(menu_error) = handle_start(bot, chat_id, telegram_id, from, &user_repo, &db).await {
                tracing::error!("Failed to send main menu after callback error: {}", menu_error);
            }
        }
    }

    Ok(())
}
