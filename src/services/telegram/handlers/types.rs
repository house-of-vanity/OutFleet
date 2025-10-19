use teloxide::utils::command::BotCommands;
use teloxide::types::{InlineKeyboardButton, InlineKeyboardMarkup, User};

use super::super::localization::{LocalizationService, Language};
use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

/// Available bot commands - keeping only admin commands
#[derive(BotCommands, Clone)]
#[command(rename_rule = "lowercase", description = "Admin commands:")]
pub enum Command {
    #[command(description = "Start the bot")]
    Start,
    #[command(description = "[Admin] Manage user requests")]
    Requests,
    #[command(description = "[Admin] Show statistics")]
    Stats,
    #[command(description = "[Admin] Broadcast message", parse_with = "split")]
    Broadcast { message: String },
}

/// Callback data for inline keyboard buttons
#[derive(Debug, Clone)]
pub enum CallbackData {
    RequestAccess,
    MyConfigs,
    SubscriptionLink,
    Support,
    AdminRequests,
    ApproveRequest(String), // request_id
    DeclineRequest(String), // request_id
    ViewRequest(String), // request_id
    ShowServerConfigs(String), // server_name encoded
    Back,
    BackToConfigs, // Back to configs list from server view
    BackToRequests, // Back to requests list from request view
    SelectServerAccess(String), // request_id - show server selection after approval
    ToggleServer(String, String), // request_id, server_id - toggle server selection
    ApplyServerAccess(String), // request_id - apply selected servers
}

impl CallbackData {
    pub fn parse(data: &str) -> Option<Self> {
        match data {
            "request_access" => Some(CallbackData::RequestAccess),
            "my_configs" => Some(CallbackData::MyConfigs),
            "subscription_link" => Some(CallbackData::SubscriptionLink),
            "support" => Some(CallbackData::Support),
            "admin_requests" => Some(CallbackData::AdminRequests),
            "back" => Some(CallbackData::Back),
            "back_to_configs" => Some(CallbackData::BackToConfigs),
            "back_to_requests" => Some(CallbackData::BackToRequests),
            _ => {
                if let Some(id) = data.strip_prefix("approve:") {
                    Some(CallbackData::ApproveRequest(id.to_string()))
                } else if let Some(id) = data.strip_prefix("decline:") {
                    Some(CallbackData::DeclineRequest(id.to_string()))
                } else if let Some(id) = data.strip_prefix("view_request:") {
                    Some(CallbackData::ViewRequest(id.to_string()))
                } else if let Some(server_name) = data.strip_prefix("server_configs:") {
                    Some(CallbackData::ShowServerConfigs(server_name.to_string()))
                } else if let Some(short_id) = data.strip_prefix("s:") {
                    get_full_request_id(short_id).map(CallbackData::SelectServerAccess)
                } else if let Some(rest) = data.strip_prefix("t:") {
                    let parts: Vec<&str> = rest.split(':').collect();
                    if parts.len() == 2 {
                        if let (Some(request_id), Some(server_id)) = (get_full_request_id(parts[0]), get_full_server_id(parts[1])) {
                            Some(CallbackData::ToggleServer(request_id, server_id))
                        } else {
                            None
                        }
                    } else {
                        None
                    }
                } else if let Some(short_id) = data.strip_prefix("a:") {
                    get_full_request_id(short_id).map(CallbackData::ApplyServerAccess)
                } else {
                    None
                }
            }
        }
    }
}

// Global storage for selected servers per request
static SELECTED_SERVERS: OnceLock<Arc<Mutex<HashMap<String, Vec<String>>>>> = OnceLock::new();

// Global storage for request ID mappings (short ID -> full UUID)
static REQUEST_ID_MAP: OnceLock<Arc<Mutex<HashMap<String, String>>>> = OnceLock::new();
static REQUEST_COUNTER: OnceLock<Arc<Mutex<u32>>> = OnceLock::new();

// Global storage for server ID mappings (short ID -> full UUID)
static SERVER_ID_MAP: OnceLock<Arc<Mutex<HashMap<String, String>>>> = OnceLock::new();
static SERVER_COUNTER: OnceLock<Arc<Mutex<u32>>> = OnceLock::new();

pub fn get_selected_servers() -> &'static Arc<Mutex<HashMap<String, Vec<String>>>> {
    SELECTED_SERVERS.get_or_init(|| Arc::new(Mutex::new(HashMap::new())))
}

pub fn get_request_id_map() -> &'static Arc<Mutex<HashMap<String, String>>> {
    REQUEST_ID_MAP.get_or_init(|| Arc::new(Mutex::new(HashMap::new())))
}

pub fn get_request_counter() -> &'static Arc<Mutex<u32>> {
    REQUEST_COUNTER.get_or_init(|| Arc::new(Mutex::new(0)))
}

pub fn get_server_id_map() -> &'static Arc<Mutex<HashMap<String, String>>> {
    SERVER_ID_MAP.get_or_init(|| Arc::new(Mutex::new(HashMap::new())))
}

pub fn get_server_counter() -> &'static Arc<Mutex<u32>> {
    SERVER_COUNTER.get_or_init(|| Arc::new(Mutex::new(0)))
}

/// Generate a short ID for a request UUID and store the mapping
pub fn generate_short_request_id(request_uuid: &str) -> String {
    let mut counter = get_request_counter().lock().unwrap();
    let mut map = get_request_id_map().lock().unwrap();
    
    // Check if we already have a short ID for this UUID
    for (short_id, uuid) in map.iter() {
        if uuid == request_uuid {
            return short_id.clone();
        }
    }
    
    // Generate new short ID
    *counter += 1;
    let short_id = format!("r{}", counter);
    map.insert(short_id.clone(), request_uuid.to_string());
    
    short_id
}

/// Get full UUID from short ID
pub fn get_full_request_id(short_id: &str) -> Option<String> {
    let map = get_request_id_map().lock().unwrap();
    map.get(short_id).cloned()
}

/// Generate a short ID for a server UUID and store the mapping
pub fn generate_short_server_id(server_uuid: &str) -> String {
    let mut counter = get_server_counter().lock().unwrap();
    let mut map = get_server_id_map().lock().unwrap();
    
    // Check if we already have a short ID for this UUID
    for (short_id, uuid) in map.iter() {
        if uuid == server_uuid {
            return short_id.clone();
        }
    }
    
    // Generate new short ID
    *counter += 1;
    let short_id = format!("s{}", counter);
    map.insert(short_id.clone(), server_uuid.to_string());
    
    short_id
}

/// Get full server UUID from short ID
pub fn get_full_server_id(short_id: &str) -> Option<String> {
    let map = get_server_id_map().lock().unwrap();
    map.get(short_id).cloned()
}

/// Helper function to get user language from Telegram user data
pub fn get_user_language(user: &User) -> Language {
    Language::from_telegram_code(user.language_code.as_deref())
}

/// Main keyboard for registered users
pub fn get_main_keyboard(is_admin: bool, lang: Language) -> InlineKeyboardMarkup {
    let l10n = LocalizationService::new();
    
    let mut keyboard = vec![
        vec![InlineKeyboardButton::callback("🔗 Subscription Link", "subscription_link")],
        vec![InlineKeyboardButton::callback(l10n.get(lang.clone(), "my_configs"), "my_configs")],
        vec![InlineKeyboardButton::callback(l10n.get(lang.clone(), "support"), "support")],
    ];
    
    if is_admin {
        keyboard.push(vec![InlineKeyboardButton::callback(l10n.get(lang, "user_requests"), "admin_requests")]);
    }
    
    InlineKeyboardMarkup::new(keyboard)
}

/// Keyboard for new users
pub fn get_new_user_keyboard(lang: Language) -> InlineKeyboardMarkup {
    let l10n = LocalizationService::new();
    
    InlineKeyboardMarkup::new(vec![
        vec![InlineKeyboardButton::callback(l10n.get(lang, "get_vpn_access"), "request_access")],
    ])
}

/// Restore UUID from compact format (without dashes)
fn restore_uuid(compact: &str) -> Option<String> {
    if compact.len() != 32 {
        return None;
    }
    
    // Insert dashes at proper positions for UUID format
    let uuid_str = format!(
        "{}-{}-{}-{}-{}",
        &compact[0..8],
        &compact[8..12],
        &compact[12..16],
        &compact[16..20],
        &compact[20..32]
    );
    
    Some(uuid_str)
}