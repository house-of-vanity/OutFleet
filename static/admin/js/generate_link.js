// static/admin/js/generate_uuid.js

function generateLink(button) {
    let row = button.closest('tr');
    let inputField = row.querySelector('input[name$="link"]');

    if (inputField) {
        inputField.value = generateRandomString(16);
    }
}

function generateRandomString(length) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

