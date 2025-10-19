use teloxide::{prelude::*, types::{InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery}};
use uuid::Uuid;

use crate::database::DatabaseManager;
use crate::database::repository::{UserRepository, UserRequestRepository};
use crate::database::entities::user_request::RequestStatus;
use super::super::localization::{LocalizationService, Language};
use super::types::{get_selected_servers, generate_short_request_id, get_full_request_id, generate_short_server_id, get_full_server_id};
use super::user::handle_start;

/// Handle admin requests edit (show list of recent requests)
pub async fn handle_admin_requests_edit(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let admin_telegram_id = q.from.id.0 as i64;
    let lang = Language::English; // Default admin language
    let l10n = LocalizationService::new();
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;
    
    let user_repo = UserRepository::new(db.connection());
    let request_repo = UserRequestRepository::new(db.connection().clone());
    
    // Check if user is admin
    if !user_repo.is_telegram_id_admin(admin_telegram_id).await.unwrap_or(false) {
        bot.answer_callback_query(q.id.clone())
            .text(l10n.get(lang, "unauthorized"))
            .await?;
        return Ok(());
    }
    
    // Get recent requests (last 10)
    let recent_requests = request_repo.find_recent(10).await.unwrap_or_default();
    
    if recent_requests.is_empty() {
        // Edit message to show no requests
        if let Some(msg) = &q.message {
            if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
                bot.edit_message_text(chat_id, regular_msg.id, l10n.get(lang.clone(), "no_pending_requests"))
                    .reply_markup(InlineKeyboardMarkup::new(vec![
                        vec![InlineKeyboardButton::callback(l10n.get(lang, "back"), "back")],
                    ]))
                    .await?;
            }
        }
        bot.answer_callback_query(q.id.clone()).await?;
        return Ok(());
    }
    
    // Build message with request list
    let mut message_lines = vec!["📋 <b>Recent Access Requests</b>\n".to_string()];
    let mut keyboard_buttons = vec![];
    
    for request in &recent_requests {
        let status_emoji = match request.status.as_str() {
            "pending" => "⏳",
            "approved" => "✅",
            "declined" => "❌",
            _ => "❓"
        };
        
        let username = request.telegram_username.as_deref().unwrap_or("unknown");
        let processed_info = if let Some(processed_by_id) = request.processed_by_user_id {
            if let Ok(Some(admin)) = user_repo.get_by_id(processed_by_id).await {
                format!(" by {}", admin.name)
            } else {
                String::new()
            }
        } else {
            String::new()
        };
        
        let button_text = format!("{} {} @{}{}", status_emoji, request.get_full_name(), username, processed_info);
        
        keyboard_buttons.push(vec![
            InlineKeyboardButton::callback(button_text, format!("view_request:{}", request.id))
        ]);
    }
    
    // Add back button
    keyboard_buttons.push(vec![
        InlineKeyboardButton::callback(l10n.get(lang, "back"), "back")
    ]);
    
    let message = message_lines.join("\n");
    
    // Edit the existing message instead of sending a new one
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
    let _chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;
    
    let user_repo = UserRepository::new(db.connection());
    let request_repo = UserRequestRepository::new(db.connection().clone());
    
    // Get admin user
    let admin = user_repo.get_by_telegram_id(admin_telegram_id).await
        .unwrap_or(None)
        .ok_or(l10n.get(lang.clone(), "admin_not_found"))?;
    
    // Parse request ID
    let request_id = Uuid::parse_str(request_id).map_err(|_| l10n.get(lang.clone(), "invalid_request_id"))?;
    
    // Get the request
    let request = request_repo.find_by_id(request_id).await
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
        Ok(new_user) => {
            // Approve the request
            request_repo.approve(
                request_id, 
                Some(format!("Approved by {}", admin.name)),
                admin.id
            ).await?;
            
            // Update the callback message to show approval status and server selection
            if let Some(message) = &q.message {
                if let teloxide::types::MaybeInaccessibleMessage::Regular(msg) = message {
                    if let Some(text) = msg.text() {
                        let updated_text = format!("{}\n\n✅ <b>APPROVED</b> by {}\n\n📋 Select servers to grant access:", text, admin.name);
                        // Generate short ID for the request
                        let short_request_id = generate_short_request_id(&request_id.to_string());
                        let callback_data = format!("s:{}", short_request_id);
                        tracing::info!("Generated callback data for server selection: '{}' (length: {})", callback_data, callback_data.len());
                        
                        let server_selection_keyboard = InlineKeyboardMarkup::new(vec![
                            vec![InlineKeyboardButton::callback("Select Servers", callback_data)],
                            vec![InlineKeyboardButton::callback("All Requests", "back_to_requests")],
                        ]);
                        
                        let _ = bot.edit_message_text(msg.chat.id, msg.id, updated_text)
                            .parse_mode(teloxide::types::ParseMode::Html)
                            .reply_markup(server_selection_keyboard)
                            .await;
                    }
                }
            }
            
            // Send main menu to the user instead of just notification
            let user_lang = Language::from_telegram_code(Some(&request.get_language()));
            let user_repo_for_user = UserRepository::new(db.connection());
            let is_admin = false; // New users are not admins by default
            
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
                db
            ).await?;
            
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "request_approved_admin"))
                .await?;
        }
        Err(e) => {
            tracing::error!("Failed to create user during approval: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.format(lang.clone(), "user_creation_failed", &[("error", &e.to_string())]))
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
    let admin = user_repo.get_by_telegram_id(admin_telegram_id).await
        .unwrap_or(None)
        .ok_or(l10n.get(lang.clone(), "admin_not_found"))?;
    
    // Parse request ID
    let request_id = Uuid::parse_str(request_id).map_err(|_| l10n.get(lang.clone(), "invalid_request_id"))?;
    
    // Get the request
    let request = request_repo.find_by_id(request_id).await
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
    request_repo.decline(
        request_id, 
        Some(format!("Declined by {}", admin.name)),
        admin.id
    ).await?;
    
    // Update the callback message to show decline status
    if let Some(message) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(msg) = message {
            if let Some(text) = msg.text() {
                let updated_text = format!("{}\n\n❌ <b>DECLINED</b> by {}", text, admin.name);
                let back_keyboard = InlineKeyboardMarkup::new(vec![
                    vec![InlineKeyboardButton::callback("📋 All Requests", "back_to_requests")],
                ]);
                
                let _ = bot.edit_message_text(msg.chat.id, msg.id, updated_text)
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
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;
    
    let request_repo = UserRequestRepository::new(db.connection().clone());
    let user_repo = UserRepository::new(db.connection());
    
    // Parse request ID
    let request_id = Uuid::parse_str(request_id).map_err(|_| l10n.get(lang.clone(), "invalid_request_id"))?;
    
    // Get the request
    let request = request_repo.find_by_id(request_id).await
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
        format!("\n⏰ Processed at: {}", processed_at.format("%Y-%m-%d %H:%M UTC"))
    } else {
        String::new()
    };
    
    let status_emoji = match request.status.as_str() {
        "pending" => "⏳",
        "approved" => "✅",
        "declined" => "❌",
        _ => "❓"
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
                InlineKeyboardButton::callback(l10n.get(lang.clone(), "approve"), format!("approve:{}", request.id)),
                InlineKeyboardButton::callback(l10n.get(lang.clone(), "decline"), format!("decline:{}", request.id)),
            ],
            vec![
                InlineKeyboardButton::callback(l10n.get(lang.clone(), "back"), "back_to_requests"),
                InlineKeyboardButton::callback("🏠 Menu", "back"),
            ],
        ])
    } else {
        InlineKeyboardMarkup::new(vec![
            vec![
                InlineKeyboardButton::callback(l10n.get(lang.clone(), "back"), "back_to_requests"),
                InlineKeyboardButton::callback("🏠 Menu", "back"),
            ],
        ])
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
    let pending_requests = request_repo.count_by_status(RequestStatus::Pending).await.unwrap_or(0);
    
    let message = l10n.format(lang, "statistics", &[
        ("users", &user_count.to_string()),
        ("servers", &server_count.to_string()),
        ("inbounds", &inbound_count.to_string()),
        ("pending", &pending_requests.to_string())
    ]);
    
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
    
    let result_message = l10n.format(lang, "broadcast_complete", &[
        ("sent", &sent_count.to_string()),
        ("failed", &failed_count.to_string())
    ]);
    
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
    let lang = Language::English; // Default admin language
    let _l10n = LocalizationService::new();
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;

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
    let request_id = get_full_request_id(short_request_id)
        .ok_or("Invalid request ID")?;
    
    tracing::info!("Handling server selection for request: {} (short: {})", request_id, short_request_id);
    
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
        tracing::debug!("Toggle button callback: '{}' (length: {})", callback_data, callback_data.len());
        
        keyboard_buttons.push(vec![
            InlineKeyboardButton::callback(button_text, callback_data)
        ]);
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
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;

    // Get the full IDs from the short IDs
    let request_id = get_full_request_id(short_request_id)
        .ok_or("Invalid request ID")?;
    let server_id = get_full_server_id(short_server_id)
        .ok_or("Invalid server ID")?;
    
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
        
        keyboard_buttons.push(vec![
            InlineKeyboardButton::callback(button_text, callback_data)
        ]);
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
    let lang = Language::English; // Default admin language
    let _l10n = LocalizationService::new();
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;

    // Get the full request ID from the short ID
    let request_id = get_full_request_id(short_request_id)
        .ok_or("Invalid request ID")?;
    
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
    let inbound_repo = crate::database::repository::ServerInboundRepository::new(db.connection().clone());
    let inbound_users_repo = crate::database::repository::InboundUsersRepository::new(db.connection().clone());

    // Parse request ID and get request
    let request_uuid = Uuid::parse_str(&request_id).map_err(|_| "Invalid request ID")?;
    let request = request_repo.find_by_id(request_uuid).await
        .unwrap_or(None)
        .ok_or("Request not found")?;

    // Get user
    let user = user_repo.get_by_telegram_id(request.telegram_id).await
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
                        if !inbound_users_repo.user_has_access_to_inbound(user.id, inbound.id).await.unwrap_or(false) {
                            // Create inbound user access
                            let dto = crate::database::entities::inbound_users::CreateInboundUserDto {
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

    let back_keyboard = InlineKeyboardMarkup::new(vec![
        vec![InlineKeyboardButton::callback("📋 All Requests", "back_to_requests")],
    ]);

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
        .text(format!("Access granted to {} servers", granted_servers.len()))
        .await?;

    Ok(())
}