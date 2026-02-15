let tg = window.Telegram.WebApp;
tg.expand();

// ============ КОНФИГУРАЦИЯ ============
const REQUIRED_CHANNEL = "@SQUIIDGAMES_CHANNEL"; // КАНАЛ АТЫН ӨЗГӨРТҮҢҮЗ!

// ============ ГЛОБАЛДЫК ӨЗГӨРМӨЛӨР ============
let userData = {
    id: tg.initDataUnsafe?.user?.id || 0,
    username: tg.initDataUnsafe?.user?.username || 'player',
    balance: 5000,        // Баланс МОНЕТА менен
    premium: 0,
    lastBonus: {},
    checkedChannel: false
};

// Оюндар үчүн өзгөрмөлөр
let crashGame = {
    active: false,
    multiplier: 1.00,
    bets: [],
    playerBet: null,
    interval: null,
    timer: null,
    roundTimer: 10
};

let cardsGame = {
    active: false,
    deck: [],
    playerCards: [],
    opponentCards: [],
    tableCards: [],
    trump: null,
    bet: 0
};

let tournament = {
    players: []
};

// ============ БАШТАЛКЫ ИНИЦИАЛИЗАЦИЯ ============
document.addEventListener('DOMContentLoaded', function() {
    loadUserData();
    updateBalance();
    startCrashGame();
    loadTournamentPlayers();
});

// ============ Telegram API ============
function sendToBot(action, data) {
    tg.sendData(JSON.stringify({
        action: action,
        data: data
    }));
}

// ============ КОЛДОНУУЧУ МААЛЫМАТТАРЫ ============
function loadUserData() {
    let saved = localStorage.getItem('userData');
    if(saved) {
        try {
            userData = JSON.parse(saved);
        } catch(e) {}
    }
    updateBalance();
}

function saveUserData() {
    localStorage.setItem('userData', JSON.stringify(userData));
}

function updateBalance() {
    let balanceSpan = document.getElementById('userBalance');
    if(balanceSpan) balanceSpan.textContent = userData.balance;
}

// ============ ТАБДЫ АЛМАШТЫРУУ ============
function showTab(tabName) {
    // Бардык табтарды жашыруу
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Бардык кнопкалардын активдүүлүгүн алуу
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Тандалган табты көрсөтүү
    let selectedTab = document.getElementById(tabName + 'Tab');
    if(selectedTab) selectedTab.classList.add('active');
    
    // Тандалган кнопканы активдештирүү
    let selectedBtn = document.querySelector(`[onclick="showTab('${tabName}')"]`);
    if(selectedBtn) selectedBtn.classList.add('active');
}

// ============ БОНУС СИСТЕМАСЫ ============
async function checkChannelSubscription() {
    try {
        tg.sendData(JSON.stringify({
            action: 'check_channel',
            channel: REQUIRED_CHANNEL
        }));
    } catch(e) {
        console.log(e);
    }
}

function claimBonus(type, amount) {
    let today = new Date().toDateString();
    
    // Бүгүн бонус алдыбы?
    if(userData.lastBonus[type] === today) {
        tg.showAlert('❌ Бонус уже получен сегодня!');
        return;
    }
    
    // Каналды текшерүү (биринчи жолу)
    if(!userData.checkedChannel) {
        checkChannelSubscription();
        userData.checkedChannel = true;
        tg.showAlert('📢 Подпишитесь на канал и нажмите "Получить" еще раз');
        return;
    }
    
    // Бонус кошуу
    userData.balance += amount;
    userData.lastBonus[type] = today;
    
    updateBalance();
    saveUserData();
    
    sendToBot('bonus_claimed', {type, amount});
    tg.showAlert(`✅ Получено: ${amount} 🪙`);
    
    // Каналды ачуу (сунушталат)
    tg.openTelegramLink(REQUIRED_CHANNEL);
}

function subscribePremium(level) {
    tg.openTelegramLink(`https://t.me/SQUIIDGAMES_KASSA?start=premium_${level}`);
}

function buyStars(amount) {
    tg.openTelegramLink(`https://t.me/SQUIIDGAMES_KASSA?start=buy_stars_${amount}`);
}

// ============ CRASH ОЮНУ ============
function playCrash() {
    showTab('crash');
    startCrashGame();
}

function startCrashGame() {
    crashGame.interval = setInterval(updateCrashGame, 100);
    startNewRound();
}

function startNewRound() {
    crashGame.active = false;
    crashGame.multiplier = 1.00;
    crashGame.playerBet = null;
    
    let multiplierEl = document.getElementById('multiplier');
    if(multiplierEl) multiplierEl.textContent = '1.00x';
    
    let placeBtn = document.getElementById('placeBetBtn');
    if(placeBtn) placeBtn.disabled = false;
    
    let cashoutBtn = document.getElementById('cashoutBtn');
    if(cashoutBtn) cashoutBtn.disabled = true;
    
    // Таймер
    crashGame.roundTimer = 10;
    if(crashGame.timer) clearInterval(crashGame.timer);
    
    crashGame.timer = setInterval(() => {
        crashGame.roundTimer--;
        let timerEl = document.getElementById('timer');
        if(timerEl) timerEl.textContent = `Следующий раунд через: ${crashGame.roundTimer}с`;
        
        if(crashGame.roundTimer <= 0) {
            clearInterval(crashGame.timer);
            startCrashRound();
        }
    }, 1000);
}

function startCrashRound() {
    crashGame.active = true;
    let placeBtn = document.getElementById('placeBetBtn');
    if(placeBtn) placeBtn.disabled = true;
    
    let crashPoint = 1 + Math.random() * 5;
    let currentMultiplier = 1.00;
    
    if(crashGame.interval) clearInterval(crashGame.interval);
    
    crashGame.interval = setInterval(() => {
        if(!crashGame.active) return;
        
        currentMultiplier += 0.01;
        crashGame.multiplier = currentMultiplier;
        
        let multiplierEl = document.getElementById('multiplier');
        if(multiplierEl) multiplierEl.textContent = currentMultiplier.toFixed(2) + 'x';
        
        if(currentMultiplier >= crashPoint) {
            crash();
        }
    }, 100);
}

function crash() {
    crashGame.active = false;
    clearInterval(crashGame.interval);
    
    crashGame.bets = [];
    updateBetsList();
    addToHistory(`💥 Крах на ${crashGame.multiplier.toFixed(2)}x`);
    
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
    
    let amountInput = document.getElementById('betAmount');
    let amount = parseInt(amountInput ? amountInput.value : 1000);
    
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
    
    crashGame.playerBet = {
        userId: userData.id,
        username: userData.username,
        amount: amount,
        multiplier: crashGame.multiplier,
        cashedOut: false
    };
    
    crashGame.bets.push(crashGame.playerBet);
    
    let cashoutBtn = document.getElementById('cashoutBtn');
    if(cashoutBtn) cashoutBtn.disabled = false;
    
    updateBetsList();
    sendToBot('bet_placed', {amount, game: 'crash'});
}

function cashOut() {
    if(!crashGame.active || !crashGame.playerBet || crashGame.playerBet.cashedOut) return;
    
    let winAmount = Math.floor(crashGame.playerBet.amount * crashGame.multiplier);
    
    userData.balance += winAmount;
    updateBalance();
    
    crashGame.playerBet.cashedOut = true;
    crashGame.playerBet.winAmount = winAmount;
    
    addToHistory(`✅ ${userData.username} забрал ${winAmount} 🪙 (${crashGame.multiplier.toFixed(2)}x)`);
    
    let cashoutBtn = document.getElementById('cashoutBtn');
    if(cashoutBtn) cashoutBtn.disabled = true;
    
    updateBetsList();
    sendToBot('cashed_out', {
        amount: crashGame.playerBet.amount,
        multiplier: crashGame.multiplier,
        win: winAmount
    });
}

function updateBetsList() {
    let betsList = document.getElementById('betsList');
    if(!betsList) return;
    
    betsList.innerHTML = '';
    
    crashGame.bets.forEach(bet => {
        let betItem = document.createElement('div');
        betItem.className = 'bet-item';
        
        if(bet.cashedOut) {
            betItem.innerHTML = `<span>✅ ${bet.username}</span> <span>${bet.winAmount} 🪙</span>`;
        } else {
            betItem.innerHTML = `<span>${bet.username}</span> <span>${bet.amount} 🪙</span>`;
        }
        
        betsList.appendChild(betItem);
    });
}

function addToHistory(text) {
    let history = document.getElementById('betHistory');
    if(!history) return;
    
    let historyItem = document.createElement('div');
    historyItem.className = 'history-item';
    historyItem.textContent = text;
    
    history.appendChild(historyItem);
    
    if(history.children.length > 10) {
        history.removeChild(history.children[1]);
    }
}

function updateCrashGame() {
    let playersCount = document.getElementById('playersCount');
    if(playersCount) {
        playersCount.textContent = `Игроков: ${crashGame.bets.length}`;
    }
    
    let plane = document.getElementById('plane');
    if(plane && crashGame.active) {
        plane.style.animation = `fly ${3 / crashGame.multiplier}s linear infinite`;
    }
}

// ============ КАРТА ОЮНУ (ДУРАК) ============
function playCards() {
    showTab('cards');
    if(!cardsGame.active) {
        startCardsGame();
    }
}

function startCardsGame() {
    let betInput = document.getElementById('cardsBet');
    let bet = parseInt(betInput ? betInput.value : 1000);
    
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
    
    cardsGame.trump = cardsGame.deck[0].suit;
}

function dealCards() {
    cardsGame.playerCards = cardsGame.deck.slice(0, 6);
    cardsGame.opponentCards = cardsGame.deck.slice(6, 12);
    cardsGame.tableCards = [];
    
    displayCards();
}

function displayCards() {
    let opponentDiv = document.getElementById('opponentCards');
    if(opponentDiv) {
        opponentDiv.innerHTML = '';
        for(let i = 0; i < cardsGame.opponentCards.length; i++) {
            let card = document.createElement('div');
            card.className = 'card';
            card.textContent = '🂠';
            opponentDiv.appendChild(card);
        }
    }
    
    let playerDiv = document.getElementById('playerCards');
    if(playerDiv) {
        playerDiv.innerHTML = '';
        cardsGame.playerCards.forEach((card, index) => {
            let cardEl = document.createElement('div');
            cardEl.className = `card ${card.color}`;
            cardEl.textContent = card.value + card.suit;
            cardEl.onclick = () => playSelectedCard(index);
            playerDiv.appendChild(cardEl);
        });
    }
    
    let tableDiv = document.getElementById('tableCards');
    if(tableDiv) {
        tableDiv.innerHTML = '';
        cardsGame.tableCards.forEach(card => {
            let cardEl = document.createElement('div');
            cardEl.className = `card ${card.color}`;
            cardEl.textContent = card.value + card.suit;
            tableDiv.appendChild(cardEl);
        });
    }
}

function playSelectedCard(index) {
    if(!cardsGame.active) return;
    
    let card = cardsGame.playerCards[index];
    cardsGame.tableCards.push(card);
    cardsGame.playerCards.splice(index, 1);
    
    setTimeout(() => {
        if(cardsGame.opponentCards.length > 0) {
            let opponentCard = cardsGame.opponentCards[0];
            cardsGame.tableCards.push(opponentCard);
            cardsGame.opponentCards.shift();
        }
        
        displayCards();
        
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
    
    cardsGame.opponentCards.push(...cardsGame.tableCards);
    cardsGame.tableCards = [];
    displayCards();
}

// ============ ТУРНИР ============
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
    let saved = localStorage.getItem('tournament');
    if(saved) {
        try {
            tournament = JSON.parse(saved);
        } catch(e) {}
    }
    updateTournamentDisplay();
}

function updateTournamentDisplay() {
    let playersCount = document.querySelector('.players-count');
    if(playersCount) {
        playersCount.textContent = `Зарегистрировано: ${tournament.players.length}/150`;
    }
    
    let playersList = document.getElementById('playersList');
    if(playersList) {
        playersList.innerHTML = '';
        tournament.players.forEach((player, index) => {
            let playerItem = document.createElement('div');
            playerItem.className = 'player-item';
            playerItem.textContent = `${index + 1}. ${player.username}`;
            playersList.appendChild(playerItem);
        });
    }
}git add script.js
git commit -m "Fixed script.js with coins and games"
git push origin main

git add script.js
git commit -m "Fixed script.js with coins and games"
git push origin main









