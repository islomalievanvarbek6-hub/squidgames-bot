let tg = window.Telegram.WebApp;
tg.expand();

// Глобальные переменные
let userData = {
    id: tg.initDataUnsafe?.user?.id || 0,
    username: tg.initDataUnsafe?.user?.username || 'player',
    balance: 5000,
    stars: 0,
    premium: 0,
    lastBonus: {}
};

let crashGame = {
    active: false,
    multiplier: 1.00,
    bets: [],
    playerBet: null,
    interval: null,
    timer: null,
    roundTimer: 10
};

let tournament = {
    players: [],
    active: false
};

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    loadUserData();
    updateBalance();
    startCrashGame();
    loadTournamentPlayers();
    
    // Автоматическая покупка звезд каждую минуту
    setInterval(autoBuyStars, 60000);
});

// Telegram API
function sendToBot(action, data) {
    tg.sendData(JSON.stringify({
        action: action,
        data: data
    }));
}

// Загрузка данных пользователя
function loadUserData() {
    // Здесь должен быть запрос к боту через Telegram API
    let saved = localStorage.getItem('userData');
    if(saved) {
        userData = JSON.parse(saved);
    }
    updateBalance();
}

// Обновление баланса
function updateBalance() {
    document.getElementById('userBalance').textContent = userData.balance;
    document.getElementById('userStars').textContent = userData.stars;
}

// Табы
function showTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    document.querySelector(`[onclick="showTab('${tabName}')"]`).classList.add('active');
    document.getElementById(tabName + 'Tab').classList.add('active');
}

// Бонус система
function claimBonus(type, amount) {
    let today = new Date().toDateString();
    
    if(userData.lastBonus[type] === today) {
        tg.showAlert('❌ Бонус уже получен сегодня!');
        return;
    }
    
    // Проверка подписки
    if(type === 'premium1' && userData.premium < 1) {
        tg.showAlert('❌ Требуется Premium 1!');
        return;
    }
    
    if(type === 'premium2' && userData.premium < 2) {
        tg.showAlert('❌ Требуется Premium 2!');
        return;
    }
    
    userData.balance += amount;
    userData.lastBonus[type] = today;
    
    updateBalance();
    saveUserData();
    
    sendToBot('bonus_claimed', {type, amount});
    tg.showAlert(`✅ Получено: ${amount} 🪙`);
}

// Подписка на Premium
function subscribePremium(level) {
    let starsNeeded = level === 1 ? 699 : 1999;
    
    if(userData.stars < starsNeeded) {
        tg.showAlert(`❌ Недостаточно звезд! Нужно: ${starsNeeded} ⭐`);
        return;
    }
    
    userData.stars -= starsNeeded;
    userData.premium = level;
    
    updateBalance();
    saveUserData();
    
    sendToBot('premium_purchased', {level});
    tg.showAlert(`✅ Premium ${level} активирован!`);
}

// Покупка звезд
function buyStars(amount) {
    tg.openTelegramLink(`https://t.me/SQUIIDGAMES_KASSA?start=buy_stars_${amount}`);
}

// Автоматическая покупка звезд (каждую минуту)
function autoBuyStars() {
    let chance = Math.random();
    
    if(chance < 0.3) { // 30% шанс
        let starAmount = [699, 1999][Math.floor(Math.random() * 2)];
        userData.stars += starAmount;
        updateBalance();
        saveUserData();
        
        console.log(`Авто-покупка: +${starAmount} ⭐`);
    }
}

// Crash Game
function startCrashGame() {
    crashGame.interval = setInterval(updateCrashGame, 100);
    startNewRound();
}

function startNewRound() {
    crashGame.active = false;
    crashGame.multiplier = 1.00;
    crashGame.playerBet = null;
    
    document.getElementById('multiplier').textContent = '1.00x';
    document.getElementById('placeBetBtn').disabled = false;
    document.getElementById('cashoutBtn').disabled = true;
    
    // Таймер до следующего раунда
    crashGame.roundTimer = 10;
    crashGame.timer = setInterval(() => {
        crashGame.roundTimer--;
        document.getElementById('timer').textContent = `Следующий раунд через: ${crashGame.roundTimer}с`;
        
        if(crashGame.roundTimer <= 0) {
            clearInterval(crashGame.timer);
            startCrashRound();
        }
    }, 1000);
}

function startCrashRound() {
    crashGame.active = true;
    document.getElementById('placeBetBtn').disabled = true;
    
    // Обновление мультипликатора
    let crashPoint = 1 + Math.random() * 5; // Случайная точка краха (1-6x)
    let currentMultiplier = 1.00;
    
    crashGame.interval = setInterval(() => {
        if(!crashGame.active) return;
        
        currentMultiplier += 0.01;
        crashGame.multiplier = currentMultiplier;
        document.getElementById('multiplier').textContent = currentMultiplier.toFixed(2) + 'x';
        
        // Крах
        if(currentMultiplier >= crashPoint) {
            crash();
        }
    }, 100);
}

function crash() {
    crashGame.active = false;
    clearInterval(crashGame.interval);
    
    // Обработка ставок
    crashGame.bets.forEach(bet => {
        if(!bet.cashedOut) {
            // Проигрыш
            addToHistory(`❌ ${bet.username} проиграл ${bet.amount} 🪙`);
        }
    });
    
    crashGame.bets = [];
    updateBetsList();
    
    // Добавление в историю
    addToHistory(`💥 Крах на ${crashGame.multiplier.toFixed(2)}x`);
    
    // Новый раунд
    setTimeout(startNewRound, 3000);
}

function placeBet() {
    if(!crashGame.active) {
        tg.showAlert('❌ Раунд еще не начался!');
        return;
    }
    
    if(crashGame.playerBet) {
        tg.showAlert('❌ Вы уже сделали ставку!');
        return;
    }
    
    let amount = parseInt(document.getElementById('betAmount').value);
    
    if(amount < 100) {
        tg.showAlert('❌ Минимальная ставка: 100 🪙');
        return;
    }
    
    if(amount > userData.balance) {
        tg.showAlert('❌ Недостаточно монет!');
        return;
    }
    
    userData.balance -= amount;
    updateBalance();
    
    let bet = {
        userId: userData.id,
        username: userData.username,
        amount: amount,
        multiplier: crashGame.multiplier,
        cashedOut: false
    };
    
    crashGame.playerBet = bet;
    crashGame.bets.push(bet);
    
    document.getElementById('cashoutBtn').disabled = false;
    updateBetsList();
    
    sendToBot('bet_placed', {amount, game: 'crash'});
}

function cashOut() {
    if(!crashGame.active || !crashGame.playerBet || crashGame.playerBet.cashedOut) {
        return;
    }
    
    let winAmount = Math.floor(crashGame.playerBet.amount * crashGame.multiplier);
    
    userData.balance += winAmount;
    updateBalance();
    
    crashGame.playerBet.cashedOut = true;
    crashGame.playerBet.winAmount = winAmount;
    
    addToHistory(`✅ ${userData.username} забрал ${winAmount} 🪙 (${crashGame.multiplier.toFixed(2)}x)`);
    
    document.getElementById('cashoutBtn').disabled = true;
    updateBetsList();
    
    sendToBot('cashed_out', {
        amount: crashGame.playerBet.amount,
        multiplier: crashGame.multiplier,
        win: winAmount
    });
}

function updateBetsList() {
    let betsList = document.getElementById('betsList');
    betsList.innerHTML = '';
    
    crashGame.bets.forEach(bet => {
        let betItem = document.createElement('div');
        betItem.className = 'bet-item';
        
        if(bet.cashedOut) {
            betItem.innerHTML = `
                <span>✅ ${bet.username}</span>
                <span>${bet.winAmount} 🪙 (${bet.multiplier.toFixed(2)}x)</span>
            `;
        } else {
            betItem.innerHTML = `
                <span>${bet.username}</span>
                <span>${bet.amount} 🪙</span>
            `;
        }
        
        betsList.appendChild(betItem);
    });
}

function addToHistory(text) {
    let history = document.getElementById('betHistory');
    let historyItem = document.createElement('div');
    historyItem.className = 'history-item';
    historyItem.textContent = text;
    
    history.appendChild(historyItem);
    
    if(history.children.length > 10) {
        history.removeChild(history.children[1]);
    }
}

// Cards Game (Дурак)
let cardsGame = {
    active: false,
    deck: [],
    playerCards: [],
    opponentCards: [],
    tableCards: [],
    trump: null,
    bet: 0
};

function startCardsGame() {
    let bet = parseInt(document.getElementById('cardsBet').value);
    
    if(bet < 100) {
        tg.showAlert('❌ Минимальная ставка: 100 🪙');
        return;
    }
    
    if(bet > userData.balance) {
        tg.showAlert('❌ Недостаточно монет!');
        return;
    }
    
    userData.balance -= bet;
    cardsGame.bet = bet;
    cardsGame.active = true;
    
    updateBalance();
    initCardsDeck();
    dealCards();
    
    sendToBot('cards_game_started', {bet});
}

function initCardsDeck() {
    let suits = ['♠', '♣', '♥', '♦'];
    let values = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
    
    cardsGame.deck = [];
    
    for(let suit of suits) {
        for(let value of values) {
            cardsGame.deck.push({
                value: value,
                suit: suit,
                color: (suit === '♥' || suit === '♦') ? 'red' : 'black'
            });
        }
    }
    
    // Перемешивание
    for(let i = cardsGame.deck.length - 1; i > 0; i--) {
        let j = Math.floor(Math.random() * (i + 1));
        [cardsGame.deck[i], cardsGame.deck[j]] = [cardsGame.deck[j], cardsGame.deck[i]];
    }
    
    // Выбор козыря
    cardsGame.trump = cardsGame.deck[0].suit;
}

function dealCards() {
    cardsGame.playerCards = cardsGame.deck.slice(0, 6);
    cardsGame.opponentCards = cardsGame.deck.slice(6, 12);
    cardsGame.tableCards = [];
    
    displayCards();
}

function displayCards() {
    // Карты противника
    let opponentDiv = document.getElementById('opponentCards');
    opponentDiv.innerHTML = '';
    
    for(let i = 0; i < cardsGame.opponentCards.length; i++) {
        let card = document.createElement('div');
        card.className = 'card';
        card.textContent = '🂠';
        opponentDiv.appendChild(card);
    }
    
    // Карты игрока
    let playerDiv = document.getElementById('playerCards');
    playerDiv.innerHTML = '';
    
    cardsGame.playerCards.forEach((card, index) => {
        let cardEl = document.createElement('div');
        cardEl.className = `card ${card.color}`;
        cardEl.textContent = card.value + card.suit;
        cardEl.onclick = () => playSelectedCard(index);
        playerDiv.appendChild(cardEl);
    });
    
    // Карты на столе
    let tableDiv = document.getElementById('tableCards');
    tableDiv.innerHTML = '';
    
    cardsGame.tableCards.forEach(card => {
        let cardEl = document.createElement('div');
        cardEl.className = `card ${card.color}`;
        cardEl.textContent = card.value + card.suit;
        tableDiv.appendChild(cardEl);
    });
}

function playSelectedCard(index) {
    if(!cardsGame.active) return;
    
    let card = cardsGame.playerCards[index];
    
    // Логика игры в дурака (упрощенная)
    cardsGame.tableCards.push(card);
    cardsGame.playerCards.splice(index, 1);
    
    // Противник бьет
    setTimeout(() => {
        if(cardsGame.opponentCards.length > 0) {
            let opponentCard = cardsGame.opponentCards[0];
            cardsGame.tableCards.push(opponentCard);
            cardsGame.opponentCards.shift();
        }
        
        displayCards();
        
        // Проверка конца игры
        if(cardsGame.playerCards.length === 0) {
            winCardsGame();
        }
    }, 500);
}

function winCardsGame() {
    let winAmount = cardsGame.bet * 2;
    userData.balance += winAmount;
    cardsGame.active = false;
    
    updateBalance();
    tg.showAlert(`✅ Вы выиграли! +${winAmount} 🪙`);
    
    sendToBot('cards_game_won', {win: winAmount});
}

function takeCards() {
    if(!cardsGame.active) return;
    
    cardsGame.playerCards.push(...cardsGame.tableCards);
    cardsGame.tableCards = [];
    
    displayCards();
}

function passCards() {
    if(!cardsGame.active) return;
    
    // Противник берет карты
    cardsGame.opponentCards.push(...cardsGame.tableCards);
    cardsGame.tableCards = [];
    
    displayCards();
}

// Турнир
function registerTournament() {
    if(userData.premium < 2) {
        tg.showAlert('❌ Требуется Premium 2!');
        return;
    }
    
    if(tournament.players.length >= 150) {
        tg.showAlert('❌ Турнир заполнен!');
        return;
    }
    
    tournament.players.push({
        id: userData.id,
        username: userData.username
    });
    
    updateTournamentDisplay();
    sendToBot('tournament_register', {});
    
    tg.showAlert('✅ Вы зарегистрированы на турнир!');
}

function loadTournamentPlayers() {
    // Загрузка из localStorage
    let saved = localStorage.getItem('tournament');
    if(saved) {
        tournament = JSON.parse(saved);
    }
    
    updateTournamentDisplay();
}

function updateTournamentDisplay() {
    document.querySelector('.players-count').textContent = `Зарегистрировано: ${tournament.players.length}/150`;
    
    let playersList = document.getElementById('playersList');
    playersList.innerHTML = '';
    
    tournament.players.forEach((player, index) => {
        let playerItem = document.createElement('div');
        playerItem.className = 'player-item';
        playerItem.textContent = `${index + 1}. ${player.username}`;
        playersList.appendChild(playerItem);
    });
}

// Сохранение данных
function saveUserData() {
    localStorage.setItem('userData', JSON.stringify(userData));
    localStorage.setItem('tournament', JSON.stringify(tournament));
}

// Обновление игры (для анимации)
function updateCrashGame() {
    // Обновление счетчика игроков
    document.getElementById('playersCount').textContent = `Игроков: ${crashGame.bets.length}`;
    
    // Анимация самолета
    let plane = document.getElementById('plane');
    if(crashGame.active) {
        plane.style.animation = `fly ${3 / crashGame.multiplier}s linear infinite`;
    }
}
