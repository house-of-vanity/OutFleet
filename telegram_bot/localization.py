"""
Message localization for Telegram bot
"""
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Translation dictionaries
MESSAGES = {
    'en': {
        'help_text': "📋 Welcome! Use buttons below to navigate.\n\n📊 Access - View your VPN subscriptions\n\nFor support contact administrator.",
        'access_request_created': "Access request created, please wait.",
        'new_user_welcome': "Welcome! To get access to VPN services, please request access using the button below.",
        'pending_request_msg': "Your access request is pending approval. Please wait for administrator to review it.",
        'choose_subscription': "**Choose subscription option:**",
        'all_in_one_desc': "🌍 **All-in-one** - Get all subscriptions in one link",
        'group_desc': "**Group** - Get specific group subscription",
        'select_option': "Select an option below:",
        'no_subscriptions': "❌ You don't have any active Xray subscriptions.\n\nPlease contact administrator for access.",
        'group_subscription': "**Group: {group_name}**",
        'subscription_link': "**🔗 Subscription Link:**",
        'web_portal': "**🌐 Web Portal:**",
        'tap_to_copy': "_Tap the subscription link to copy it. Use it in your Xray client._",
        'all_in_one_subscription': "🌍 **All-in-one Subscription**",
        'your_access_includes': "**Your Access Includes:**",
        'universal_subscription_link': "**🔗 Universal Subscription Link:**",
        'all_subscriptions_note': "_This link includes all your active subscriptions. Tap to copy._",
        'error_loading_subscriptions': "❌ Error loading subscriptions. Please try again later.",
        'error_loading_group': "❌ Error loading group subscription. Please try again later.",
        'received_content': "Received your {message_type}. An administrator will review it.",
        'approval_notification': "✅ Access approved!",
        'content_types': {
            'photo': 'photo',
            'document': 'document', 
            'voice': 'voice',
            'video': 'video',
            'content': 'content'
        },
        'guide_title': "📖 **VPN Setup Guide**",
        'guide_choose_platform': "Select your device platform:",
        'web_portal_description': "_Web portal shows your access list on one convenient page with some statistics._",
        'servers_in_group': "🔒 **Servers in group:**",
        
        # Admin messages
        'admin_new_request_notification': "🔔 **New Access Request**\n\n👤 **User:** {user_info}\n📱 **Telegram:** {telegram_info}\n📅 **Date:** {date}\n\n💬 **Message:** {message}",
        'admin_access_requests_title': "📋 **Pending Access Requests**",
        'admin_no_pending_requests': "✅ No pending access requests",
        'admin_request_item': "👤 **{user_info}**\n📅 {date}\n💬 _{message_preview}_",
        'admin_choose_subscription_groups': "📦 **Choose Subscription Groups for {user_info}:**\n\nSelect groups to assign to this user:",
        'admin_approval_success': "✅ **Request Approved!**\n\n👤 User: {user_info}\n📦 Groups: {groups}\n\nUser has been notified and given access.",
        'admin_rejection_success': "❌ **Request Rejected**\n\n👤 User: {user_info}\n\nUser has been notified.",
        'admin_request_already_processed': "⚠️ This request has already been processed by another admin.",
        'admin_error_processing': "❌ Error processing request: {error}",
        
        'android_guide': "🤖 **Android Setup Guide**\n\n**Step 1: Install the app**\nDownload V2RayTUN from Google Play:\nhttps://play.google.com/store/apps/details?id=com.v2raytun.android\n\n**Step 2: Add subscription**\n• Open the app\n• Tap the **+** button in the top right corner\n• Paste your subscription link from the bot\n• The app will automatically load all VPN servers\n\n**Step 3: Connect**\n• Choose a server from the list\n• Tap **Connect**\n• All your traffic will now go through VPN\n\n**💡 Useful settings:**\n• In settings, enable direct access for banking apps and local sites\n• You can choose specific apps to use VPN while others use direct connection\n\n**🔄 If VPN stops working:**\nTap the refresh icon next to the server list to update your subscription.",
        'ios_guide': " **iOS Setup Guide**\n\n**Step 1: Install the app**\nDownload V2RayTUN from App Store:\nhttps://apps.apple.com/us/app/v2raytun/id6476628951\n\n**Step 2: Add subscription**\n• Open the app\n• Tap the **+** button in the top right corner\n• Paste your subscription link from the bot\n• The app will automatically load all VPN servers\n\n**Step 3: Connect**\n• Choose a server from the list\n• Tap **Connect**\n• All your traffic will now go through VPN\n\n**⚠️ Note for iOS users:**\nCurrently, only VLESS protocol works reliably on iOS. Other protocols may have connectivity issues.\n\n**💡 Useful settings:**\n• In settings, enable direct access for banking apps and local sites to improve performance\n\n**🔄 If VPN stops working:**\nTap the refresh icon next to the server list to update your subscription.",
        'buttons': {
            'access': "🌍 Get access",
            'guide': "📖 Guide",
            'android': "🤖 Android",
            'ios': " iOS",
            'web_portal': "🌐 Web Portal",
            'all_in_one': "🌍 All-in-one",
            'back': "⬅️ Back",
            'group_prefix': "Group: ",
            'request_access': "🔑 Request Access",
            # Admin buttons
            'access_requests': "📋 Access Requests",
            'approve': "✅ Approve",
            'reject': "❌ Reject",
            'details': "👁 Details",
            'confirm_approval': "✅ Confirm Approval",
            'confirm_rejection': "❌ Confirm Rejection",
            'cancel': "🚫 Cancel"
        }
    },
    'ru': {
        'help_text': "📋 Добро пожаловать! Используйте кнопки ниже для навигации.\n\n📊 Доступ - Просмотр VPN подписок\n\nДля поддержки обратитесь к администратору.",
        'access_request_created': "Запрос на доступ создан, ожидайте.",
        'new_user_welcome': "Добро пожаловать! Для получения доступа к VPN сервисам, пожалуйста запросите доступ с помощью кнопки ниже.",
        'pending_request_msg': "Ваш запрос на доступ ожидает одобрения. Пожалуйста, дождитесь рассмотрения администратором.",
        'choose_subscription': "**Выберите вариант подписки:**",
        'all_in_one_desc': "🌍 **Все в одном** - Получить все подписки в одной ссылке",
        'group_desc': "**Группа** - Получить подписку на группу",
        'select_option': "Выберите вариант ниже:",
        'no_subscriptions': "❌ У вас нет активных Xray подписок.\n\nОбратитесь к администратору для получения доступа.",
        'group_subscription': "**Группа: {group_name}**",
        'subscription_link': "**🔗 **",
        'web_portal': "**🌐 Веб-портал пользователя:**",
        'tap_to_copy': "_Нажмите на ссылку чтобы скопировать. Используйте в вашем Xray клиенте как подписку._",
        'all_in_one_subscription': "🌍 **Подписка «Все в одном»**",
        'your_access_includes': "**Ваш доступ включает:**",
        'universal_subscription_link': "**🔗 Универсальная ссылка на подписку:**",
        'all_subscriptions_note': "_Эта ссылка включает все ваши активные подписки. Нажмите чтобы скопировать._",
        'error_loading_subscriptions': "❌ Ошибка загрузки подписок. Попробуйте позже.",
        'error_loading_group': "❌ Ошибка загрузки подписки группы. Попробуйте позже.",
        'received_content': "Получен ваш {message_type}. Администратор его рассмотрит.",
        'approval_notification': "✅ Доступ одобрен!",
        'content_types': {
            'photo': 'фото',
            'document': 'документ',
            'voice': 'голосовое сообщение',
            'video': 'видео',
            'content': 'контент'
        },
        'guide_title': "📖 **Руководство по настройке VPN**",
        'guide_choose_platform': "Выберите платформу вашего устройства:",
        'web_portal_description': "_Веб-портал показывает список ваших доступов на одной удобной странице с некоторой статистикой._",
        'servers_in_group': "🔒 **Серверы в группе:**",
        
        # Admin messages
        'admin_new_request_notification': "🔔 **Новый запрос на доступ**\n\n👤 **Пользователь:** {user_info}\n📱 **Telegram:** {telegram_info}\n📅 **Дата:** {date}\n\n💬 **Сообщение:** {message}",
        'admin_access_requests_title': "📋 **Ожидающие запросы на доступ**",
        'admin_no_pending_requests': "✅ Нет ожидающих запросов на доступ",
        'admin_request_item': "👤 **{user_info}**\n📅 {date}\n💬 _{message_preview}_",
        'admin_choose_subscription_groups': "📦 **Выберите группы подписки для {user_info}:**\n\nВыберите группы для назначения этому пользователю:",
        'admin_approval_success': "✅ **Запрос одобрен!**\n\n👤 Пользователь: {user_info}\n📦 Группы: {groups}\n\nПользователь уведомлен и получил доступ.",
        'admin_rejection_success': "❌ **Запрос отклонен**\n\n👤 Пользователь: {user_info}\n\nПользователь уведомлен.",
        'admin_request_already_processed': "⚠️ Этот запрос уже обработан другим администратором.",
        'admin_error_processing': "❌ Ошибка обработки запроса: {error}",
        
        'android_guide': "🤖 **Руководство для Android**\n\n**Шаг 1: Установите приложение**\nСкачайте V2RayTUN из Google Play:\nhttps://play.google.com/store/apps/details?id=com.v2raytun.android\n\n**Шаг 2: Добавьте подписку**\n• Откройте приложение\n• Нажмите кнопку **+** в правом верхнем углу\n• Вставьте ссылку на подписку из бота\n• Приложение автоматически загрузит список VPN серверов\n\n**Шаг 3: Подключитесь**\n• Выберите сервер из списка\n• Нажмите **Подключиться**\n• Весь ваш трафик будет проходить через VPN\n\n**💡 Полезные настройки:**\n• В настройках включите прямой доступ для банковских приложений и местных сайтов\n• Вы можете выбрать конкретные приложения для использования VPN, в то время как остальные будут работать напрямую\n\n**🔄 Если VPN перестал работать:**\nНажмите иконку обновления рядом со списком серверов для обновления подписки.",
        'ios_guide': " **Руководство для iOS**\n\n**Шаг 1: Установите приложение**\nСкачайте V2RayTUN из App Store:\nhttps://apps.apple.com/us/app/v2raytun/id6476628951\n\n**Шаг 2: Добавьте подписку**\n• Откройте приложение\n• Нажмите кнопку **+** в правом верхнем углу\n• Вставьте ссылку на подписку из бота\n• Приложение автоматически загрузит список VPN серверов\n\n**Шаг 3: Подключитесь**\n• Выберите сервер из списка\n• Нажмите **Подключиться**\n• Весь ваш трафик будет проходить через VPN\n\n**⚠️ Важно для пользователей iOS:**\nВ настоящее время на iOS стабильно работает только протокол VLESS. Другие протоколы могут иметь проблемы с подключением.\n\n**💡 Полезные настройки:**\n• В настройках включите прямой доступ для банковских приложений и местных сайтов для улучшения производительности\n\n**🔄 Если VPN перестал работать:**\nНажмите иконку обновления рядом со списком серверов для обновления подписки.",
        'buttons': {
            'access': "🌍 Получить VPN",
            'guide': "📖 Гайд",
            'android': "🤖 Android",
            'ios': " iOS",
            'web_portal': "🌐 Веб-портал",
            'all_in_one': "🌍 Все в одном",
            'back': "⬅️ Назад",
            'group_prefix': "Группа: ",
            'request_access': "🔑 Запросить доступ",
            # Admin buttons
            'access_requests': "📋 Запросы на доступ",
            'approve': "✅ Одобрить",
            'reject': "❌ Отклонить",
            'details': "👁 Подробности",
            'confirm_approval': "✅ Подтвердить одобрение",
            'confirm_rejection': "❌ Подтвердить отклонение",
            'cancel': "🚫 Отмена"
        }
    }
}

class MessageLocalizer:
    """Class for bot message localization"""
    
    @staticmethod
    def get_user_language(telegram_user) -> str:
        """
        Determines user language from Telegram language_code
        
        Args:
            telegram_user: Telegram user object
            
        Returns:
            str: Language code ('ru' or 'en')
        """
        if not telegram_user:
            return 'en'
        
        language_code = getattr(telegram_user, 'language_code', None)
        
        if not language_code:
            return 'en'
        
        # Support Russian and English
        if language_code.startswith('ru'):
            return 'ru'
        else:
            return 'en'
    
    @staticmethod
    def get_message(key: str, language: str = 'en', **kwargs) -> str:
        """
        Gets localized message
        
        Args:
            key: Message key
            language: Language code
            **kwargs: Formatting parameters
            
        Returns:
            str: Localized message
        """
        try:
            # Fallback to English if language not supported
            if language not in MESSAGES:
                language = 'en'
                
            message = MESSAGES[language].get(key, MESSAGES['en'].get(key, f"Missing translation: {key}"))
            
            # Format with parameters
            if kwargs:
                try:
                    message = message.format(**kwargs)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Error formatting message {key}: {e}")
                    
            return message
            
        except Exception as e:
            logger.error(f"Error getting message {key} for language {language}: {e}")
            return f"Error: {key}"
    
    @staticmethod
    def get_button_text(button_key: str, language: str = 'en') -> str:
        """
        Gets button text
        
        Args:
            button_key: Button key
            language: Language code
            
        Returns:
            str: Button text
        """
        try:
            if language not in MESSAGES:
                language = 'en'
                
            buttons = MESSAGES[language].get('buttons', {})
            return buttons.get(button_key, MESSAGES['en']['buttons'].get(button_key, button_key))
            
        except Exception as e:
            logger.error(f"Error getting button text {button_key} for language {language}: {e}")
            return button_key
    
    @staticmethod
    def get_content_type_name(content_type: str, language: str = 'en') -> str:
        """
        Gets localized content type name
        
        Args:
            content_type: Content type
            language: Language code
            
        Returns:
            str: Localized name
        """
        try:
            if language not in MESSAGES:
                language = 'en'
                
            content_types = MESSAGES[language].get('content_types', {})
            return content_types.get(content_type, content_type)
            
        except Exception as e:
            logger.error(f"Error getting content type {content_type} for language {language}: {e}")
            return content_type

# Convenience functions for use in code
def get_localized_message(telegram_user, message_key: str, **kwargs) -> str:
    """Get localized message for user"""
    language = MessageLocalizer.get_user_language(telegram_user)
    return MessageLocalizer.get_message(message_key, language, **kwargs)

def get_localized_button(telegram_user, button_key: str) -> str:
    """Get localized button text for user"""
    language = MessageLocalizer.get_user_language(telegram_user)
    return MessageLocalizer.get_button_text(button_key, language)

def get_user_language(telegram_user) -> str:
    """Get user language"""
    return MessageLocalizer.get_user_language(telegram_user)