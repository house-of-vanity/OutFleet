use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};
use teloxide::{
    prelude::*,
    types::{CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup},
};
use uuid::Uuid;

use super::super::localization::{Language, LocalizationService};
use super::types::{
    generate_short_request_id, generate_short_server_id, generate_short_user_id,
    get_full_request_id, get_full_server_id, get_selected_servers, get_user_language,
};
use super::user::handle_start;
use crate::database::entities::user_request::RequestStatus;
use crate::database::repository::{UserRepository, UserRequestRepository};
use crate::database::DatabaseManager;

/// Handle admin requests edit (show list of recent requests) - redirect to first page
pub async fn handle_admin_requests_edit(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    handle_request_list(bot, q, db, 1).await
}

/// Handle request list with pagination
pub async fn handle_request_list(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
    page: u32,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let admin_telegram_id = q.from.id.0 as i64;
    let lang = Language::English; // Default admin language
    let l10n = LocalizationService::new();
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    let user_repo = UserRepository::new(db.connection());
    let request_repo = UserRequestRepository::new(db.connection().clone());

    // Check if user is admin
    if !user_repo
        .is_telegram_id_admin(admin_telegram_id)
        .await
        .unwrap_or(false)
    {
        bot.answer_callback_query(q.id.clone())
            .text(l10n.get(lang, "unauthorized"))
            .await?;
        return Ok(());
    }

    let per_page = 20;
    let offset = (page - 1) * per_page;

    // Get total request count
    let total_requests = match request_repo.count_all().await {
        Ok(count) => count,
        Err(e) => {
            tracing::error!("Failed to count requests: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "error_occurred"))
                .await?;
            return Ok(());
        }
    };

    if total_requests == 0 {
        let message = l10n.get(lang.clone(), "no_pending_requests");
        let keyboard = InlineKeyboardMarkup::new(vec![vec![InlineKeyboardButton::callback(
            l10n.get(lang, "back_to_menu"),
            "back_to_menu",
        )]]);

        if let Some(msg) = &q.message {
            if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
                bot.edit_message_text(chat_id, regular_msg.id, message)
                    .reply_markup(keyboard)
                    .await?;
            }
        }

        bot.answer_callback_query(q.id.clone()).await?;
        return Ok(());
    }

    // Get requests for current page
    let requests = match request_repo
        .find_paginated(offset as u64, per_page as u64)
        .await
    {
        Ok(requests) => requests,
        Err(e) => {
            tracing::error!("Failed to get requests: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "error_occurred"))
                .await?;
            return Ok(());
        }
    };

    let total_pages = (total_requests + per_page as i64 - 1) / per_page as i64;

    // Build message
    let mut message_lines = vec!["📋 <b>Access Requests</b>".to_string()];
    message_lines.push(format!(
        "\n{}",
        l10n.format(
            lang.clone(),
            "page_info",
            &[
                ("page", &page.to_string()),
                ("total", &total_pages.to_string())
            ]
        )
    ));
    message_lines.push("".to_string());

    // Build request buttons
    let mut keyboard_buttons = Vec::new();

    for request in &requests {
        let status_emoji = match request.status.as_str() {
            "pending" => "⏳",
            "approved" => "✅",
            "declined" => "❌",
            _ => "❓",
        };

        let username = request.telegram_username.as_deref().unwrap_or("unknown");
        let request_display = format!("{} {} @{}", status_emoji, request.get_full_name(), username);

        let short_request_id = generate_short_request_id(&request.id.to_string());
        keyboard_buttons.push(vec![InlineKeyboardButton::callback(
            request_display,
            format!("view_request:{}", short_request_id),
        )]);
    }

    // Add pagination buttons
    let mut pagination_row = Vec::new();

    if page > 1 {
        pagination_row.push(InlineKeyboardButton::callback(
            l10n.get(lang.clone(), "prev_page"),
            format!("request_list:{}", page - 1),
        ));
    }

    if page < total_pages as u32 {
        pagination_row.push(InlineKeyboardButton::callback(
            l10n.get(lang.clone(), "next_page"),
            format!("request_list:{}", page + 1),
        ));
    }

    if !pagination_row.is_empty() {
        keyboard_buttons.push(pagination_row);
    }

    // Add back button
    keyboard_buttons.push(vec![InlineKeyboardButton::callback(
        l10n.get(lang, "back_to_menu"),
        "back_to_menu",
    )]);

    let message = message_lines.join("\n");
    let keyboard = InlineKeyboardMarkup::new(keyboard_buttons);

    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(keyboard)
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone()).await?;
    Ok(())
}

/// Handle approve request
pub async fn handle_approve_request(
    bot: Bot,
    q: &CallbackQuery,
    request_id: &str,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let admin_telegram_id = q.from.id.0 as i64;
    let lang = Language::English; // Default admin language
    let l10n = LocalizationService::new();
    let _chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    let user_repo = UserRepository::new(db.connection());
    let request_repo = UserRequestRepository::new(db.connection().clone());

    // Get admin user
    let admin = user_repo
        .get_by_telegram_id(admin_telegram_id)
        .await
        .unwrap_or(None)
        .ok_or(l10n.get(lang.clone(), "admin_not_found"))?;

    // Get full UUID from short request ID
    let request_uuid_str = get_full_request_id(request_id)
        .ok_or_else(|| l10n.get(lang.clone(), "invalid_request_id"))?;
    let request_id = Uuid::parse_str(&request_uuid_str)
        .map_err(|_| l10n.get(lang.clone(), "invalid_request_id"))?;

    // Get the request
    let request = request_repo
        .find_by_id(request_id)
        .await
        .unwrap_or(None)
        .ok_or(l10n.get(lang.clone(), "request_not_found"))?;

    // Check if request is already processed
    if request.status != "pending" {
        bot.answer_callback_query(q.id.clone())
            .text("This request has already been processed")
            .await?;
        return Ok(());
    }

    // Create user account
    let username = request.telegram_username.as_deref().unwrap_or("Unknown");
    let dto = crate::database::entities::user::CreateUserDto {
        name: request.get_full_name(),
        comment: Some(format!("Telegram user: @{}", username)),
        telegram_id: Some(request.telegram_id),
        is_telegram_admin: false,
    };

    match user_repo.create(dto).await {
        Ok(_new_user) => {
            // Approve the request
            request_repo
                .approve(
                    request_id,
                    Some(format!("Approved by {}", admin.name)),
                    admin.id,
                )
                .await?;

            // Update the callback message to show approval status and server selection
            if let Some(message) = &q.message {
                if let teloxide::types::MaybeInaccessibleMessage::Regular(msg) = message {
                    if let Some(text) = msg.text() {
                        let updated_text = format!(
                            "{}\n\n✅ <b>APPROVED</b> by {}\n\n📋 Select servers to grant access:",
                            text, admin.name
                        );
                        // Generate short ID for the request
                        let short_request_id = generate_short_request_id(&request_id.to_string());
                        let callback_data = format!("s:{}", short_request_id);
                        tracing::info!(
                            "Generated callback data for server selection: '{}' (length: {})",
                            callback_data,
                            callback_data.len()
                        );

                        let server_selection_keyboard = InlineKeyboardMarkup::new(vec![
                            vec![InlineKeyboardButton::callback(
                                "Select Servers",
                                callback_data,
                            )],
                            vec![InlineKeyboardButton::callback(
                                "All Requests",
                                "back_to_requests",
                            )],
                        ]);

                        let _ = bot
                            .edit_message_text(msg.chat.id, msg.id, updated_text)
                            .parse_mode(teloxide::types::ParseMode::Html)
                            .reply_markup(server_selection_keyboard)
                            .await;
                    }
                }
            }

            // Send main menu to the user instead of just notification
            let _user_lang = Language::from_telegram_code(Some(&request.get_language()));
            let user_repo_for_user = UserRepository::new(db.connection());
            let _is_admin = false; // New users are not admins by default

            // Create a fake user object for language detection
            let fake_user = teloxide::types::User {
                id: teloxide::types::UserId(request.telegram_id as u64),
                is_bot: false,
                first_name: request.telegram_first_name.clone().unwrap_or_default(),
                last_name: request.telegram_last_name.clone(),
                username: request.telegram_username.clone(),
                language_code: Some(request.get_language()),
                is_premium: false,
                added_to_attachment_menu: false,
            };

            // Send main menu using handle_start
            handle_start(
                bot.clone(),
                ChatId(request.telegram_id),
                request.telegram_id,
                &fake_user,
                &user_repo_for_user,
                db,
            )
            .await?;

            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "request_approved_admin"))
                .await?;
        }
        Err(e) => {
            tracing::error!("Failed to create user during approval: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.format(
                    lang.clone(),
                    "user_creation_failed",
                    &[("error", &e.to_string())],
                ))
                .await?;
        }
    }

    Ok(())
}

/// Handle decline request
pub async fn handle_decline_request(
    bot: Bot,
    q: &CallbackQuery,
    request_id: &str,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let admin_telegram_id = q.from.id.0 as i64;
    let lang = Language::English; // Default admin language
    let l10n = LocalizationService::new();

    let user_repo = UserRepository::new(db.connection());
    let request_repo = UserRequestRepository::new(db.connection().clone());

    // Get admin user
    let admin = user_repo
        .get_by_telegram_id(admin_telegram_id)
        .await
        .unwrap_or(None)
        .ok_or(l10n.get(lang.clone(), "admin_not_found"))?;

    // Get full UUID from short request ID
    let request_uuid_str = get_full_request_id(request_id)
        .ok_or_else(|| l10n.get(lang.clone(), "invalid_request_id"))?;
    let request_id = Uuid::parse_str(&request_uuid_str)
        .map_err(|_| l10n.get(lang.clone(), "invalid_request_id"))?;

    // Get the request
    let request = request_repo
        .find_by_id(request_id)
        .await
        .unwrap_or(None)
        .ok_or(l10n.get(lang.clone(), "request_not_found"))?;

    // Check if request is already processed
    if request.status != "pending" {
        bot.answer_callback_query(q.id.clone())
            .text("This request has already been processed")
            .await?;
        return Ok(());
    }

    // Decline the request
    request_repo
        .decline(
            request_id,
            Some(format!("Declined by {}", admin.name)),
            admin.id,
        )
        .await?;

    // Update the callback message to show decline status
    if let Some(message) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(msg) = message {
            if let Some(text) = msg.text() {
                let updated_text = format!("{}\n\n❌ <b>DECLINED</b> by {}", text, admin.name);
                let back_keyboard =
                    InlineKeyboardMarkup::new(vec![vec![InlineKeyboardButton::callback(
                        "📋 All Requests",
                        "back_to_requests",
                    )]]);

                let _ = bot
                    .edit_message_text(msg.chat.id, msg.id, updated_text)
                    .parse_mode(teloxide::types::ParseMode::Html)
                    .reply_markup(back_keyboard)
                    .await;
            }
        }
    }

    // Notify the user using their saved language preference
    let user_lang = Language::from_telegram_code(Some(&request.get_language()));
    let user_message = l10n.get(user_lang, "request_declined_notification");

    bot.send_message(ChatId(request.telegram_id), user_message)
        .parse_mode(teloxide::types::ParseMode::Html)
        .await?;

    bot.answer_callback_query(q.id.clone())
        .text(l10n.get(lang, "request_declined_admin"))
        .await?;

    Ok(())
}

/// Handle view request details
pub async fn handle_view_request(
    bot: Bot,
    q: &CallbackQuery,
    request_id: &str,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let lang = Language::English; // Default admin language
    let l10n = LocalizationService::new();
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    let request_repo = UserRequestRepository::new(db.connection().clone());
    let user_repo = UserRepository::new(db.connection());

    // Get full UUID from short request ID
    let request_uuid_str = get_full_request_id(request_id)
        .ok_or_else(|| l10n.get(lang.clone(), "invalid_request_id"))?;
    let request_id = Uuid::parse_str(&request_uuid_str)
        .map_err(|_| l10n.get(lang.clone(), "invalid_request_id"))?;

    // Get the request
    let request = request_repo
        .find_by_id(request_id)
        .await
        .unwrap_or(None)
        .ok_or(l10n.get(lang.clone(), "request_not_found"))?;

    // Get processed by admin info
    let processed_by = if let Some(processed_by_id) = request.processed_by_user_id {
        if let Ok(Some(admin)) = user_repo.get_by_id(processed_by_id).await {
            format!("\n👤 Processed by: {}", admin.name)
        } else {
            String::new()
        }
    } else {
        String::new()
    };

    let processed_at = if let Some(processed_at) = request.processed_at {
        format!(
            "\n⏰ Processed at: {}",
            processed_at.format("%Y-%m-%d %H:%M UTC")
        )
    } else {
        String::new()
    };

    let status_emoji = match request.status.as_str() {
        "pending" => "⏳",
        "approved" => "✅",
        "declined" => "❌",
        _ => "❓",
    };

    let message = format!(
        "📋 <b>Access Request Details</b>\n\n\
        👤 Name: {}\n\
        🆔 Telegram: {}\n\
        🌍 Language: {}\n\
        📅 Requested: {}\n\
        {} Status: <b>{}</b>{}{}\n\n\
        💬 Message: {}",
        request.get_full_name(),
        request.get_telegram_link(),
        request.get_language().to_uppercase(),
        request.created_at.format("%Y-%m-%d %H:%M UTC"),
        status_emoji,
        request.status.to_uppercase(),
        processed_by,
        processed_at,
        request.request_message.as_deref().unwrap_or("No message")
    );

    // Create keyboard based on request status
    let keyboard = if request.status == "pending" {
        InlineKeyboardMarkup::new(vec![
            vec![
                InlineKeyboardButton::callback(
                    l10n.get(lang.clone(), "approve"),
                    format!("approve:{}", request.id),
                ),
                InlineKeyboardButton::callback(
                    l10n.get(lang.clone(), "decline"),
                    format!("decline:{}", request.id),
                ),
            ],
            vec![
                InlineKeyboardButton::callback(l10n.get(lang.clone(), "back"), "back_to_requests"),
                InlineKeyboardButton::callback("🏠 Menu", "back"),
            ],
        ])
    } else {
        InlineKeyboardMarkup::new(vec![vec![
            InlineKeyboardButton::callback(l10n.get(lang.clone(), "back"), "back_to_requests"),
            InlineKeyboardButton::callback("🏠 Menu", "back"),
        ]])
    };

    // Edit the existing message instead of sending a new one
    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(keyboard)
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone()).await?;

    Ok(())
}

/// Handle /stats command (admin only)
pub async fn handle_stats(
    bot: Bot,
    chat_id: ChatId,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let lang = Language::English; // Default admin language
    let l10n = LocalizationService::new();

    let user_repo = UserRepository::new(db.connection());
    let server_repo = crate::database::repository::ServerRepository::new(db.connection());
    let inbound_repo = crate::database::repository::ServerInboundRepository::new(db.connection());
    let request_repo = UserRequestRepository::new(db.connection().clone());

    let user_count = user_repo.count().await.unwrap_or(0);
    let server_count = server_repo.count().await.unwrap_or(0);
    let inbound_count = inbound_repo.count().await.unwrap_or(0);
    let pending_requests = request_repo
        .count_by_status(RequestStatus::Pending)
        .await
        .unwrap_or(0);

    let message = l10n.format(
        lang,
        "statistics",
        &[
            ("users", &user_count.to_string()),
            ("servers", &server_count.to_string()),
            ("inbounds", &inbound_count.to_string()),
            ("pending", &pending_requests.to_string()),
        ],
    );

    bot.send_message(chat_id, message)
        .parse_mode(teloxide::types::ParseMode::Html)
        .await?;

    Ok(())
}

/// Handle /broadcast command (admin only)
pub async fn handle_broadcast(
    bot: Bot,
    chat_id: ChatId,
    message: String,
    user_repo: &UserRepository,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let users = user_repo.get_all(1, 1000).await.unwrap_or_default();
    let mut sent_count = 0;
    let mut failed_count = 0;

    for user in users {
        if let Some(telegram_id) = user.telegram_id {
            match bot.send_message(ChatId(telegram_id), &message).await {
                Ok(_) => sent_count += 1,
                Err(_) => failed_count += 1,
            }
        }
    }

    let lang = Language::English; // Default admin language
    let l10n = LocalizationService::new();

    let result_message = l10n.format(
        lang,
        "broadcast_complete",
        &[
            ("sent", &sent_count.to_string()),
            ("failed", &failed_count.to_string()),
        ],
    );

    bot.send_message(chat_id, result_message).await?;

    Ok(())
}

/// Handle server selection after approval
pub async fn handle_select_server_access(
    bot: Bot,
    q: &CallbackQuery,
    short_request_id: &str,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let _lang = Language::English; // Default admin language
    let _l10n = LocalizationService::new();
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    let server_repo = crate::database::repository::ServerRepository::new(db.connection());

    // Get all active servers
    let servers = server_repo.find_all().await.unwrap_or_default();

    if servers.is_empty() {
        bot.answer_callback_query(q.id.clone())
            .text("No servers available")
            .await?;
        return Ok(());
    }

    // Get the full request ID from the short ID
    let request_id = get_full_request_id(short_request_id).ok_or("Invalid request ID")?;

    tracing::info!(
        "Handling server selection for request: {} (short: {})",
        request_id,
        short_request_id
    );

    // Initialize selected servers for this request (empty initially)
    {
        let mut selected = get_selected_servers().lock().unwrap();
        selected.insert(request_id.clone(), Vec::new());
    }

    // Build keyboard with server toggle buttons
    let mut keyboard_buttons = vec![];
    let selected_servers = {
        let selected = get_selected_servers().lock().unwrap();
        selected.get(&request_id).cloned().unwrap_or_default()
    };

    for server in &servers {
        let is_selected = selected_servers.contains(&server.id.to_string());
        let button_text = if is_selected {
            format!("✅ {}", server.name)
        } else {
            format!("⬜ {}", server.name)
        };

        let short_server_id = generate_short_server_id(&server.id.to_string());
        let callback_data = format!("t:{}:{}", short_request_id, short_server_id);
        tracing::debug!(
            "Toggle button callback: '{}' (length: {})",
            callback_data,
            callback_data.len()
        );

        keyboard_buttons.push(vec![InlineKeyboardButton::callback(
            button_text,
            callback_data,
        )]);
    }

    // Add apply and back buttons
    keyboard_buttons.push(vec![
        InlineKeyboardButton::callback("✅ Apply Selected", format!("a:{}", short_request_id)),
        InlineKeyboardButton::callback("🔙 Back", "back_to_requests"),
    ]);

    let message = format!("🖥️ <b>Select Servers for Access</b>\n\nChoose which servers to grant access to the approved user:");

    // Edit the existing message
    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(InlineKeyboardMarkup::new(keyboard_buttons))
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone()).await?;
    Ok(())
}

/// Handle toggling server selection
pub async fn handle_toggle_server(
    bot: Bot,
    q: &CallbackQuery,
    short_request_id: &str,
    short_server_id: &str,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    // Get the full IDs from the short IDs
    let request_id = get_full_request_id(short_request_id).ok_or("Invalid request ID")?;
    let server_id = get_full_server_id(short_server_id).ok_or("Invalid server ID")?;

    tracing::info!("Toggling server {} for request {}", server_id, request_id);

    // Toggle server selection
    {
        let mut selected = get_selected_servers().lock().unwrap();
        let server_list = selected.entry(request_id.clone()).or_insert_with(Vec::new);

        if let Some(pos) = server_list.iter().position(|x| x == &server_id) {
            server_list.remove(pos);
        } else {
            server_list.push(server_id.clone());
        }
    }

    // Rebuild the keyboard with updated selection
    let server_repo = crate::database::repository::ServerRepository::new(db.connection());
    let servers = server_repo.find_all().await.unwrap_or_default();

    let mut keyboard_buttons = vec![];
    let selected_servers = {
        let selected = get_selected_servers().lock().unwrap();
        selected.get(&request_id).cloned().unwrap_or_default()
    };

    for server in &servers {
        let is_selected = selected_servers.contains(&server.id.to_string());
        let button_text = if is_selected {
            format!("✅ {}", server.name)
        } else {
            format!("⬜ {}", server.name)
        };

        let short_server_id = generate_short_server_id(&server.id.to_string());
        let callback_data = format!("t:{}:{}", short_request_id, short_server_id);

        keyboard_buttons.push(vec![InlineKeyboardButton::callback(
            button_text,
            callback_data,
        )]);
    }

    // Add apply and back buttons
    keyboard_buttons.push(vec![
        InlineKeyboardButton::callback("✅ Apply Selected", format!("a:{}", short_request_id)),
        InlineKeyboardButton::callback("🔙 Back", "back_to_requests"),
    ]);

    let selected_count = selected_servers.len();
    let message = format!("🖥️ <b>Select Servers for Access</b>\n\nChoose which servers to grant access to the approved user:\n\n📊 Selected: {} server{}", 
        selected_count, if selected_count == 1 { "" } else { "s" });

    // Edit the existing message
    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(InlineKeyboardMarkup::new(keyboard_buttons))
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone()).await?;
    Ok(())
}

/// Handle applying server access
pub async fn handle_apply_server_access(
    bot: Bot,
    q: &CallbackQuery,
    short_request_id: &str,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let _lang = Language::English; // Default admin language
    let _l10n = LocalizationService::new();
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    // Get the full request ID from the short ID
    let request_id = get_full_request_id(short_request_id).ok_or("Invalid request ID")?;

    // Get selected servers
    let selected_server_ids = {
        let selected = get_selected_servers().lock().unwrap();
        selected.get(&request_id).cloned().unwrap_or_default()
    };

    if selected_server_ids.is_empty() {
        bot.answer_callback_query(q.id.clone())
            .text("No servers selected")
            .await?;
        return Ok(());
    }

    let request_repo = UserRequestRepository::new(db.connection().clone());
    let user_repo = UserRepository::new(db.connection());
    let server_repo = crate::database::repository::ServerRepository::new(db.connection());
    let inbound_repo =
        crate::database::repository::ServerInboundRepository::new(db.connection().clone());
    let inbound_users_repo =
        crate::database::repository::InboundUsersRepository::new(db.connection().clone());

    // Parse request ID and get request
    let request_uuid = Uuid::parse_str(&request_id).map_err(|_| "Invalid request ID")?;
    let request = request_repo
        .find_by_id(request_uuid)
        .await
        .unwrap_or(None)
        .ok_or("Request not found")?;

    // Get user
    let user = user_repo
        .get_by_telegram_id(request.telegram_id)
        .await
        .unwrap_or(None)
        .ok_or("User not found")?;

    let mut granted_servers = Vec::new();
    let mut total_inbounds = 0;

    // Grant access to all inbounds on selected servers
    for server_id_str in &selected_server_ids {
        if let Ok(server_id) = Uuid::parse_str(server_id_str) {
            // Get server info
            if let Ok(Some(server)) = server_repo.find_by_id(server_id).await {
                granted_servers.push(server.name.clone());

                // Get all inbounds for this server
                if let Ok(inbounds) = inbound_repo.find_by_server_id(server_id).await {
                    for inbound in inbounds {
                        // Check if user already has access to this inbound
                        if !inbound_users_repo
                            .user_has_access_to_inbound(user.id, inbound.id)
                            .await
                            .unwrap_or(false)
                        {
                            // Create inbound user access
                            let dto =
                                crate::database::entities::inbound_users::CreateInboundUserDto {
                                    user_id: user.id,
                                    server_inbound_id: inbound.id,
                                    level: Some(0),
                                };

                            if let Ok(_) = inbound_users_repo.create(dto).await {
                                total_inbounds += 1;
                            }
                        }
                    }
                }
            }
        }
    }

    // Clean up selected servers storage
    {
        let mut selected = get_selected_servers().lock().unwrap();
        selected.remove(&request_id);
    }

    // Update message with success
    let message = format!(
        "✅ <b>Server Access Granted</b>\n\nUser: {}\nServers: {}\nTotal inbounds: {}\n\n✅ Access has been successfully granted!",
        user.name,
        granted_servers.join(", "),
        total_inbounds
    );

    let back_keyboard = InlineKeyboardMarkup::new(vec![vec![InlineKeyboardButton::callback(
        "📋 All Requests",
        "back_to_requests",
    )]]);

    // Edit the existing message
    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(back_keyboard)
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone())
        .text(format!(
            "Access granted to {} servers",
            granted_servers.len()
        ))
        .await?;

    Ok(())
}

/// Handle manage users button
pub async fn handle_manage_users(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // Redirect to first page of user list
    handle_user_list(bot, q, db, 1).await
}

/// Handle user list with pagination
pub async fn handle_user_list(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
    page: u32,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    let user_repo = UserRepository::new(db.connection());
    let per_page = 20;
    let offset = (page - 1) * per_page;

    // Get total user count
    let total_users = match user_repo.count_all().await {
        Ok(count) => count,
        Err(e) => {
            tracing::error!("Failed to count users: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "error_occurred"))
                .await?;
            return Ok(());
        }
    };

    if total_users == 0 {
        let message = l10n.get(lang.clone(), "no_users_found");
        let keyboard = InlineKeyboardMarkup::new(vec![vec![InlineKeyboardButton::callback(
            l10n.get(lang, "back_to_menu"),
            "back_to_menu",
        )]]);

        if let Some(msg) = &q.message {
            if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
                bot.edit_message_text(chat_id, regular_msg.id, message)
                    .reply_markup(keyboard)
                    .await?;
            }
        }

        bot.answer_callback_query(q.id.clone()).await?;
        return Ok(());
    }

    // Get users for current page
    let users = match user_repo
        .find_paginated(offset as u64, per_page as u64)
        .await
    {
        Ok(users) => users,
        Err(e) => {
            tracing::error!("Failed to get users: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "error_occurred"))
                .await?;
            return Ok(());
        }
    };

    let total_pages = (total_users + per_page as i64 - 1) / per_page as i64;

    // Build message
    let mut message_lines = vec![l10n.get(lang.clone(), "user_list")];
    message_lines.push(format!(
        "\n{}",
        l10n.format(
            lang.clone(),
            "page_info",
            &[
                ("page", &page.to_string()),
                ("total", &total_pages.to_string())
            ]
        )
    ));
    message_lines.push("".to_string());

    // Build user buttons
    let mut keyboard_buttons = Vec::new();

    for user in &users {
        let user_display = if let Some(telegram_id) = user.telegram_id {
            format!("👤 {} (@{})", user.name, telegram_id)
        } else {
            format!("👤 {}", user.name)
        };

        let short_user_id = generate_short_user_id(&user.id.to_string());
        keyboard_buttons.push(vec![InlineKeyboardButton::callback(
            user_display,
            format!("user_details:{}", short_user_id),
        )]);
    }

    // Add pagination buttons
    let mut pagination_row = Vec::new();

    if page > 1 {
        pagination_row.push(InlineKeyboardButton::callback(
            l10n.get(lang.clone(), "prev_page"),
            format!("user_list:{}", page - 1),
        ));
    }

    if page < total_pages as u32 {
        pagination_row.push(InlineKeyboardButton::callback(
            l10n.get(lang.clone(), "next_page"),
            format!("user_list:{}", page + 1),
        ));
    }

    if !pagination_row.is_empty() {
        keyboard_buttons.push(pagination_row);
    }

    // Add back button
    keyboard_buttons.push(vec![InlineKeyboardButton::callback(
        l10n.get(lang, "back_to_menu"),
        "back_to_menu",
    )]);

    let message = message_lines.join("\n");
    let keyboard = InlineKeyboardMarkup::new(keyboard_buttons);

    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(keyboard)
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone()).await?;
    Ok(())
}

/// Handle user details view
pub async fn handle_user_details(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
    user_id_str: &str,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    let user_id = match Uuid::parse_str(user_id_str) {
        Ok(id) => id,
        Err(_) => {
            bot.answer_callback_query(q.id.clone())
                .text("Invalid user ID")
                .await?;
            return Ok(());
        }
    };

    let user_repo = UserRepository::new(db.connection());
    let inbound_users_repo =
        crate::database::repository::InboundUsersRepository::new(db.connection().clone());

    // Get user info
    let user = match user_repo.get_by_id(user_id).await {
        Ok(Some(user)) => user,
        Ok(None) => {
            bot.answer_callback_query(q.id.clone())
                .text("User not found")
                .await?;
            return Ok(());
        }
        Err(e) => {
            tracing::error!("Failed to get user: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "error_occurred"))
                .await?;
            return Ok(());
        }
    };

    // Get user's active inbound accesses
    let inbound_users = inbound_users_repo
        .find_by_user_id(user_id)
        .await
        .unwrap_or_default();
    let active_inbounds = inbound_users.iter().filter(|iu| iu.is_active).count();

    // Build user info message
    let mut message_lines = vec![l10n.get(lang.clone(), "user_details")];
    message_lines.push("".to_string());
    message_lines.push(format!("👤 <b>Name:</b> {}", user.name));
    message_lines.push(format!("🆔 <b>ID:</b> <code>{}</code>", user.id));

    if let Some(telegram_id) = user.telegram_id {
        message_lines.push(format!("📱 <b>Telegram:</b> @{}", telegram_id));
    }

    message_lines.push(format!("📊 <b>Active Accesses:</b> {}", active_inbounds));
    message_lines.push(format!(
        "🛡️ <b>Admin:</b> {}",
        if user.is_telegram_admin { "Yes" } else { "No" }
    ));
    message_lines.push(format!(
        "📅 <b>Created:</b> {}",
        user.created_at.format("%Y-%m-%d %H:%M UTC")
    ));

    // Build keyboard
    let short_user_id = generate_short_user_id(&user_id.to_string());
    let keyboard_buttons = vec![
        vec![InlineKeyboardButton::callback(
            l10n.get(lang.clone(), "manage_access"),
            format!("user_manage:{}", short_user_id),
        )],
        vec![InlineKeyboardButton::callback(
            l10n.get(lang.clone(), "back_to_users"),
            "user_list:1",
        )],
        vec![InlineKeyboardButton::callback(
            l10n.get(lang, "back_to_menu"),
            "back_to_menu",
        )],
    ];

    let message = message_lines.join("\n");
    let keyboard = InlineKeyboardMarkup::new(keyboard_buttons);

    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(keyboard)
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone()).await?;
    Ok(())
}

/// Handle user access management
pub async fn handle_user_manage_access(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
    user_id_str: &str,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    let user_id = match Uuid::parse_str(user_id_str) {
        Ok(id) => id,
        Err(_) => {
            bot.answer_callback_query(q.id.clone())
                .text("Invalid user ID")
                .await?;
            return Ok(());
        }
    };

    let user_repo = UserRepository::new(db.connection());
    let server_repo = crate::database::repository::ServerRepository::new(db.connection().clone());
    let inbound_users_repo =
        crate::database::repository::InboundUsersRepository::new(db.connection().clone());

    // Get user info
    let user = match user_repo.get_by_id(user_id).await {
        Ok(Some(user)) => user,
        Ok(None) => {
            bot.answer_callback_query(q.id.clone())
                .text("User not found")
                .await?;
            return Ok(());
        }
        Err(e) => {
            tracing::error!("Failed to get user: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "error_occurred"))
                .await?;
            return Ok(());
        }
    };

    // Get all servers
    let all_servers = match server_repo.find_all().await {
        Ok(servers) => servers,
        Err(e) => {
            tracing::error!("Failed to get servers: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "error_occurred"))
                .await?;
            return Ok(());
        }
    };

    // Filter servers that have active inbounds
    let mut servers_with_inbounds = Vec::new();
    let inbound_repo =
        crate::database::repository::ServerInboundRepository::new(db.connection().clone());

    for server in all_servers {
        match inbound_repo.find_by_server_id(server.id).await {
            Ok(inbounds) => {
                if !inbounds.is_empty() {
                    servers_with_inbounds.push(server);
                }
            }
            Err(e) => {
                tracing::warn!("Failed to get inbounds for server {}: {}", server.name, e);
            }
        }
    }

    if servers_with_inbounds.is_empty() {
        let message = "No servers with inbounds available";
        let keyboard = InlineKeyboardMarkup::new(vec![vec![InlineKeyboardButton::callback(
            l10n.get(lang, "back_to_users"),
            format!("user_details:{}", user_id),
        )]]);

        if let Some(msg) = &q.message {
            if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
                bot.edit_message_text(chat_id, regular_msg.id, message)
                    .reply_markup(keyboard)
                    .await?;
            }
        }

        bot.answer_callback_query(q.id.clone()).await?;
        return Ok(());
    }

    // Get user's current accesses
    let user_inbounds = inbound_users_repo
        .find_by_user_id(user_id)
        .await
        .unwrap_or_default();
    let mut user_server_ids = std::collections::HashSet::new();

    for inbound_user in &user_inbounds {
        if inbound_user.is_active {
            // Get server ID for this inbound
            if let Ok(Some(inbound)) =
                crate::database::repository::ServerInboundRepository::new(db.connection().clone())
                    .find_by_id(inbound_user.server_inbound_id)
                    .await
            {
                user_server_ids.insert(inbound.server_id);
            }
        }
    }

    // Initialize or get selected servers for this user
    let selected_servers = get_user_selected_servers(&user_id.to_string());

    // Build message
    let mut message_lines = vec![
        format!("🔧 <b>Manage Access for {}</b>", user.name),
        "".to_string(),
        "Select servers to grant or revoke access:".to_string(),
        "".to_string(),
    ];

    // Build server buttons
    let mut keyboard_buttons = Vec::new();
    let short_user_id = generate_short_user_id(&user_id.to_string());

    for server in &servers_with_inbounds {
        let has_access = user_server_ids.contains(&server.id);
        let is_selected = selected_servers.contains(&server.id.to_string());

        let (emoji, action) = if has_access {
            if is_selected {
                ("❌", "Remove") // Selected for removal
            } else {
                ("✅", "Keep") // Current access, not selected for removal
            }
        } else {
            if is_selected {
                ("✅", "Grant") // Selected for granting
            } else {
                ("⚪", "Grant") // No access, not selected
            }
        };

        message_lines.push(format!("{} {} - {}", emoji, server.name, action));

        let short_server_id = generate_short_server_id(&server.id.to_string());
        keyboard_buttons.push(vec![InlineKeyboardButton::callback(
            format!("{} {}", emoji, server.name),
            format!("user_toggle:{}:{}", short_user_id, short_server_id),
        )]);
    }

    // Add apply and back buttons
    keyboard_buttons.push(vec![InlineKeyboardButton::callback(
        l10n.get(lang.clone(), "grant_access"),
        format!("user_apply:{}", short_user_id),
    )]);

    keyboard_buttons.push(vec![InlineKeyboardButton::callback(
        l10n.get(lang.clone(), "back_to_users"),
        format!("user_details:{}", short_user_id),
    )]);

    let message = message_lines.join("\n");
    let keyboard = InlineKeyboardMarkup::new(keyboard_buttons);

    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(keyboard)
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone()).await?;
    Ok(())
}

/// Handle user server toggle
pub async fn handle_user_toggle_server(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
    user_id_str: &str,
    server_id_str: &str,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let user_id = match Uuid::parse_str(user_id_str) {
        Ok(id) => id,
        Err(_) => {
            bot.answer_callback_query(q.id.clone())
                .text("Invalid user ID")
                .await?;
            return Ok(());
        }
    };

    let server_id = match Uuid::parse_str(server_id_str) {
        Ok(id) => id,
        Err(_) => {
            bot.answer_callback_query(q.id.clone())
                .text("Invalid server ID")
                .await?;
            return Ok(());
        }
    };

    // Toggle server selection
    toggle_user_server_selection(&user_id.to_string(), &server_id.to_string());

    // Refresh the access management view
    handle_user_manage_access(bot, q, db, user_id_str).await
}

/// Handle apply user access changes
pub async fn handle_user_apply_access(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
    user_id_str: &str,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    let chat_id = q
        .message
        .as_ref()
        .and_then(|m| match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        })
        .ok_or("No chat ID")?;

    let user_id = match Uuid::parse_str(user_id_str) {
        Ok(id) => id,
        Err(_) => {
            bot.answer_callback_query(q.id.clone())
                .text("Invalid user ID")
                .await?;
            return Ok(());
        }
    };

    let user_repo = UserRepository::new(db.connection());
    let server_repo = crate::database::repository::ServerRepository::new(db.connection().clone());
    let inbound_repo =
        crate::database::repository::ServerInboundRepository::new(db.connection().clone());
    let inbound_users_repo =
        crate::database::repository::InboundUsersRepository::new(db.connection().clone());

    // Get user info
    let user = match user_repo.get_by_id(user_id).await {
        Ok(Some(user)) => user,
        Ok(None) => {
            bot.answer_callback_query(q.id.clone())
                .text("User not found")
                .await?;
            return Ok(());
        }
        Err(e) => {
            tracing::error!("Failed to get user: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "error_occurred"))
                .await?;
            return Ok(());
        }
    };

    // Get selected servers
    let selected_server_ids = get_user_selected_servers(&user_id.to_string());

    if selected_server_ids.is_empty() {
        bot.answer_callback_query(q.id.clone())
            .text("No servers selected")
            .await?;
        return Ok(());
    }

    // Get user's current server accesses
    let user_inbounds = inbound_users_repo
        .find_by_user_id(user_id)
        .await
        .unwrap_or_default();
    let mut current_server_ids = std::collections::HashSet::new();

    for inbound_user in &user_inbounds {
        if inbound_user.is_active {
            if let Ok(Some(inbound)) = inbound_repo
                .find_by_id(inbound_user.server_inbound_id)
                .await
            {
                current_server_ids.insert(inbound.server_id.to_string());
            }
        }
    }

    let mut granted_servers = Vec::new();
    let mut removed_servers = Vec::new();
    let mut total_changes = 0;

    for server_id_str in &selected_server_ids {
        if let Ok(server_id) = Uuid::parse_str(server_id_str) {
            let has_access = current_server_ids.contains(server_id_str);

            if has_access {
                // Remove access - deactivate all inbounds for this server
                for inbound_user in &user_inbounds {
                    if let Ok(Some(inbound)) = inbound_repo
                        .find_by_id(inbound_user.server_inbound_id)
                        .await
                    {
                        if inbound.server_id == server_id && inbound_user.is_active {
                            if let Ok(_) = inbound_users_repo.disable(inbound_user.id).await {
                                total_changes += 1;
                            }
                        }
                    }
                }

                if let Ok(Some(server)) = server_repo.find_by_id(server_id).await {
                    removed_servers.push(server.name);
                }
            } else {
                // Grant access - add to all inbounds for this server
                if let Ok(inbounds) = inbound_repo.find_by_server_id(server_id).await {
                    for inbound in inbounds {
                        // Check if user already has access to this inbound
                        if !inbound_users_repo
                            .user_has_access_to_inbound(user_id, inbound.id)
                            .await
                            .unwrap_or(false)
                        {
                            let dto =
                                crate::database::entities::inbound_users::CreateInboundUserDto {
                                    user_id,
                                    server_inbound_id: inbound.id,
                                    level: Some(0),
                                };

                            if let Ok(_) = inbound_users_repo.create(dto).await {
                                total_changes += 1;
                            }
                        }
                    }
                }

                if let Ok(Some(server)) = server_repo.find_by_id(server_id).await {
                    granted_servers.push(server.name);
                }
            }
        }
    }

    // Clear selected servers
    clear_user_selected_servers(&user_id.to_string());

    // Build result message
    let mut message_lines = vec![
        format!("✅ <b>Access Updated for {}</b>", user.name),
        "".to_string(),
    ];

    if !granted_servers.is_empty() {
        message_lines.push(format!(
            "✅ <b>Granted access to:</b> {}",
            granted_servers.join(", ")
        ));
    }

    if !removed_servers.is_empty() {
        message_lines.push(format!(
            "❌ <b>Removed access from:</b> {}",
            removed_servers.join(", ")
        ));
    }

    message_lines.push("".to_string());
    message_lines.push(format!("📊 <b>Total changes:</b> {}", total_changes));

    let short_user_id = generate_short_user_id(&user_id.to_string());
    let keyboard = InlineKeyboardMarkup::new(vec![
        vec![InlineKeyboardButton::callback(
            l10n.get(lang.clone(), "back_to_users"),
            format!("user_details:{}", short_user_id),
        )],
        vec![InlineKeyboardButton::callback(
            l10n.get(lang.clone(), "back_to_menu"),
            "back_to_menu",
        )],
    ]);

    let message = message_lines.join("\n");

    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, message)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(keyboard)
                .await?;
        }
    }

    bot.answer_callback_query(q.id.clone())
        .text(l10n.get(lang.clone(), "access_updated"))
        .await?;

    Ok(())
}

// Global storage for user selected servers for access management
static USER_SELECTED_SERVERS: OnceLock<Arc<Mutex<HashMap<String, Vec<String>>>>> = OnceLock::new();

fn get_user_selected_servers_storage() -> &'static Arc<Mutex<HashMap<String, Vec<String>>>> {
    USER_SELECTED_SERVERS.get_or_init(|| Arc::new(Mutex::new(HashMap::new())))
}

fn get_user_selected_servers(user_id: &str) -> Vec<String> {
    let storage = get_user_selected_servers_storage().lock().unwrap();
    storage.get(user_id).cloned().unwrap_or_default()
}

fn toggle_user_server_selection(user_id: &str, server_id: &str) {
    let mut storage = get_user_selected_servers_storage().lock().unwrap();
    let servers = storage.entry(user_id.to_string()).or_insert_with(Vec::new);

    if let Some(pos) = servers.iter().position(|id| id == server_id) {
        servers.remove(pos);
    } else {
        servers.push(server_id.to_string());
    }
}

fn clear_user_selected_servers(user_id: &str) {
    let mut storage = get_user_selected_servers_storage().lock().unwrap();
    storage.remove(user_id);
}
