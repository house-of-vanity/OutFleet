use teloxide::{prelude::*, utils::command::BotCommands};
use teloxide::types::Me;
use uuid::Uuid;

use crate::database::DatabaseManager;
use crate::database::repository::UserRepository;
use crate::database::entities::user::CreateUserDto;

/// Available bot commands
#[derive(BotCommands, Clone)]
#[command(rename_rule = "lowercase", description = "Available commands:")]
pub enum Command {
    #[command(description = "Start the bot and register")]
    Start,
    #[command(description = "Show help message")]
    Help,
    #[command(description = "Show your status")]
    Status,
    #[command(description = "List available configurations")]
    Configs,
    // Admin commands
    #[command(description = "[Admin] List all users")]
    Users,
    #[command(description = "[Admin] List all servers")]
    Servers,
    #[command(description = "[Admin] Show statistics")]
    Stats,
    #[command(description = "[Admin] Broadcast message", parse_with = "split")]
    Broadcast { message: String },
}

/// Handle command messages
pub async fn handle_command(
    bot: Bot,
    msg: Message,
    cmd: Command,
    db: DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let chat_id = msg.chat.id;
    let from = msg.from.as_ref().ok_or("No sender info")?;
    let telegram_id = from.id.0 as i64;

    let user_repo = UserRepository::new(db.connection());

    match cmd {
        Command::Start => {
            handle_start(bot, chat_id, telegram_id, from, &user_repo).await?;
        }
        Command::Help => {
            bot.send_message(chat_id, Command::descriptions().to_string()).await?;
        }
        Command::Status => {
            handle_status(bot, chat_id, telegram_id, &user_repo, &db).await?;
        }
        Command::Configs => {
            handle_configs(bot, chat_id, telegram_id, &user_repo, &db).await?;
        }
        // Admin commands
        Command::Users => {
            if !user_repo.is_telegram_id_admin(telegram_id).await.unwrap_or(false) {
                bot.send_message(chat_id, "❌ You are not authorized to use this command").await?;
                return Ok(());
            }
            handle_users(bot, chat_id, &user_repo).await?;
        }
        Command::Servers => {
            if !user_repo.is_telegram_id_admin(telegram_id).await.unwrap_or(false) {
                bot.send_message(chat_id, "❌ You are not authorized to use this command").await?;
                return Ok(());
            }
            handle_servers(bot, chat_id, &db).await?;
        }
        Command::Stats => {
            if !user_repo.is_telegram_id_admin(telegram_id).await.unwrap_or(false) {
                bot.send_message(chat_id, "❌ You are not authorized to use this command").await?;
                return Ok(());
            }
            handle_stats(bot, chat_id, &db).await?;
        }
        Command::Broadcast { message } => {
            if !user_repo.is_telegram_id_admin(telegram_id).await.unwrap_or(false) {
                bot.send_message(chat_id, "❌ You are not authorized to use this command").await?;
                return Ok(());
            }
            handle_broadcast(bot, chat_id, message, &user_repo).await?;
        }
    }

    Ok(())
}

/// Handle regular text messages
pub async fn handle_message(
    bot: Bot,
    msg: Message,
    db: DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    if let Some(text) = msg.text() {
        if !text.starts_with('/') {
            bot.send_message(
                msg.chat.id, 
                "Please use /help to see available commands"
            ).await?;
        }
    }

    Ok(())
}

/// Handle /start command
async fn handle_start(
    bot: Bot,
    chat_id: ChatId,
    telegram_id: i64,
    from: &teloxide::types::User,
    user_repo: &UserRepository,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // Check if user already exists
    if let Some(user) = user_repo.get_by_telegram_id(telegram_id).await.unwrap_or(None) {
        let message = format!(
            "👋 Welcome back, {}!\n\n\
            You are already registered.\n\
            Use /help to see available commands.",
            user.name
        );
        bot.send_message(chat_id, message).await?;
    } else {
        // Create new user
        let username = from.username.as_deref().unwrap_or("Unknown");
        let full_name = format!(
            "{} {}",
            from.first_name,
            from.last_name.as_deref().unwrap_or("")
        ).trim().to_string();
        
        let dto = CreateUserDto {
            name: if !full_name.is_empty() { full_name } else { username.to_string() },
            comment: Some(format!("Telegram user: @{}", username)),
            telegram_id: Some(telegram_id),
            is_telegram_admin: false,
        };

        match user_repo.create(dto).await {
            Ok(user) => {
                let message = format!(
                    "✅ Registration successful!\n\n\
                    Name: {}\n\
                    User ID: {}\n\n\
                    Use /help to see available commands.",
                    user.name, user.id
                );
                bot.send_message(chat_id, message).await?;
            }
            Err(e) => {
                bot.send_message(
                    chat_id, 
                    format!("❌ Registration failed: {}", e)
                ).await?;
            }
        }
    }

    Ok(())
}

/// Handle /status command
async fn handle_status(
    bot: Bot,
    chat_id: ChatId,
    telegram_id: i64,
    user_repo: &UserRepository,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    if let Some(user) = user_repo.get_by_telegram_id(telegram_id).await.unwrap_or(None) {
        let server_inbound_repo = crate::database::repository::ServerInboundRepository::new(db.connection());
        let configs = server_inbound_repo.find_by_user_id(user.id).await.unwrap_or_default();
        
        let admin_status = if user.is_telegram_admin { "Admin" } else { "User" };
        
        let message = format!(
            "📊 Your Status\n\n\
            Name: {}\n\
            User ID: {}\n\
            Role: {}\n\
            Active Configs: {}\n\
            Registered: {}",
            user.name,
            user.id,
            admin_status,
            configs.len(),
            user.created_at.format("%Y-%m-%d %H:%M UTC")
        );
        
        bot.send_message(chat_id, message).await?;
    } else {
        bot.send_message(
            chat_id, 
            "❌ You are not registered. Use /start to register."
        ).await?;
    }

    Ok(())
}

/// Handle /configs command
async fn handle_configs(
    bot: Bot,
    chat_id: ChatId,
    telegram_id: i64,
    user_repo: &UserRepository,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    if let Some(user) = user_repo.get_by_telegram_id(telegram_id).await.unwrap_or(None) {
        let server_inbound_repo = crate::database::repository::ServerInboundRepository::new(db.connection());
        let configs = server_inbound_repo.find_by_user_id(user.id).await.unwrap_or_default();
        
        if configs.is_empty() {
            bot.send_message(chat_id, "You don't have any configurations yet.").await?;
        } else {
            let mut message = String::from("📋 Your Configurations:\n\n");
            
            for (i, config) in configs.iter().enumerate() {
                message.push_str(&format!(
                    "{}. {} (Port: {})\n",
                    i + 1,
                    config.tag,
                    config.port_override.unwrap_or(0)
                ));
            }
            
            bot.send_message(chat_id, message).await?;
        }
    } else {
        bot.send_message(
            chat_id, 
            "❌ You are not registered. Use /start to register."
        ).await?;
    }

    Ok(())
}

/// Handle /users command (admin only)
async fn handle_users(
    bot: Bot,
    chat_id: ChatId,
    user_repo: &UserRepository,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let users = user_repo.get_all(1, 100).await.unwrap_or_default();
    
    if users.is_empty() {
        bot.send_message(chat_id, "No users found.").await?;
    } else {
        let mut message = String::from("👥 Users:\n\n");
        
        for (i, user) in users.iter().enumerate() {
            let telegram_status = if user.telegram_id.is_some() { "✅" } else { "❌" };
            let admin_status = if user.is_telegram_admin { " (Admin)" } else { "" };
            
            message.push_str(&format!(
                "{}. {} {} {}{}\n",
                i + 1,
                user.name,
                telegram_status,
                user.id,
                admin_status
            ));
        }
        
        bot.send_message(chat_id, message).await?;
    }

    Ok(())
}

/// Handle /servers command (admin only)
async fn handle_servers(
    bot: Bot,
    chat_id: ChatId,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let server_repo = crate::database::repository::ServerRepository::new(db.connection());
    let servers = server_repo.get_all().await.unwrap_or_default();
    
    if servers.is_empty() {
        bot.send_message(chat_id, "No servers found.").await?;
    } else {
        let mut message = String::from("🖥️ Servers:\n\n");
        
        for (i, server) in servers.iter().enumerate() {
            let status = if server.status == "active" { "✅" } else { "❌" };
            
            message.push_str(&format!(
                "{}. {} {} - {}\n",
                i + 1,
                status,
                server.name,
                server.hostname
            ));
        }
        
        bot.send_message(chat_id, message).await?;
    }

    Ok(())
}

/// Handle /stats command (admin only)
async fn handle_stats(
    bot: Bot,
    chat_id: ChatId,
    db: &DatabaseManager,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let user_repo = UserRepository::new(db.connection());
    let server_repo = crate::database::repository::ServerRepository::new(db.connection());
    let inbound_repo = crate::database::repository::ServerInboundRepository::new(db.connection());
    
    let user_count = user_repo.count().await.unwrap_or(0);
    let server_count = server_repo.count().await.unwrap_or(0);
    let inbound_count = inbound_repo.count().await.unwrap_or(0);
    
    let message = format!(
        "📊 Statistics\n\n\
        Total Users: {}\n\
        Total Servers: {}\n\
        Total Inbounds: {}",
        user_count,
        server_count,
        inbound_count
    );
    
    bot.send_message(chat_id, message).await?;

    Ok(())
}

/// Handle /broadcast command (admin only)
async fn handle_broadcast(
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
                Err(e) => {
                    tracing::warn!("Failed to send broadcast to {}: {}", telegram_id, e);
                    failed_count += 1;
                }
            }
        }
    }
    
    bot.send_message(
        chat_id, 
        format!(
            "✅ Broadcast complete\n\
            Sent: {}\n\
            Failed: {}",
            sent_count, failed_count
        )
    ).await?;

    Ok(())
}