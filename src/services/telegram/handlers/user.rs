use teloxide::{prelude::*, types::{InlineKeyboardButton, InlineKeyboardMarkup}};
use base64::{Engine, engine::general_purpose};

use crate::database::DatabaseManager;
use crate::database::repository::{UserRepository, UserRequestRepository};
use crate::database::entities::user_request::{CreateUserRequestDto, RequestStatus};
use super::super::localization::{LocalizationService, Language};
use super::types::{get_user_language, get_main_keyboard, get_new_user_keyboard};

/// Handle start command and main menu
pub async fn handle_start(
    bot: Bot,
    chat_id: ChatId,
    telegram_id: i64,
    from: &teloxide::types::User,
    user_repo: &UserRepository,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    handle_start_impl(bot, chat_id, telegram_id, from, user_repo, db, None, None).await
}

/// Handle start with message editing support
pub async fn handle_start_edit(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let telegram_id = from.id.0 as i64;
    let user_repo = UserRepository::new(db.connection());
    
    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            let chat_id = regular_msg.chat.id;
            handle_start_impl(
                bot.clone(), 
                chat_id, 
                telegram_id, 
                from, 
                &user_repo, 
                db, 
                Some(regular_msg.id),
                Some(q.id.clone())
            ).await?;
        }
    }
    
    Ok(())
}

/// Internal implementation of handle_start with optional message editing
async fn handle_start_impl(
    bot: Bot,
    chat_id: ChatId,
    telegram_id: i64,
    from: &teloxide::types::User,
    user_repo: &UserRepository,
    db: &DatabaseManager,
    edit_message_id: Option<teloxide::types::MessageId>,
    callback_query_id: Option<String>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    
    // Check if user exists in our database
    match user_repo.get_by_telegram_id(telegram_id).await {
        Ok(Some(user)) => {
            // Check if user is admin
            let is_admin = user_repo.is_telegram_id_admin(telegram_id).await.unwrap_or(false);
            
            // Check if user has any pending requests
            let request_repo = UserRequestRepository::new(db.connection().clone());
            
            // Check for existing requests
            if let Ok(existing_requests) = request_repo.find_by_telegram_id(telegram_id).await {
                if let Some(latest_request) = existing_requests.into_iter()
                    .filter(|r| r.status == "pending" || r.status == "approved" || r.status == "declined")
                    .max_by_key(|r| r.created_at) {
                    
                    match latest_request.status.as_str() {
                        "pending" => {
                            let message = l10n.format(lang.clone(), "request_pending", &[
                                ("status", "⏳ pending"),
                                ("date", &latest_request.created_at.format("%Y-%m-%d %H:%M UTC").to_string())
                            ]);
                            
                            let keyboard = get_new_user_keyboard(lang);
                            
                            if let Some(msg_id) = edit_message_id {
                                bot.edit_message_text(chat_id, msg_id, message)
                                    .parse_mode(teloxide::types::ParseMode::Html)
                                    .reply_markup(keyboard)
                                    .await?;
                                    
                                if let Some(cb_id) = callback_query_id {
                                    bot.answer_callback_query(cb_id).await?;
                                }
                            } else {
                                bot.send_message(chat_id, message)
                                    .parse_mode(teloxide::types::ParseMode::Html)
                                    .reply_markup(keyboard)
                                    .await?;
                            }
                            return Ok(());
                        }
                        "declined" => {
                            let message = l10n.format(lang.clone(), "request_pending", &[
                                ("status", &l10n.get(lang.clone(), "request_declined_status")),
                                ("date", &latest_request.created_at.format("%Y-%m-%d %H:%M UTC").to_string())
                            ]);
                            
                            let keyboard = get_new_user_keyboard(lang);
                            
                            if let Some(msg_id) = edit_message_id {
                                bot.edit_message_text(chat_id, msg_id, message)
                                    .parse_mode(teloxide::types::ParseMode::Html)
                                    .reply_markup(keyboard)
                                    .await?;
                                    
                                if let Some(cb_id) = callback_query_id {
                                    bot.answer_callback_query(cb_id).await?;
                                }
                            } else {
                                bot.send_message(chat_id, message)
                                    .parse_mode(teloxide::types::ParseMode::Html)
                                    .reply_markup(keyboard)
                                    .await?;
                            }
                            return Ok(());
                        }
                        _ => {} // approved - continue with normal flow
                    }
                }
            }
            
            // Existing user - show main menu
            let message = l10n.format(lang.clone(), "welcome_back", &[("name", &user.name)]);
            let keyboard = get_main_keyboard(is_admin, lang);
            
            if let Some(msg_id) = edit_message_id {
                bot.edit_message_text(chat_id, msg_id, message)
                    .reply_markup(keyboard)
                    .await?;
                    
                if let Some(cb_id) = callback_query_id {
                    bot.answer_callback_query(cb_id).await?;
                }
            } else {
                bot.send_message(chat_id, message)
                    .reply_markup(keyboard)
                    .await?;
            }
        }
        Ok(None) => {
            // New user - show access request
            let username = from.username.as_deref().unwrap_or("Unknown");
            let message = l10n.format(lang.clone(), "welcome_new_user", &[("username", username)]);
            let keyboard = get_new_user_keyboard(lang);
            
            if let Some(msg_id) = edit_message_id {
                bot.edit_message_text(chat_id, msg_id, message)
                    .reply_markup(keyboard)
                    .await?;
                    
                if let Some(cb_id) = callback_query_id {
                    bot.answer_callback_query(cb_id).await?;
                }
            } else {
                bot.send_message(chat_id, message)
                    .reply_markup(keyboard)
                    .await?;
            }
        }
        Err(e) => {
            tracing::error!("Database error: {}", e);
            bot.send_message(chat_id, "Database error occurred").await?;
        }
    }
    
    Ok(())
}

/// Handle access request
pub async fn handle_request_access(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    let telegram_id = from.id.0 as i64;
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;
    
    let user_repo = UserRepository::new(db.connection());
    let request_repo = UserRequestRepository::new(db.connection().clone());
    
    // Check if user already exists
    if let Some(_) = user_repo.get_by_telegram_id(telegram_id).await.unwrap_or(None) {
        bot.answer_callback_query(q.id.clone())
            .text(l10n.get(lang, "already_approved"))
            .await?;
        return Ok(());
    }
    
    // Check for existing requests
    if let Ok(existing_requests) = request_repo.find_by_telegram_id(telegram_id).await {
        if let Some(latest_request) = existing_requests.iter()
            .filter(|r| r.status == "pending")
            .max_by_key(|r| r.created_at) {
            
            // Show pending status in the message instead of just an alert
            let message = l10n.format(lang.clone(), "request_pending", &[
                ("status", "⏳ pending"),
                ("date", &latest_request.created_at.format("%Y-%m-%d %H:%M UTC").to_string())
            ]);
            
            if let Some(message_ref) = &q.message {
                if let teloxide::types::MaybeInaccessibleMessage::Regular(msg) = message_ref {
                    let _ = bot.edit_message_text(chat_id, msg.id, message)
                        .parse_mode(teloxide::types::ParseMode::Html)
                        .reply_markup(InlineKeyboardMarkup::new(vec![
                            vec![InlineKeyboardButton::callback(l10n.get(lang, "back"), "back")],
                        ]))
                        .await;
                }
            }
            
            bot.answer_callback_query(q.id.clone()).await?;
            return Ok(());
        }
        
        // Check for declined requests - allow new request after decline
        let _has_declined = existing_requests.iter()
            .any(|r| r.status == "declined");
    }
    
    // Create new access request
    let dto = CreateUserRequestDto {
        telegram_id,
        telegram_first_name: Some(from.first_name.clone()),
        telegram_last_name: from.last_name.clone(),
        telegram_username: from.username.clone(),
        request_message: Some("Access request via Telegram bot".to_string()),
        language: lang.code().to_string(),
    };
    
    match request_repo.create(dto).await {
        Ok(request) => {
            // Edit message to show success
            if let Some(message) = &q.message {
                if let teloxide::types::MaybeInaccessibleMessage::Regular(msg) = message {
                    let _ = bot.edit_message_text(chat_id, msg.id, l10n.get(lang.clone(), "request_submitted"))
                        .reply_markup(InlineKeyboardMarkup::new(vec![
                            vec![InlineKeyboardButton::callback(l10n.get(lang, "back"), "back")],
                        ]))
                        .await;
                }
            }
            
            // Notify admins
            notify_admins_new_request(&bot, &request, db).await?;
            
            bot.answer_callback_query(q.id.clone()).await?;
        }
        Err(e) => {
            tracing::error!("Failed to create request: {}", e);
            bot.answer_callback_query(q.id.clone())
                .text(l10n.format(lang, "request_submit_failed", &[("error", &e.to_string())]))
                .await?;
        }
    }
    
    Ok(())
}

/// Handle my configs with message editing
pub async fn handle_my_configs_edit(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    let telegram_id = from.id.0 as i64;
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;
    
    let user_repo = UserRepository::new(db.connection());
    let inbound_users_repo = crate::database::repository::InboundUsersRepository::new(db.connection().clone());
    let uri_service = crate::services::UriGeneratorService::new();
    
    if let Some(user) = user_repo.get_by_telegram_id(telegram_id).await.unwrap_or(None) {
        // Get all active inbound users for this user
        let inbound_users = inbound_users_repo.find_by_user_id(user.id).await.unwrap_or_default();
        
        if inbound_users.is_empty() {
            // Edit message to show no configs available
            if let Some(msg) = &q.message {
                if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
                    bot.edit_message_text(chat_id, regular_msg.id, l10n.get(lang.clone(), "no_configs_available"))
                        .reply_markup(InlineKeyboardMarkup::new(vec![
                            vec![InlineKeyboardButton::callback(l10n.get(lang, "back"), "back")],
                        ]))
                        .await?;
                }
            }
            bot.answer_callback_query(q.id.clone()).await?;
            return Ok(());
        }
        
        // Structure to hold config with inbound_id
        #[derive(Debug, Clone)]
        struct ConfigWithInbound {
            client_config: crate::services::uri_generator::ClientConfig,
            server_inbound_id: uuid::Uuid,
        }
        
        // Group configurations by server name
        let mut servers: std::collections::HashMap<String, Vec<ConfigWithInbound>> = std::collections::HashMap::new();
        
        for inbound_user in inbound_users {
            if !inbound_user.is_active {
                continue;
            }
            
            // Get client config data for this specific inbound
            if let Ok(Some(config_data)) = inbound_users_repo.get_client_config_data(user.id, inbound_user.server_inbound_id).await {
                match uri_service.generate_client_config(user.id, &config_data) {
                    Ok(client_config) => {
                        let config_with_inbound = ConfigWithInbound {
                            client_config: client_config.clone(),
                            server_inbound_id: inbound_user.server_inbound_id,
                        };
                        
                        servers.entry(client_config.server_name.clone())
                            .or_insert_with(Vec::new)
                            .push(config_with_inbound);
                    },
                    Err(e) => {
                        tracing::warn!("Failed to generate client config: {}", e);
                        continue;
                    }
                }
            }
        }
        
        // Build message with statistics only
        let mut message_lines = vec![l10n.get(lang.clone(), "your_configurations")];
        
        // Calculate statistics
        let server_count = servers.len();
        let total_configs = servers.values().map(|configs| configs.len()).sum::<usize>();
        
        // Count unique protocols
        let mut protocols = std::collections::HashSet::new();
        for configs in servers.values() {
            for config_with_inbound in configs {
                protocols.insert(config_with_inbound.client_config.protocol.clone());
            }
        }
        
        let server_word = match lang {
            Language::Russian => {
                if server_count == 1 { "сервер" } 
                else if server_count < 5 { "сервера" } 
                else { "серверов" }
            },
            Language::English => {
                if server_count == 1 { "server" } 
                else { "servers" }
            }
        };
        
        let config_word = match lang {
            Language::Russian => {
                if total_configs == 1 { "конфигурация" }
                else if total_configs < 5 { "конфигурации" }
                else { "конфигураций" }
            },
            Language::English => {
                if total_configs == 1 { "configuration" }
                else { "configurations" }
            }
        };
        
        let protocol_word = match lang {
            Language::Russian => {
                if protocols.len() == 1 { "протокол" }
                else if protocols.len() < 5 { "протокола" }
                else { "протоколов" }
            },
            Language::English => {
                if protocols.len() == 1 { "protocol" }
                else { "protocols" }
            }
        };
        
        message_lines.push(format!(
            "\n📊 {} {} • {} {} • {} {}",
            server_count, server_word,
            total_configs, config_word,
            protocols.len(), protocol_word
        ));
        
        // Create keyboard with buttons for each server
        let mut keyboard_buttons = vec![];
        
        for (server_name, configs) in servers.iter() {
            // Encode server name to avoid issues with special characters
            let encoded_server_name = general_purpose::STANDARD.encode(server_name.as_bytes());
            let config_count = configs.len();
            
            let config_suffix = match lang {
                Language::Russian => {
                    if config_count == 1 { 
                        "" 
                    } else if config_count < 5 { 
                        "а" 
                    } else { 
                        "ов" 
                    }
                },
                Language::English => {
                    if config_count == 1 { 
                        "" 
                    } else { 
                        "s" 
                    }
                }
            };
            
            let config_word = match lang {
                Language::Russian => "конфиг",
                Language::English => "config",
            };
            
            keyboard_buttons.push(vec![
                InlineKeyboardButton::callback(
                    format!("🖥️ {} ({} {}{})", server_name, config_count, config_word, config_suffix),
                    format!("server_configs:{}", encoded_server_name)
                )
            ]);
        }
        
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
    }
    
    Ok(())
}

/// Handle show server configs callback
pub async fn handle_show_server_configs(
    bot: Bot,
    q: &CallbackQuery,
    encoded_server_name: &str,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    let telegram_id = from.id.0 as i64;
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;
    
    // Decode server name
    let server_name = match general_purpose::STANDARD.decode(encoded_server_name) {
        Ok(bytes) => String::from_utf8(bytes).map_err(|_| "Invalid server name encoding")?,
        Err(_) => return Ok(()), // Invalid encoding, ignore
    };
    
    let user_repo = UserRepository::new(db.connection());
    let inbound_users_repo = crate::database::repository::InboundUsersRepository::new(db.connection().clone());
    let uri_service = crate::services::UriGeneratorService::new();
    
    // Get user from telegram_id
    if let Some(user) = user_repo.get_by_telegram_id(telegram_id).await.unwrap_or(None) {
        // Get all active inbound users for this user
        let inbound_users = inbound_users_repo.find_by_user_id(user.id).await.unwrap_or_default();
        
        let mut server_configs = Vec::new();
        
        for inbound_user in inbound_users {
            if !inbound_user.is_active {
                continue;
            }
            
            // Get client config data for this specific inbound
            if let Ok(Some(config_data)) = inbound_users_repo.get_client_config_data(user.id, inbound_user.server_inbound_id).await {
                if config_data.server_name == server_name {
                    match uri_service.generate_client_config(user.id, &config_data) {
                        Ok(client_config) => {
                            server_configs.push(client_config);
                        },
                        Err(e) => {
                            tracing::warn!("Failed to generate client config: {}", e);
                            continue;
                        }
                    }
                }
            }
        }
        
        if server_configs.is_empty() {
            bot.answer_callback_query(q.id.clone())
                .text(l10n.get(lang, "config_not_found"))
                .await?;
            return Ok(());
        }
        
        // Build message with all configs for this server
        let mut message_lines = vec![
            l10n.format(lang.clone(), "server_configs_title", &[("server_name", &server_name)])
        ];
        
        for config in &server_configs {
            let protocol_emoji = match config.protocol.as_str() {
                "vless" => "🔵",
                "vmess" => "🟢", 
                "trojan" => "🔴",
                "shadowsocks" => "🟡",
                _ => "⚪"
            };
            
            message_lines.push(format!(
                "\n{} <b>{} - {}</b> ({})",
                protocol_emoji,
                config.server_name,
                config.template_name,
                config.protocol.to_uppercase()
            ));
            
            message_lines.push(format!("<code>{}</code>", config.uri));
        }
        
        // Create back button
        let keyboard = InlineKeyboardMarkup::new(vec![
            vec![InlineKeyboardButton::callback(l10n.get(lang, "back"), "back_to_configs")],
        ]);
        
        let message = message_lines.join("\n");
        
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
    } else {
        bot.answer_callback_query(q.id.clone())
            .text(l10n.get(lang, "unauthorized"))
            .await?;
    }
    
    Ok(())
}

/// Handle support button
pub async fn handle_support(
    bot: Bot,
    q: &CallbackQuery,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = &q.from;
    let lang = get_user_language(from);
    let l10n = LocalizationService::new();
    let chat_id = q.message.as_ref().and_then(|m| {
        match m {
            teloxide::types::MaybeInaccessibleMessage::Regular(msg) => Some(msg.chat.id),
            _ => None,
        }
    }).ok_or("No chat ID")?;
    
    let keyboard = InlineKeyboardMarkup::new(vec![
        vec![InlineKeyboardButton::callback(l10n.get(lang.clone(), "back"), "back")],
    ]);
    
    // Edit the existing message instead of sending a new one
    if let Some(msg) = &q.message {
        if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
            bot.edit_message_text(chat_id, regular_msg.id, l10n.get(lang, "support_info"))
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(keyboard)
                .await?;
        }
    }
    
    bot.answer_callback_query(q.id.clone()).await?;
    
    Ok(())
}

/// Notify admins about new access request
async fn notify_admins_new_request(
    bot: &Bot,
    request: &crate::database::entities::user_request::Model,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let user_repo = UserRepository::new(db.connection());
    
    // Get all admins
    let admins = user_repo.get_telegram_admins().await.unwrap_or_default();
    
    if !admins.is_empty() {
        let lang = Language::English; // Default admin language
        let l10n = LocalizationService::new();
        
        let message = l10n.format(lang.clone(), "new_access_request", &[
            ("first_name", &request.telegram_first_name.as_deref().unwrap_or("")),
            ("last_name", &request.telegram_last_name.as_deref().unwrap_or("")),
            ("username", &request.telegram_username.as_deref().unwrap_or("unknown")),
        ]);
        
        let keyboard = InlineKeyboardMarkup::new(vec![
            vec![
                InlineKeyboardButton::callback(l10n.get(lang.clone(), "approve"), format!("approve:{}", request.id)),
                InlineKeyboardButton::callback(l10n.get(lang.clone(), "decline"), format!("decline:{}", request.id)),
            ],
            vec![
                InlineKeyboardButton::callback("📋 All Requests", "back_to_requests"),
            ],
        ]);
        
        for admin in admins {
            if let Some(telegram_id) = admin.telegram_id {
                let _ = bot.send_message(ChatId(telegram_id), &message)
                    .parse_mode(teloxide::types::ParseMode::Html)
                    .reply_markup(keyboard.clone())
                    .await;
            }
        }
    }
    
    Ok(())
}

/// Handle subscription link request
pub async fn handle_subscription_link(
    bot: Bot,
    q: &CallbackQuery,
    db: &DatabaseManager,
    app_config: &crate::config::AppConfig,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let from = q.from.clone();
    let telegram_id = from.id.0 as i64;
    let lang = get_user_language(&from);
    let l10n = LocalizationService::new();

    // Get user from database
    let user_repo = UserRepository::new(db.connection());
    if let Ok(Some(user)) = user_repo.get_by_telegram_id(telegram_id).await {
        // Generate subscription URL
        let subscription_url = format!("{}/sub/{}", app_config.web.base_url, user.id);
        
        let message = match lang {
            Language::Russian => {
                format!(
                    "🔗 <b>Ваша ссылка подписки</b>\n\n\
                    Скопируйте эту ссылку и добавьте её в ваш VPN-клиент:\n\n\
                    <code>{}</code>\n\n\
                    💡 <i>Эта ссылка содержит все ваши конфигурации и автоматически обновляется при изменениях</i>",
                    subscription_url
                )
            },
            Language::English => {
                format!(
                    "🔗 <b>Your Subscription Link</b>\n\n\
                    Copy this link and add it to your VPN client:\n\n\
                    <code>{}</code>\n\n\
                    💡 <i>This link contains all your configurations and updates automatically when changes are made</i>",
                    subscription_url
                )
            }
        };

        let keyboard = InlineKeyboardMarkup::new(vec![
            vec![InlineKeyboardButton::callback(l10n.get(lang, "back"), "back")],
        ]);

        // Edit the existing message
        if let Some(msg) = &q.message {
            if let teloxide::types::MaybeInaccessibleMessage::Regular(regular_msg) = msg {
                let chat_id = regular_msg.chat.id;
                bot.edit_message_text(chat_id, regular_msg.id, message)
                    .parse_mode(teloxide::types::ParseMode::Html)
                    .reply_markup(keyboard)
                    .await?;
            }
        }
    } else {
        // User not found - this shouldn't happen for registered users
        bot.answer_callback_query(q.id.clone())
            .text("User not found")
            .await?;
        return Ok(());
    }

    bot.answer_callback_query(q.id.clone()).await?;
    Ok(())
}