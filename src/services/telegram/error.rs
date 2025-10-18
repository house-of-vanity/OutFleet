use thiserror::Error;

#[derive(Error, Debug)]
pub enum TelegramError {
    #[error("Bot is not configured")]
    NotConfigured,

    #[error("Bot is not running")]
    NotRunning,

    #[error("Invalid bot token")]
    InvalidToken,

    #[error("User not found")]
    UserNotFound,

    #[error("User is not authorized")]
    Unauthorized,

    #[error("Database error: {0}")]
    Database(String),

    #[error("Telegram API error: {0}")]
    TelegramApi(String),

    #[error("Other error: {0}")]
    Other(String),
}

impl From<teloxide::RequestError> for TelegramError {
    fn from(err: teloxide::RequestError) -> Self {
        Self::TelegramApi(err.to_string())
    }
}

impl From<sea_orm::DbErr> for TelegramError {
    fn from(err: sea_orm::DbErr) -> Self {
        Self::Database(err.to_string())
    }
}

impl From<anyhow::Error> for TelegramError {
    fn from(err: anyhow::Error) -> Self {
        Self::Other(err.to_string())
    }
}