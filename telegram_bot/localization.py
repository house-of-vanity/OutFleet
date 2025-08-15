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
        'buttons': {
            'access': "🌍 Get access",
            'all_in_one': "🌍 All-in-one",
            'back': "⬅️ Back",
            'group_prefix': "Group: ",
            'request_access': "🔑 Request Access"
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
        'buttons': {
            'access': "🌍 Получить VPN",
            'all_in_one': "🌍 Все в одном",
            'back': "⬅️ Назад",
            'group_prefix': "Группа: ",
            'request_access': "🔑 Запросить доступ"
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