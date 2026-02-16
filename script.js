// Telegram Web App инициализация
let tg = window.Telegram.WebApp;
tg.expand();

let userId = null;
let userBalance = 0;
let username = '';

// Краш оюну үчүн өзгөрмөлөр
let crashActive = false;
let currentMultiplier = 1.0;
let crashInterval = null;
let roundTimer = null;
let roundTime = 10;
let userBet = null;
let cashoutEnabled = false;
let allBets = [];

// API дареги
const API_URL = 'https://islomav4.beget.tech'; // Өзүңдүн домениңди кой

// Башкы функциялар
document.addEventListener('DOMContentLoaded', function() {
    // Telegramдан колдонуучу маалыматын алуу
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        userId = tg.initDataUnsafe.user.id;
        username = tg.initDataUnsafe.user.first_name || tg.initDataUnsafe.user.username || 'User';
        
        loadUserBalance();
        loadTopUsers();
        loadTournamentStatus();
    } else {
        // Тест үчүн
        userId = 123456789;
        username = 'Test User';
        loadUserBalance();
    }
    
    // Балансты 5 секунд сайын жаңыртуу
    setInterval(loadUserBalance, 5000);
});

// Балансты жүктөө
async function loadUserBalance() {
    if (!userId) return;
    
    try {
        const response = await fetch(`${API_URL}/api/get_balance/${userId}`);
        const data = await response.json();
        
        if (data.success) {
            userBalance = data.balance;
            updateAllBalances();
        }
    } catch (error) {
        console.error('Баланс жүктөөдө ката:', error);
    }
}

// Бардык жерлерде балансты жаңыртуу
function updateAllBalances() {
    const balanceElements = document.querySelectorAll('.balance');
    balanceElements.forEach(el => {
        el.textContent = `${userBalance.toLocaleString()} 🪙`;
    });
}

// Экрандарды өзгөртүү
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
    
    // Экранга жараша маалыматтарды жүктөө
    if (screenId === 'bonus') {
        loadBonusGrid();
    } else if (screenId === 'top') {
        loadTopUsers();
    } else if (screenId === 'tournament') {
        loadTournamentStatus();
    } else if (screenId === 'profile') {
        loadProfile();
    } else if (screenId === 'crash') {
        initCrashGame();
    }
}

// Бонус системасы (60 канал)
function loadBonusGrid() {
    // 1-катар: Бекер (20 канал)
    const freeGrid = document.getElementById('free-bonus-grid');
    freeGrid.innerHTML = '';
    
    for (let i = 0; i < 20; i++) {
        const channel = document.createElement('div');
        channel.className = 'bonus-channel free';
        channel.innerHTML = `
            <div class="channel-icon">📢</div>
            <div class="channel-name">Канал ${i+1}</div>
            <div class="bonus-amount">6k-20k</div>
        `;
        channel.onclick = () => claimBonus('free', i);
        freeGrid.appendChild(channel);
    }
    
    // 2-катар: Акчалуу 1 (20 канал)
    const paid1Grid = document.getElementById('paid1-bonus-grid');
    paid1Grid.innerHTML = '';
    
    for (let i = 0; i < 20; i++) {
        const channel = document.createElement('div');
        channel.className = 'bonus-channel paid1';
        channel.innerHTML = `
            <div class="channel-icon">💎</div>
            <div class="channel-name">VIP ${i+1}</div>
            <div class="bonus-amount">20k-40k</div>
        `;
        channel.onclick = () => claimBonus('paid1', i);
        paid1Grid.appendChild(channel);
    }
    
    // 3-катар: Акчалуу 2 (20 канал)
    const paid2Grid = document.getElementById('paid2-bonus-grid');
    paid2Grid.innerHTML = '';
    
    for (let i = 0; i < 20; i++) {
        const channel = document.createElement('div');
        channel.className = 'bonus-channel paid2';
        channel.innerHTML = `
            <div class="channel-icon">👑</div>
            <div class="channel-name">ULTRA ${i+1}</div>
            <div class="bonus-amount">200k-1M</div>
        `;
        channel.onclick = () => claimBonus('paid2', i);
        paid2Grid.appendChild(channel);
    }
    
    // localStorage'дан алынгандарды белгилөө
    loadClaimedChannels();
}

// Каналга подписка жана бонус алуу
async function claimBonus(type, index) {
    const channelLink = 'https://t.me/hbjkhboygg'; // Бардык каналдар бир эле ссылка
    
    // Каналды ачуу
    window.open(channelLink, '_blank');
    
    // Колдонуучу подписка болгонун текшерүү (5 секунд күтөбүз)
    setTimeout(async () => {
        try {
            const response = await fetch(`${API_URL}/api/add_bonus`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    type: type,
                    channel_index: index
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                userBalance = data.new_balance;
                updateAllBalances();
                
                // Бул каналды бүткөн деп белгилөө
                markChannelClaimed(type, index);
                
                tg.showAlert(`🎁 Вы получили ${data.amount.toLocaleString()} 🪙!`);
            } else {
                tg.showAlert('❌ Ошибка получения бонуса');
            }
        } catch (error) {
            console.error('Бонус алууда ката:', error);
            tg.showAlert('❌ Ошибка соединения');
        }
    }, 5000);
}

// Бүткөн каналдарды белгилөө
function markChannelClaimed(type, index) {
    let claimed = JSON.parse(localStorage.getItem(`bonus_${userId}`) || '{}');
    if (!claimed[type]) claimed[type] = [];
    claimed[type].push(index);
    localStorage.setItem(`bonus_${userId}`, JSON.stringify(claimed));
    
    // UI'да белгилөө
    loadClaimedChannels();
}

function loadClaimedChannels() {
    const claimed = JSON.parse(localStorage.getItem(`bonus_${userId}`) || '{}');
    
    document.querySelectorAll('.bonus-channel').forEach((channel, i) => {
        channel.classList.remove('completed');
    });
    
    if (claimed.free) {
        claimed.free.forEach(index => {
            const channels = document.querySelectorAll('.bonus-channel.free');
            if (channels[index]) channels[index].classList.add('completed');
        });
    }
    
    if (claimed.paid1) {
        claimed.paid1.forEach(index => {
            const channels = document.querySelectorAll('.bonus-channel.paid1');
            if (channels[index]) channels[index].classList.add('completed');
        });
    }
    
    if (claimed.paid2) {
        claimed.paid2.forEach(index => {
            const channels = document.querySelectorAll('.bonus-channel.paid2');
            if (channels[index]) channels[index].classList.add('completed');
        });
    }
}

// Топ 10 колдонуучуну жүктөө
async function loadTopUsers() {
    try {
        const response = await fetch(`${API_URL}/api/get_top_users`);
        const data = await response.json();
        
        if (data.success) {
            const topList = document.getElementById('top-list');
            topList.innerHTML = '';
            
            data.users.forEach((user, index) => {
                const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `${index+1}`;
                
                const item = document.createElement('div');
                item.className = 'top-item';
                item.innerHTML = `
                    <div class="top-position">${medal}</div>
                    <div class="top-user">${user.name}</div>
                    <div class="top-balance">${user.balance.toLocaleString()} 🪙</div>
                `;
                topList.appendChild(item);
            });
        }
    } catch (error) {
        console.error('Топ жүктөөдө ката:', error);
    }
}

// Турнир статусун жүктөө
async function loadTournamentStatus() {
    try {
        const response = await fetch(`${API_URL}/api/get_tournament_registrations`);
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('tournament-players').textContent = `${data.count}/150`;
            
            // Premium текшерүү
            const premiumResponse = await fetch(`${API_URL}/api/get_user_premium?user_id=${userId}`);
            const premiumData = await premiumResponse.json();
            
            if (premiumData.success && premiumData.premium_type >= 2) {
                document.getElementById('tournament-register-btn').disabled = false;
            } else {
                document.getElementById('tournament-register-btn').disabled = true;
                document.getElementById('tournament-register-btn').textContent = 'Требуется Premium 2';
            }
        }
    } catch (error) {
        console.error('Турнир статусун жүктөөдө ката:', error);
    }
}

// Турнирге катталуу
async function registerTournament() {
    try {
        const response = await fetch(`${API_URL}/api/register_tournament`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, username: username })
        });
        
        const data = await response.json();
        
        if (data.success) {
            tg.showAlert('✅ Вы зарегистрированы на турнир!');
            loadTournamentStatus();
        } else {
            tg.showAlert('❌ ' + data.message);
        }
    } catch (error) {
        console.error('Катталууда ката:', error);
        tg.showAlert('❌ Ошибка соединения');
    }
}

// Профиль жүктөө
async function loadProfile() {
    try {
        const response = await fetch(`${API_URL}/api/get_user_info/${userId}`);
        const data = await response.json();
        
        if (data.success) {
            const user = data.user;
            
            document.getElementById('profile-name').textContent = user.display_name || user.username || user.first_name;
            document.getElementById('profile-id').textContent = `ID: ${user.id}`;
            document.getElementById('profile-balance-value').textContent = user.balance.toLocaleString();
            document.getElementById('profile-tournaments').textContent = user.tournament_wins;
            
            if (user.premium_type > 0) {
                document.getElementById('profile-premium').textContent = `Premium ${user.premium_type}`;
            } else {
                document.getElementById('profile-premium').textContent = 'Нет';
            }
        }
    } catch (error) {
        console.error('Профиль жүктөөдө ката:', error);
    }
}

// КРАШ ОЮНУ (Самолет)
function initCrashGame() {
    // Эски интервалдарды тазалоо
    if (crashInterval) clearInterval(crashInterval);
    if (roundTimer) clearInterval(roundTimer);
    
    crashActive = false;
    currentMultiplier = 1.0;
    cashoutEnabled = false;
    userBet = null;
    allBets = [];
    
    document.getElementById('multiplier').textContent = 'x1.00';
    document.getElementById('game-status').textContent = 'Ожидание ставок...';
    document.getElementById('cashout-btn').disabled = true;
    document.getElementById('place-bet-btn').disabled = false;
    document.getElementById('bet-amount').disabled = false;
    
    // Жасалма ставкалар (тест үчүн)
    allBets = [
        { user: 'Игрок1', amount: 1000, multiplier: 1.5 },
        { user: 'Игрок2', amount: 2000, multiplier: 2.3 },
        { user: 'Игрок3', amount: 500, multiplier: 3.1 }
    ];
    
    updateBetsList();
    
    // Раундду баштоо
    startRoundTimer();
}

function startRoundTimer() {
    roundTime = 10;
    document.getElementById('round-timer').textContent = `Следующий раунд через: ${roundTime}с`;
    
    roundTimer = setInterval(() => {
        roundTime--;
        document.getElementById('round-timer').textContent = `Следующий раунд через: ${roundTime}с`;
        
        if (roundTime <= 0) {
            clearInterval(roundTimer);
            startCrashRound();
        }
    }, 1000);
}

function startCrashRound() {
    crashActive = true;
    currentMultiplier = 1.0;
    document.getElementById('game-status').textContent = 'Самолет летит!';
    document.getElementById('cashout-btn').disabled = false;
    
    // Ставка коюуну өчүрүү
    document.getElementById('place-bet-btn').disabled = true;
    document.getElementById('bet-amount').disabled = true;
    
    // Мультипликаторду өстүрүү
    crashInterval = setInterval(() => {
        if (!crashActive) return;
        
        // Мультипликаторду өстүрүү (кокус сан)
        currentMultiplier += 0.1;
        document.getElementById('multiplier').textContent = `x${currentMultiplier.toFixed(2)}`;
        
        // Кокус жарылуу (30% мүмкүнчүлүк)
        if (Math.random() < 0.03) {
            crash();
        }
    }, 500);
}

function crash() {
    crashActive = false;
    clearInterval(crashInterval);
    
    document.getElementById('game-status').textContent = '💥 САМОЛЕТ ВЗОРВАЛСЯ!';
    document.getElementById('cashout-btn').disabled = true;
    
    // Уттургандарды эсептөө
    allBets.forEach(bet => {
        if (!bet.cashedOut && bet.user === username) {
            // Уттурду
            updateBalance(-bet.amount, 'Проигрыш в краш');
        }
    });
    
    // 10 секунддан кийин кайра баштоо
    setTimeout(() => {
        startRoundTimer();
    }, 10000);
}

function placeCrashBet() {
    if (!crashActive && roundTime > 0) {
        const amount = parseInt(document.getElementById('bet-amount').value);
        
        if (amount < 1000) {
            tg.showAlert('❌ Минимальная ставка: 1000 монет!');
            return;
        }
        
        if (amount > userBalance) {
            tg.showAlert('❌ Недостаточно монет!');
            return;
        }
        
        userBet = {
            user: username,
            amount: amount,
            multiplier: 0,
            cashedOut: false
        };
        
        allBets.push(userBet);
        updateBetsList();
        
        // Балансты убактылуу азайтуу
        userBalance -= amount;
        updateAllBalances();
        
        tg.showAlert(`✅ Ставка ${amount} принята!`);
    } else {
        tg.showAlert('❌ Сейчас нельзя делать ставку!');
    }
}

function cashout() {
    if (crashActive && userBet && !userBet.cashedOut) {
        const winAmount = Math.floor(userBet.amount * currentMultiplier);
        
        userBet.cashedOut = true;
        userBet.multiplier = currentMultiplier;
        
        // Утушту кошуу
        userBalance += winAmount;
        updateAllBalances();
        updateBalance(winAmount, 'Выигрыш в краш');
        
        updateBetsList();
        
        tg.showAlert(`✅ Вы выиграли ${winAmount.toLocaleString()} 🪙! (x${currentMultiplier.toFixed(2)})`);
    }
}

function updateBetsList() {
    const betsDiv = document.getElementById('active-bets');
    betsDiv.innerHTML = '';
    
    allBets.forEach(bet => {
        const betItem = document.createElement('div');
        betItem.className = 'bet-item';
        
        let status = '';
        if (bet.cashedOut) {
            status = `✅ x${bet.multiplier.toFixed(2)}`;
        } else if (!crashActive) {
            status = '⏳';
        } else {
            status = `x${currentMultiplier.toFixed(2)}`;
        }
        
        betItem.innerHTML = `
            <span class="user">${bet.user}</span>
            <span class="amount">${bet.amount.toLocaleString()} 🪙</span>
            <span class="multiplier">${status}</span>
        `;
        betsDiv.appendChild(betItem);
    });
}

// Балансты серверге жаңыртуу
async function updateBalance(amount, description) {
    try {
        await fetch(`${API_URL}/api/update_balance`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                amount: amount,
                description: description
            })
        });
    } catch (error) {
        console.error('Баланс жаңыртууда ката:', error);
    }
}

// ДУРАК ОЮНУ (тесттик версия)
function findDurakGame() {
    tg.showAlert('🔍 Поиск игры... (скоро)');
}

function createDurakGame() {
    tg.showAlert('🎮 Создание игры... (скоро)');
}
