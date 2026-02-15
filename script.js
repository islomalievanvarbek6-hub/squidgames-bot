// Telegram WebApp инициализациясы
const tg = window.Telegram.WebApp;
tg.expand();

// Глобалдык өзгөрмөләр
let userId = null;
let userBalance = 0;
let userStars = 0;
let userName = '';
let premiumType = 0;

// Краш оюну үчүн өзгөрмөләр
let crashGameActive = false;
let crashMultiplier = 1.0;
let crashBets = {};
let playerBet = 0;
let hasCashedOut = false;
let crashInterval = null;

// Баштапкы инициализация
document.addEventListener('DOMContentLoaded', function() {
    initCrashCanvas();
    loadUserData();
});

// Колдонуучунун маалыматтарын жүктөө
function loadUserData() {
    tg.sendData(JSON.stringify({
        action: 'get_user'
    }));
}

// Telegram'дан келген жоопторду угуу
tg.onEvent('webAppData', function(data) {
    try {
        const response = JSON.parse(data);
        console.log('Ответ от бота:', response);
        
        if (response.user_id) {
            userId = response.user_id;
            userBalance = response.balance;
            userName = response.display_name || 'Игрок';
            userStars = response.stars || 0;
            premiumType = response.premium_type || 0;
            
            updateUI();
            checkDailyBonus();
        } else if (response.success !== undefined) {
            handleActionResponse(response);
        }
    } catch (e) {
        console.error('Ошибка обработки данных:', e);
    }
});

// UI жаңыртуу
function updateUI() {
    const balanceElement = document.getElementById('balance');
    if (balanceElement) {
        balanceElement.textContent = userBalance.toLocaleString() + ' 🪙';
    }
    
    const profileName = document.getElementById('profile-name');
    if (profileName) {
        profileName.textContent = userName;
    }
    
    const profileId = document.getElementById('profile-id');
    if (profileId) {
        profileId.textContent = 'ID: ' + (userId || '...');
    }
}

// Күндүк бонусту текшерүү
function checkDailyBonus() {
    tg.sendData(JSON.stringify({
        action: 'get_daily_bonus'
    }));
}

// Күндүк бонусту алуу
function claimDailyBonus() {
    const button = document.querySelector('#daily-bonus .bonus-button');
    if (button) {
        button.textContent = 'Получение...';
        button.disabled = true;
    }
    
    tg.sendData(JSON.stringify({
        action: 'claim_daily_bonus'
    }));
}

// Жылдызча менен сатып алуу
function buyWithStars() {
    const select = document.getElementById('stars-amount');
    if (!select) return;
    
    const starsAmount = parseInt(select.value);
    const coinAmount = starsAmount * 500;
    
    tg.sendData(JSON.stringify({
        action: 'buy_with_stars',
        stars: starsAmount,
        coins: coinAmount
    }));
}

// Тариф сатып алуу
function buyTariff(stars, coins) {
    if (userStars < stars) {
        showNotification('Недостаточно звёзд!', 'error');
        return;
    }
    
    tg.sendData(JSON.stringify({
        action: 'buy_with_stars',
        stars: stars,
        coins: coins
    }));
}

// Жоопторду иштетүү
function handleActionResponse(response) {
    if (response.success) {
        if (response.bonus) {
            userBalance += response.bonus;
            updateUI();
            showNotification('Бонус получен: +' + response.bonus + ' 🪙', 'success');
            
            const button = document.querySelector('#daily-bonus .bonus-button');
            if (button) {
                button.textContent = 'Получено';
                button.disabled = true;
            }
        } else if (response.coins) {
            userBalance += response.coins;
            updateUI();
            showNotification('Покупка успешна: +' + response.coins + ' 🪙', 'success');
        }
    } else {
        if (response.error === 'Already claimed') {
            showNotification('Вы уже получили бонус сегодня!', 'error');
            const button = document.querySelector('#daily-bonus .bonus-button');
            if (button) {
                button.textContent = 'Уже получено';
                button.disabled = true;
            }
        } else {
            showNotification('Ошибка: ' + response.error, 'error');
            
            const button = document.querySelector('#daily-bonus .bonus-button');
            if (button) {
                button.textContent = 'Получить';
                button.disabled = false;
            }
        }
    }
}

// Билдирүү көрсөтүү
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'success' ? '#4caf50' : '#f44336'};
        color: white;
        padding: 15px 30px;
        border-radius: 50px;
        font-weight: bold;
        z-index: 1000;
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Краш оюнунун канвасын инициализациялоо
function initCrashCanvas() {
    const canvas = document.getElementById('crashCanvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#87CEEB';
    ctx.fillRect(0, 0, canvas.width, 150);
    ctx.fillStyle = '#FFE4B5';
    ctx.fillRect(0, 150, canvas.width, 150);
}

// Играларды көрсөтүү
function showGame(game) {
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.game-container').forEach(container => container.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(game + '-game').classList.add('active');
}

