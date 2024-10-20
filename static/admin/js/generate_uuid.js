// static/admin/js/generate_uuid.js

function generateUUID() {
    let uuid = '';
    const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    const length = 10;

    for (let i = 0; i < length; i++) {
        const randomIndex = Math.floor(Math.random() * characters.length);
        uuid += characters[randomIndex];
    }

    const hashField = document.getElementById('id_hash');
    if (hashField) {
        hashField.value = uuid;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    generateUUID();
});
