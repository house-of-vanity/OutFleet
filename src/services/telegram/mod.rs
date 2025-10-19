use anyhow::Result;
use std::sync::Arc;
use teloxide::{Bot, prelude::*};
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::database::DatabaseManager;
use crate::database::repository::TelegramConfigRepository;
use crate::database::entities::telegram_config::Model as TelegramConfig;
use crate::config::AppConfig;

pub mod bot;
pub mod handlers;
pub mod error;
pub mod localization;

pub use error::TelegramError;

/// Main Telegram service that manages the bot lifecycle
pub struct TelegramService {
    db: DatabaseManager,
    app_config: AppConfig,
    bot: Arc<RwLock<Option<Bot>>>,
    config: Arc<RwLock<Option<TelegramConfig>>>,
    shutdown_signal: Arc<RwLock<Option<tokio::sync::oneshot::Sender<()>>>>,
}

impl TelegramService {
    /// Create a new Telegram service
    pub fn new(db: DatabaseManager, app_config: AppConfig) -> Self {
        Self {
            db,
            app_config,
            bot: Arc::new(RwLock::new(None)),
            config: Arc::new(RwLock::new(None)),
            shutdown_signal: Arc::new(RwLock::new(None)),
        }
    }

    /// Initialize and start the bot if active configuration exists
    pub async fn initialize(&self) -> Result<()> {
        let repo = TelegramConfigRepository::new(self.db.connection());
        
        // Get active configuration
        if let Some(config) = repo.get_active().await? {
            self.start_with_config(config).await?;
        }
        
        Ok(())
    }

    /// Start bot with specific configuration
    pub async fn start_with_config(&self, config: TelegramConfig) -> Result<()> {
        // Stop existing bot if running
        self.stop().await?;

        // Create new bot instance
        let bot = Bot::new(&config.bot_token);
        
        // Verify token by calling getMe
        match bot.get_me().await {
            Ok(me) => {
                let username = me.user.username.unwrap_or_default();
                tracing::info!("Telegram bot started: @{}", username);
            }
            Err(e) => {
                return Err(anyhow::anyhow!("Invalid bot token: {}", e));
            }
        }

        // Store bot and config
        *self.bot.write().await = Some(bot.clone());
        *self.config.write().await = Some(config.clone());

        // Start polling in background
        if config.is_active {
            self.start_polling(bot).await?;
        }

        Ok(())
    }

    /// Start polling for updates
    async fn start_polling(&self, bot: Bot) -> Result<()> {
        let (tx, rx) = tokio::sync::oneshot::channel();
        *self.shutdown_signal.write().await = Some(tx);

        let db = self.db.clone();
        let app_config = self.app_config.clone();
        
        // Spawn polling task
        tokio::spawn(async move {
            bot::run_polling(bot, db, app_config, rx).await;
        });

        Ok(())
    }

    /// Stop the bot
    pub async fn stop(&self) -> Result<()> {
        // Send shutdown signal if polling is running
        if let Some(tx) = self.shutdown_signal.write().await.take() {
            let _ = tx.send(()); // Ignore error if receiver is already dropped
        }

        // Clear bot and config
        *self.bot.write().await = None;
        *self.config.write().await = None;

        tracing::info!("Telegram bot stopped");
        Ok(())
    }

    /// Update configuration and restart if needed
    pub async fn update_config(&self, config_id: Uuid) -> Result<()> {
        let repo = TelegramConfigRepository::new(self.db.connection());
        
        if let Some(config) = repo.find_by_id(config_id).await? {
            if config.is_active {
                self.start_with_config(config).await?;
            } else {
                self.stop().await?;
            }
        }
        
        Ok(())
    }

    /// Get current bot status
    pub async fn get_status(&self) -> BotStatus {
        let bot_guard = self.bot.read().await;
        let config_guard = self.config.read().await;
        
        BotStatus {
            is_running: bot_guard.is_some(),
            config: config_guard.clone(),
        }
    }

    /// Send message to user
    pub async fn send_message(&self, chat_id: i64, text: String) -> Result<()> {
        let bot_guard = self.bot.read().await;
        
        if let Some(bot) = bot_guard.as_ref() {
            bot.send_message(ChatId(chat_id), text).await?;
            Ok(())
        } else {
            Err(anyhow::anyhow!("Bot is not running"))
        }
    }
    
    /// Send message to user with inline keyboard
    pub async fn send_message_with_keyboard(&self, chat_id: i64, text: String, keyboard: teloxide::types::InlineKeyboardMarkup) -> Result<()> {
        let bot_guard = self.bot.read().await;
        
        if let Some(bot) = bot_guard.as_ref() {
            bot.send_message(ChatId(chat_id), text)
                .parse_mode(teloxide::types::ParseMode::Html)
                .reply_markup(keyboard)
                .await?;
            Ok(())
        } else {
            Err(anyhow::anyhow!("Bot is not running"))
        }
    }

    /// Send message to all admins
    pub async fn broadcast_to_admins(&self, text: String) -> Result<()> {
        let bot_guard = self.bot.read().await;
        
        if let Some(bot) = bot_guard.as_ref() {
            let user_repo = crate::database::repository::UserRepository::new(self.db.connection());
            let admins = user_repo.get_telegram_admins().await?;
            
            for admin in admins {
                if let Some(telegram_id) = admin.telegram_id {
                    if let Err(e) = bot.send_message(ChatId(telegram_id), text.clone()).await {
                        tracing::warn!("Failed to send message to admin {}: {}", telegram_id, e);
                    }
                }
            }
            
            Ok(())
        } else {
            Err(anyhow::anyhow!("Bot is not running"))
        }
    }
}

/// Bot status information
#[derive(Debug, Clone, serde::Serialize)]
pub struct BotStatus {
    pub is_running: bool,
    pub config: Option<TelegramConfig>,
}