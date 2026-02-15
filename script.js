// Telegram WebApp инициализациясы
const tg = window.Telegram.WebApp;
tg.expand();

// Глобалдык өзгөрмөлөр
let userId = null;
let userBalance = 0;
let userStars = 0;
let userName = '';
let premiumType = 0;

// Краш оюну үчүн өзгөрмөлөр
let crashGameActive = false;
let crashMultiplier = 1.0;
let crashBets = {};
let playerBet = 0;
let hasCashedOut = false;
let crashInterval = null;
let canvas = null;
let ctx = null;
let planeX = 20;
let planeY = 200;

// Дурак оюну үчүн өзгөрмөлөр
let durakGame = null;
let playerCards = [];
let opponentCards = [];
let tableCards = [];
let trumpSuit = '♥';
let currentBet = 1000;

// Турнир үчүн өзгөрмөлөр
let tournamentActive = false;
let tournamentCount = 0;

// Баштапкы инициализация
document.addEventListener('DOMContentLoaded', function() {
    initApp();
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
        if (response.user_id) {
            userId = response.user_id;
            userBalance = response.balance;
            userName = response.display_name || 'Игрок';
            userStars = response.stars || 0;
            premiumType = response.premium_type || 0;
            
            updateUI();
        } else if (response.success !== undefined) {
            handleActionResponse(response);
        }
    } catch (e) {
        console.error('Ошибка обработки данных:', e);
    }
});

// UI жаңыртуу
function updateUI() {
    document.getElementById('balance').textContent = userBalance.toLocaleString() + ' 🪙';
    document.getElementById('profile-name').textContent = userName;
    document.getElementById('profile-id').textContent = 'ID: ' + (userId || '...');
    
    // Күндүк бонусту текшерүү
    checkDailyBonus();
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
    button.textContent = 'Получение...';
    button.disabled = true;
    
    tg.sendData(JSON.stringify({
        action: 'claim_daily_bonus'
    }));
}

// Жылдызча менен сатып алуу
function buyWithStars() {
    const select = document.getElementById('stars-amount');
    const starsAmount = parseInt(select.value);
    
    // Жылдызчанын баасы (1 звезда = 500 монет)
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

// Играларды көрсөтүү
function showGame(game) {
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.game-container').forEach(container => container.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(game + '-game').classList.add('active');
    
    if (game === 'crash') {
        startCrashGame();
    }
}

// Краш оюнунун канвасын инициализациялоо
function initCrashCanvas() {
    canvas = document.getElementById('crashCanvas');
    ctx = canvas.getContext('2d');
    drawCrashScene();
}

// Краш сценасын тартуу
function drawCrashScene() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Горизонт
    ctx.fillStyle = '#87CEEB';
    ctx.fillRect(0, 0, canvas.width, 150);
    ctx.fillStyle = '#FFE4B5';
    ctx.fillRect(0, 150, canvas.width, 150);
    
    // Облака
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.beginPath();
    ctx.arc(100, 50, 30, 0, Math.PI*2);
    ctx.arc(150, 70, 40, 0, Math.PI*2);
    ctx.arc(300, 30, 25, 0, Math.PI*2);
    ctx.fill();
    
    // Самолёттун изи
    ctx.strokeStyle = 'rgba(255,255,255,0.3)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(planeX - 50, planeY);
    ctx.lineTo(planeX, planeY);
    ctx.stroke();
    
    // Самолёттун позициясын жаңыртуу
    const plane = document.getElementById('plane-emoji');
    plane.style.left = planeX + 'px';
    plane.style.bottom = (canvas.height - planeY) + 'px';
}

// Краш оюнун баштоо
function startCrashGame() {
    if (crashInterval) clearInterval(crashInterval);
    
    crashGameActive = true;
    crashMultiplier = 1.0;
    crashBets = {};
    hasCashedOut = false;
    
    document.getElementById('multiplier').textContent = '1.00x';
    document.getElementById('plane-status').textContent = 'Приём ставок...';
    document.getElementById('cashout-btn').disabled = true;
    
    // Ставкаларды көрсөтүү
    updateBetsList();
    
    // 10 секунд күтүп, андан кийин оюнду баштоо
    setTimeout(() => {
        if (crashGameActive) {
            startCrashRound();
        }
    }, 10000);
}

// Краш раундун баштоо
function startCrashRound() {
    if (!crashGameActive) return;
    
    document.getElementById('plane-status').textContent = 'Самолёт взлетает!';
    document.getElementById('cashout-btn').disabled = false;
    
    const crashPoint = 1.5 + Math.random() * 8.5; // 1.5x - 10x
    
    let startTime = Date.now();
    
    crashInterval = setInterval(() => {
        if (!crashGameActive) {
            clearInterval(crashInterval);
            return;
        }
        
        const elapsed = (Date.now() - startTime) / 1000;
        crashMultiplier = 1.0 + elapsed * 0.5; // Секундасына 0.5x
        
        // Самолёттун кыймылы
        planeX = 20 + elapsed * 50;
        planeY = 200 - elapsed * 30;
        
        if (planeY < 50) planeY = 50;
        if (planeX > canvas.width - 50) planeX = canvas.width - 50;
        
        document.getElementById('multiplier').textContent = crashMultiplier.toFixed(2) + 'x';
        drawCrashScene();
        
        // Жарылуу
        if (crashMultiplier >= crashPoint) {
            crashGameActive = false;
            clearInterval(crashInterval);
            
            document.getElementById('plane-status').textContent = 'САМОЛЁТ ВЗОРВАЛСЯ! 💥';
            document.getElementById('multiplier').classList.add('shake');
            document.getElementById('cashout-btn').disabled = true;
            
            // Утулгандарды эсептөө
            setTimeout(() => {
                document.getElementById('multiplier').classList.remove('shake');
                startCrashGame(); // Кийинки раунд
            }, 5000);
        }
    }, 100);
}

// Краш оюнуна ставка коюу
function placeCrashBet() {
    const amount = parseInt(document.getElementById('bet-amount').value);
    
    if (amount < 1000) {
        showNotification('Минимальная ставка: 1000 🪙', 'error');
        return;
    }
    
    if (amount > userBalance) {
        showNotification('Недостаточно монет!', 'error');
        return;
    }
    
    if (!crashGameActive || crashMultiplier > 1.1) {
        showNotification('Ставки принимаются только до взлёта!', 'error');
        return;
    }
    
    tg.sendData(JSON.stringify({
        action: 'crash_bet',
        amount: amount
    }));
    
    playerBet = amount;
    document.getElementById('cashout-btn').disabled = false;
}

// Забрать кылуу
function cashout() {
    if (!crashGameActive || hasCashedOut) return;
    
    tg.sendData(JSON.stringify({
        action: 'crash_cashout'
    }));
    
    hasCashedOut = true;
    document.getElementById('cashout-btn').disabled = true;
}

// Ставкалардын тизмесин жаңыртуу
function updateBetsList() {
    tg.sendData(JSON.stringify({
        action: 'crash_status'
    }));
}

// Дурак оюнун издөө
function findDurakGame() {
    currentBet = parseInt(document.getElementById('durak-bet').value);
    
    if (currentBet < 1000) {
        showNotification('Минимальная ставка: 1000 🪙', 'error');
        return;
    }
    
    if (currentBet > userBalance) {
        showNotification('Недостаточно монет!', 'error');
        return;
    }
    
    document.getElementById('durak-status').textContent = 'Поиск игрока...';
    
    // Дурак оюнун симуляциялоо (реалдуу ишке ашыруу үчүн WebSocket керек)
    setTimeout(() => {
        startDurakGame();
    }, 3000);
}

// Дурак оюнун баштоо
function startDurakGame() {
    document.getElementById('durak-status').textContent = 'Игра началась!';
    
    // Карталарды түзүү
    const suits = ['♥', '♦', '♣', '♠'];
    const values = ['6', '7', '8', '9', '10', 'В', 'Д', 'К', 'Т'];
    
    trumpSuit = suits[Math.floor(Math.random() * suits.length)];
    document.getElementById('trump-card').textContent = trumpSuit;
    
    // Оюнчунун карталары
    playerCards = [];
    for (let i = 0; i < 6; i++) {
        const suit = suits[Math.floor(Math.random() * suits.length)];
        const value = values[Math.floor(Math.random() * values.length)];
        playerCards.push({ suit, value });
    }
    
    // Каршылаштын карталары
    opponentCards = [];
    for (let i = 0; i < 6; i++) {
        const suit = suits[Math.floor(Math.random() * suits.length)];
        const value = values[Math.floor(Math.random() * values.length)];
        opponentCards.push({ suit, value });
    }
    
    renderDurakCards();
}

// Дурак карталарын көрсөтүү
function renderDurakCards() {
    const opponentDiv = document.getElementById('opponent-cards');
    const playerDiv = document.getElementById('player-cards');
    const tableDiv = document.getElementById('table-cards');
    
    opponentDiv.innerHTML = '';
    playerDiv.innerHTML = '';
    tableDiv.innerHTML = '';
    
    // Каршылаштын карталары (жашыруун)
    opponentCards.forEach(() => {
        const card = document.createElement('div');
        card.className = 'card black';
        card.textContent = '🂠';
        opponentDiv.appendChild(card);
    });
    
    // Оюнчунун карталары
    playerCards.forEach((card, index) => {
        const cardDiv = document.createElement('div');
        cardDiv.className = `card ${card.suit === '♥' || card.suit === '♦' ? 'red' : 'black'}`;
        cardDiv.textContent = card.value + card.suit;
        cardDiv.onclick = () => playCard(index);
        playerDiv.appendChild(cardDiv);
    });
}

// Карта ойноо
function playCard(index) {
    const card = playerCards[index];
    tableCards.push(card);
    playerCards.splice(index, 1);
    
    renderDurakCards();
    
    // Каршылаштын жообу (автоматтык)
    setTimeout(() => {
        if (opponentCards.length > 0) {
            const randomIndex = Math.floor(Math.random() * opponentCards.length);
            const opponentCard = opponentCards[randomIndex];
            tableCards.push(opponentCard);
            opponentCards.splice(randomIndex, 1);
            
            renderDurakCards();
            
            // Раундду текшерүү
            checkDurakRound();
        }
    }, 1000);
}

// Дурак раундун текшерүү
function checkDurakRound() {
    if (tableCards.length >= 2) {
        // Эң жогорку картаны табуу
        setTimeout(() => {
            tableCards = [];
            renderDurakCards();
            
            // Карталарды толуктоо
            if (playerCards.length < 6) {
                // Колодадан карта алуу
            }
            if (opponentCards.length < 6) {
                // Колодадан карта алуу
            }
            
            // Оюндун аякташын текшерүү
            if (playerCards.length === 0) {
                document.getElementById('durak-status').textContent = 'Вы выиграли! +' + (currentBet * 2) + ' 🪙';
                userBalance += currentBet * 2;
                updateUI();
            } else if (opponentCards.length === 0) {
                document.getElementById('durak-status').textContent = 'Вы проиграли! -' + currentBet + ' 🪙';
                userBalance -= currentBet;
                updateUI();
            }
        }, 2000);
    }
}

// Турнирге катталуу
function registerTournament() {
    if (premiumType < 2) {
        showNotification('Турнир только для Premium 2!', 'error');
        return;
    }
    
    tg.sendData(JSON.stringify({
        action: 'tournament_register'
    }));
    
    tournamentCount++;
    document.getElementById('tournament-count').textContent = tournamentCount + '/150';
    showNotification('Вы зарегистрированы на турнир!', 'success');
}

// Ботту ачуу
function openBot() {
    tg.openTelegramLink('https://t.me/SQUIIDGAMES_BOT');
}

// Жоопторду иштетүү
function handleActionResponse(response) {
    if (response.success) {
        if (response.bonus) {
            userBalance += response.bonus;
            updateUI();
            showNotification('Бонус получен: +' + response.bonus + ' 🪙', 'success');
        } else if (response.coins) {
            userBalance += response.coins;
            updateUI();
            showNotification('Покупка успешна: +' + response.coins + ' 🪙', 'success');
        } else if (response.result) {
            // Краш оюнунун жообу
            if (response.result.includes('забрали')) {
                showNotification('Вы забрали: ' + response.result, 'success');
            }
        }
    } else {
        if (response.error === 'Already claimed') {
            showNotification('Вы уже получили бонус сегодня!', 'error');
            document.querySelector('#daily-bonus .bonus-button').textContent = 'Уже получено';
        } else {
            showNotification('Ошибка: ' + response.error, 'error');
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
        animation: slideDown 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Краш оюнунун статусун автоматтык түрдө жаңыртуу
setInterval(() => {
    if (document.getElementById('crash-game').classList.contains('active')) {
        tg.sendData(JSON.stringify({
            action: 'crash_status'
        }));
    }
}, 2000);



