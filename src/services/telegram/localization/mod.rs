use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Language {
    Russian,
    English,
}

impl Language {
    pub fn from_telegram_code(code: Option<&str>) -> Self {
        match code {
            Some("ru") | Some("by") | Some("kk") | Some("uk") => Self::Russian,
            _ => Self::English, // Default to English
        }
    }

    pub fn code(&self) -> &'static str {
        match self {
            Self::Russian => "ru",
            Self::English => "en",
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Translations {
    pub welcome_new_user: String,
    pub welcome_back: String,
    pub request_pending: String,
    pub request_approved_status: String,
    pub request_declined_status: String,
    pub get_vpn_access: String,
    pub my_configs: String,
    pub support: String,
    pub user_requests: String,
    pub back: String,
    pub approve: String,
    pub decline: String,

    // Request handling
    pub already_pending: String,
    pub already_approved: String,
    pub already_declined: String,
    pub request_submitted: String,
    pub request_submit_failed: String,

    // Approval/Decline messages
    pub request_approved: String,
    pub request_declined: String,
    pub request_approved_notification: String,
    pub request_declined_notification: String,

    // Admin messages
    pub new_access_request: String,
    pub no_pending_requests: String,
    pub access_request_details: String,
    pub unauthorized: String,
    pub request_approved_admin: String,
    pub request_declined_admin: String,
    pub user_creation_failed: String,

    // Support
    pub support_info: String,

    // Stats
    pub statistics: String,
    pub total_users: String,
    pub total_servers: String,
    pub total_inbounds: String,
    pub pending_requests: String,

    // Broadcast
    pub broadcast_complete: String,
    pub sent: String,
    pub failed: String,

    // Configs
    pub configs_coming_soon: String,
    pub your_configurations: String,
    pub no_configs_available: String,
    pub config_copy_message: String,
    pub config_copied: String,
    pub config_not_found: String,
    pub server_configs_title: String,

    // Subscription
    pub subscription_link: String,

    // User Management
    pub manage_users: String,
    pub user_list: String,
    pub user_details: String,
    pub manage_access: String,
    pub remove_access: String,
    pub grant_access: String,
    pub user_info: String,
    pub no_users_found: String,
    pub page_info: String,
    pub next_page: String,
    pub prev_page: String,
    pub back_to_users: String,
    pub back_to_menu: String,
    pub access_updated: String,
    pub access_removed: String,
    pub access_granted: String,

    // Errors
    pub error_occurred: String,
    pub admin_not_found: String,
    pub request_not_found: String,
    pub invalid_request_id: String,
}

pub struct LocalizationService {
    translations: HashMap<Language, Translations>,
}

impl LocalizationService {
    pub fn new() -> Self {
        let mut translations = HashMap::new();

        // Load English translations
        translations.insert(Language::English, Self::load_english());

        // Load Russian translations
        translations.insert(Language::Russian, Self::load_russian());

        Self { translations }
    }

    pub fn get(&self, lang: Language, key: &str) -> String {
        let translations = self
            .translations
            .get(&lang)
            .unwrap_or_else(|| self.translations.get(&Language::English).unwrap());

        match key {
            "welcome_new_user" => translations.welcome_new_user.clone(),
            "welcome_back" => translations.welcome_back.clone(),
            "request_pending" => translations.request_pending.clone(),
            "request_approved_status" => translations.request_approved_status.clone(),
            "request_declined_status" => translations.request_declined_status.clone(),
            "get_vpn_access" => translations.get_vpn_access.clone(),
            "my_configs" => translations.my_configs.clone(),
            "support" => translations.support.clone(),
            "user_requests" => translations.user_requests.clone(),
            "back" => translations.back.clone(),
            "approve" => translations.approve.clone(),
            "decline" => translations.decline.clone(),
            "already_pending" => translations.already_pending.clone(),
            "already_approved" => translations.already_approved.clone(),
            "already_declined" => translations.already_declined.clone(),
            "request_submitted" => translations.request_submitted.clone(),
            "request_submit_failed" => translations.request_submit_failed.clone(),
            "request_approved" => translations.request_approved.clone(),
            "request_declined" => translations.request_declined.clone(),
            "request_approved_notification" => translations.request_approved_notification.clone(),
            "request_declined_notification" => translations.request_declined_notification.clone(),
            "new_access_request" => translations.new_access_request.clone(),
            "no_pending_requests" => translations.no_pending_requests.clone(),
            "access_request_details" => translations.access_request_details.clone(),
            "unauthorized" => translations.unauthorized.clone(),
            "request_approved_admin" => translations.request_approved_admin.clone(),
            "request_declined_admin" => translations.request_declined_admin.clone(),
            "user_creation_failed" => translations.user_creation_failed.clone(),
            "support_info" => translations.support_info.clone(),
            "statistics" => translations.statistics.clone(),
            "total_users" => translations.total_users.clone(),
            "total_servers" => translations.total_servers.clone(),
            "total_inbounds" => translations.total_inbounds.clone(),
            "pending_requests" => translations.pending_requests.clone(),
            "broadcast_complete" => translations.broadcast_complete.clone(),
            "sent" => translations.sent.clone(),
            "failed" => translations.failed.clone(),
            "configs_coming_soon" => translations.configs_coming_soon.clone(),
            "your_configurations" => translations.your_configurations.clone(),
            "no_configs_available" => translations.no_configs_available.clone(),
            "config_copy_message" => translations.config_copy_message.clone(),
            "config_copied" => translations.config_copied.clone(),
            "config_not_found" => translations.config_not_found.clone(),
            "server_configs_title" => translations.server_configs_title.clone(),
            "subscription_link" => translations.subscription_link.clone(),
            "manage_users" => translations.manage_users.clone(),
            "user_list" => translations.user_list.clone(),
            "user_details" => translations.user_details.clone(),
            "manage_access" => translations.manage_access.clone(),
            "remove_access" => translations.remove_access.clone(),
            "grant_access" => translations.grant_access.clone(),
            "user_info" => translations.user_info.clone(),
            "no_users_found" => translations.no_users_found.clone(),
            "page_info" => translations.page_info.clone(),
            "next_page" => translations.next_page.clone(),
            "prev_page" => translations.prev_page.clone(),
            "back_to_users" => translations.back_to_users.clone(),
            "back_to_menu" => translations.back_to_menu.clone(),
            "access_updated" => translations.access_updated.clone(),
            "access_removed" => translations.access_removed.clone(),
            "access_granted" => translations.access_granted.clone(),
            "error_occurred" => translations.error_occurred.clone(),
            "admin_not_found" => translations.admin_not_found.clone(),
            "request_not_found" => translations.request_not_found.clone(),
            "invalid_request_id" => translations.invalid_request_id.clone(),
            _ => format!("Missing translation: {}", key),
        }
    }

    pub fn format(&self, lang: Language, template: &str, args: &[(&str, &str)]) -> String {
        let mut result = self.get(lang, template);
        for (placeholder, value) in args {
            result = result.replace(&format!("{{{}}}", placeholder), value);
        }
        result
    }

    fn load_english() -> Translations {
        Translations {
            welcome_new_user: "👋 Welcome, {username}!\n\nI'm the OutFleet VPN bot. To get started, you'll need to request access.\n\nClick the button below to submit your access request:".to_string(),
            welcome_back: "👋 Welcome back, {name}!\n\nWhat would you like to do?".to_string(),
            request_pending: "👋 Hello!\n\nYour access request is currently <b>{status}</b>.\n\nRequest submitted: {date}".to_string(),
            request_approved_status: "✅ approved".to_string(),
            request_declined_status: "❌ declined".to_string(),
            get_vpn_access: "🚀 Get VPN Access".to_string(),
            my_configs: "📋 My Configs".to_string(),
            support: "💬 Support".to_string(),
            user_requests: "❔ User Requests".to_string(),
            back: "🔙 Back".to_string(),
            approve: "✅ Approve".to_string(),
            decline: "❌ Decline".to_string(),

            already_pending: "⏳ You already have a pending access request. Please wait for admin review.".to_string(),
            already_approved: "✅ Your access request has already been approved. Use /start to access the main menu.".to_string(),
            already_declined: "❌ Your previous access request was declined. Please contact administrators if you believe this is a mistake.".to_string(),
            request_submitted: "✅ Your access request has been submitted!\n\nAn administrator will review your request soon. You'll receive a notification once it's processed.".to_string(),
            request_submit_failed: "❌ Failed to submit request: {error}".to_string(),

            request_approved: "✅ Request approved".to_string(),
            request_declined: "❌ Request declined".to_string(),
            request_approved_notification: "🎉 <b>Your access request has been approved!</b>\n\nWelcome to OutFleet VPN! Your account has been created.\n\nUser ID: <code>{user_id}</code>\n\nYou can now use /start to access the main menu.".to_string(),
            request_declined_notification: "❌ Your access request has been declined.\n\nIf you believe this is a mistake, please contact the administrators.".to_string(),

            new_access_request: "🔔 <b>New Access Request</b>\n\n👤 Name: {first_name} {last_name}\n🆔 Username: @{username}\n\nUse /requests to review".to_string(),
            no_pending_requests: "No pending access requests".to_string(),
            access_request_details: "❔ <b>Access Request</b>\n\n👤 Name: {full_name}\n🆔 Telegram: {telegram_link}\n📅 Requested: {date}\n\nMessage: {message}".to_string(),
            unauthorized: "❌ You are not authorized to use this command".to_string(),
            request_approved_admin: "✅ Request approved".to_string(),
            request_declined_admin: "❌ Request declined".to_string(),
            user_creation_failed: "❌ Failed to create user account: {error}\n\nPlease try again or contact technical support.".to_string(),

            support_info: "💬 <b>Support Information</b>\n\n📱 <b>How to connect:</b>\n1. Download v2raytun app for Android or iOS from:\n   https://v2raytun.com/\n\n2. Add your subscription link from \"🔗 Subscription Link\" menu\n   OR\n   Add individual server links from \"📋 My Configs\"\n\n3. Connect and enjoy secure VPN!\n\n❓ If you need help, please contact the administrators.".to_string(),
            statistics: "📊 <b>Statistics</b>\n\n👥 Total Users: {users}\n🖥️ Total Servers: {servers}\n📡 Total Inbounds: {inbounds}\n⏳ Pending Requests: {pending}".to_string(),
            total_users: "👥 Total Users".to_string(),
            total_servers: "🖥️ Total Servers".to_string(),
            total_inbounds: "📡 Total Inbounds".to_string(),
            pending_requests: "⏳ Pending Requests".to_string(),

            broadcast_complete: "✅ Broadcast complete\nSent: {sent}\nFailed: {failed}".to_string(),
            sent: "Sent".to_string(),
            failed: "Failed".to_string(),

            configs_coming_soon: "📋 Your configurations will be shown here (coming soon)".to_string(),
            your_configurations: "📋 <b>Your Configurations</b>".to_string(),
            no_configs_available: "📋 No configurations available\n\nYou don't have access to any VPN configurations yet. Please contact an administrator to get access.".to_string(),
            config_copy_message: "📋 <b>{server_name}</b> - {inbound_tag} ({protocol})\n\nConnection URI:".to_string(),
            config_copied: "✅ Configuration copied to clipboard".to_string(),
            config_not_found: "❌ Configuration not found".to_string(),
            server_configs_title: "🖥️ <b>{server_name}</b> - Connection Links".to_string(),

            subscription_link: "🔗 Subscription Link".to_string(),
            manage_users: "👥 Manage Users".to_string(),
            user_list: "👥 User List".to_string(),
            user_details: "👤 User Details".to_string(),
            manage_access: "🔧 Manage Access".to_string(),
            remove_access: "❌ Remove Access".to_string(),
            grant_access: "✅ Grant Access".to_string(),
            user_info: "User Information".to_string(),
            no_users_found: "No users found".to_string(),
            page_info: "Page {page} of {total}".to_string(),
            next_page: "Next →".to_string(),
            prev_page: "← Previous".to_string(),
            back_to_users: "👥 Back to Users".to_string(),
            back_to_menu: "🏠 Main Menu".to_string(),
            access_updated: "✅ Access updated successfully".to_string(),
            access_removed: "❌ Access removed successfully".to_string(),
            access_granted: "✅ Access granted successfully".to_string(),

            error_occurred: "An error occurred".to_string(),
            admin_not_found: "Admin not found".to_string(),
            request_not_found: "Request not found".to_string(),
            invalid_request_id: "Invalid request ID".to_string(),
        }
    }

    fn load_russian() -> Translations {
        Translations {
            welcome_new_user: "👋 Добро пожаловать, {username}!\n\nЯ бот OutFleet VPN. Чтобы начать работу, вам необходимо запросить доступ.\n\nНажмите кнопку ниже, чтобы отправить запрос на доступ:".to_string(),
            welcome_back: "👋 С возвращением, {name}!\n\nЧто вы хотите сделать?".to_string(),
            request_pending: "👋 Привет!\n\nВаш запрос на доступ в настоящее время <b>{status}</b>.\n\nЗапрос отправлен: {date}".to_string(),
            request_approved_status: "✅ одобрен".to_string(),
            request_declined_status: "❌ отклонен".to_string(),
            get_vpn_access: "🚀 Получить доступ к VPN".to_string(),
            my_configs: "📋 Мои конфигурации".to_string(),
            support: "💬 Поддержка".to_string(),
            user_requests: "❔ Запросы пользователей".to_string(),
            back: "🔙 Назад".to_string(),
            approve: "✅ Одобрить".to_string(),
            decline: "❌ Отклонить".to_string(),

            already_pending: "⏳ У вас уже есть ожидающий рассмотрения запрос на доступ. Пожалуйста, дождитесь проверки администратором.".to_string(),
            already_approved: "✅ Ваш запрос на доступ уже был одобрен. Используйте /start для доступа к главному меню.".to_string(),
            already_declined: "❌ Ваш предыдущий запрос на доступ был отклонен. Пожалуйста, свяжитесь с администраторами, если считаете, что это ошибка.".to_string(),
            request_submitted: "✅ Ваш запрос на доступ отправлен!\n\nАдминистратор скоро рассмотрит ваш запрос. Вы получите уведомление после обработки.".to_string(),
            request_submit_failed: "❌ Не удалось отправить запрос: {error}".to_string(),

            request_approved: "✅ Запрос одобрен".to_string(),
            request_declined: "❌ Запрос отклонен".to_string(),
            request_approved_notification: "🎉 <b>Ваш запрос на доступ одобрен!</b>\n\nДобро пожаловать в OutFleet VPN! Ваш аккаунт создан.\n\nID пользователя: <code>{user_id}</code>\n\nТеперь вы можете использовать /start для доступа к главному меню.".to_string(),
            request_declined_notification: "❌ Ваш запрос на доступ отклонен.\n\nЕсли вы считаете, что это ошибка, пожалуйста, свяжитесь с администраторами.".to_string(),

            new_access_request: "🔔 <b>Новый запрос на доступ</b>\n\n👤 Имя: {first_name} {last_name}\n🆔 Имя пользователя: @{username}\n\nИспользуйте /requests для просмотра".to_string(),
            no_pending_requests: "Нет ожидающих запросов на доступ".to_string(),
            access_request_details: "❔ <b>Запрос на доступ</b>\n\n👤 Имя: {full_name}\n🆔 Telegram: {telegram_link}\n📅 Запрошено: {date}\n\nСообщение: {message}".to_string(),
            unauthorized: "❌ У вас нет прав для использования этой команды".to_string(),
            request_approved_admin: "✅ Запрос одобрен".to_string(),
            request_declined_admin: "❌ Запрос отклонен".to_string(),
            user_creation_failed: "❌ Не удалось создать аккаунт пользователя: {error}\n\nПожалуйста, попробуйте еще раз или обратитесь в техническую поддержку.".to_string(),

            support_info: "💬 <b>Информация о поддержке</b>\n\n📱 <b>Как подключиться:</b>\n1. Скачайте приложение v2raytun для Android или iOS с сайта:\n   https://v2raytun.com/\n\n2. Добавьте ссылку подписки из меню \"🔗 Ссылка подписки\"\n   ИЛИ\n   Добавьте отдельные ссылки серверов из \"📋 Мои конфигурации\"\n\n3. Подключайтесь и наслаждайтесь безопасным VPN!\n\n❓ Если нужна помощь, обратитесь к администраторам.".to_string(),

            statistics: "📊 <b>Статистика</b>\n\n👥 Всего пользователей: {users}\n🖥️ Всего серверов: {servers}\n📡 Всего входящих подключений: {inbounds}\n⏳ Ожидающих запросов: {pending}".to_string(),
            total_users: "👥 Всего пользователей".to_string(),
            total_servers: "🖥️ Всего серверов".to_string(),
            total_inbounds: "📡 Всего входящих подключений".to_string(),
            pending_requests: "⏳ Ожидающих запросов".to_string(),

            broadcast_complete: "✅ Рассылка завершена\nОтправлено: {sent}\nНе удалось: {failed}".to_string(),
            sent: "Отправлено".to_string(),
            failed: "Не удалось".to_string(),

            configs_coming_soon: "📋 Ваши конфигурации будут показаны здесь (скоро)".to_string(),
            your_configurations: "📋 <b>Ваши конфигурации</b>".to_string(),
            no_configs_available: "📋 Нет доступных конфигураций\n\nУ вас пока нет доступа к конфигурациям VPN. Пожалуйста, обратитесь к администратору для получения доступа.".to_string(),
            config_copy_message: "📋 <b>{server_name}</b> - {inbound_tag} ({protocol})\n\nСсылка для подключения:".to_string(),
            config_copied: "✅ Конфигурация скопирована в буфер обмена".to_string(),
            config_not_found: "❌ Конфигурация не найдена".to_string(),
            server_configs_title: "🖥️ <b>{server_name}</b> - Ссылки для подключения".to_string(),

            subscription_link: "🔗 Ссылка подписки".to_string(),

            manage_users: "👥 Управление пользователями".to_string(),
            user_list: "👥 Список пользователей".to_string(),
            user_details: "👤 Данные пользователя".to_string(),
            manage_access: "🔧 Управление доступом".to_string(),
            remove_access: "❌ Убрать доступ".to_string(),
            grant_access: "✅ Предоставить доступ".to_string(),
            user_info: "Информация о пользователе".to_string(),
            no_users_found: "Пользователи не найдены".to_string(),
            page_info: "Страница {page} из {total}".to_string(),
            next_page: "Далее →".to_string(),
            prev_page: "← Назад".to_string(),
            back_to_users: "👥 К пользователям".to_string(),
            back_to_menu: "🏠 Главное меню".to_string(),
            access_updated: "✅ Доступ успешно обновлен".to_string(),
            access_removed: "❌ Доступ успешно убран".to_string(),
            access_granted: "✅ Доступ успешно предоставлен".to_string(),

            error_occurred: "Произошла ошибка".to_string(),
            admin_not_found: "Администратор не найден".to_string(),
            request_not_found: "Запрос не найден".to_string(),
            invalid_request_id: "Неверный ID запроса".to_string(),
        }
    }
}
