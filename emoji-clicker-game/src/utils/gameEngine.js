// Format large numbers with suffixes
export const formatNumber = (num) => {
    if (num < 1000) return Math.floor(num).toString();

    const suffixes = ['', 'K', 'M', 'B', 'T', 'Qa', 'Qi', 'Sx', 'Sp', 'Oc', 'No', 'Dc'];
    const tier = Math.floor(Math.log10(Math.abs(num)) / 3);

    if (tier <= 0) return Math.floor(num).toString();
    if (tier >= suffixes.length) {
        // For extremely large numbers, use scientific notation
        return num.toExponential(2);
    }

    const suffix = suffixes[tier];
    const scale = Math.pow(10, tier * 3);
    const scaled = num / scale;

    return scaled.toFixed(2) + suffix;
};

// Format number with commas
export const formatWithCommas = (num) => {
    return Math.floor(num).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
};

// Calculate click value with all multipliers
export const calculateClickValue = (baseValue, upgrades, achievements, prestige) => {
    let value = baseValue;

    // Apply click upgrades
    if (upgrades.clickPower) {
        value *= Math.pow(2, upgrades.clickPower);
    }

    // Apply multiplier upgrades
    if (upgrades.clickMultiplier) {
        value *= (1 + upgrades.clickMultiplier * 0.5);
    }

    // Apply prestige bonuses
    if (prestige.permanentMultiplier) {
        value *= prestige.permanentMultiplier;
    }

    // Apply achievement bonuses
    const achievementBonus = achievements.completed.length * 0.02; // 2% per achievement
    value *= (1 + achievementBonus);

    return value;
};

// Calculate production per second
export const calculateProductionPerSecond = (autoClickers, upgrades, prestige) => {
    let total = 0;

    // Calculate each auto-clicker type
    Object.entries(autoClickers).forEach(([type, data]) => {
        if (data.owned > 0) {
            const baseProduction = data.baseValue * data.owned;
            total += baseProduction;
        }
    });

    // Apply global multipliers
    if (upgrades.productionMultiplier) {
        total *= (1 + upgrades.productionMultiplier * 0.25);
    }

    if (prestige.productionBonus) {
        total *= prestige.productionBonus;
    }

    return total;
};

// Calculate upgrade cost with exponential scaling
export const calculateUpgradeCost = (baseCost, currentLevel, scalingFactor = 1.15) => {
    return Math.floor(baseCost * Math.pow(scalingFactor, currentLevel));
};

// Calculate auto-clicker cost
export const calculateAutoClickerCost = (baseCost, owned) => {
    return Math.floor(baseCost * Math.pow(1.15, owned));
};

// Calculate prestige currency gain
export const calculatePrestigeCurrency = (totalEmojis) => {
    // Prestige formula: sqrt(totalEmojis / 1000000)
    if (totalEmojis < 1000000) return 0;
    return Math.floor(Math.sqrt(totalEmojis / 1000000));
};

// Calculate offline progress
export const calculateOfflineProgress = (productionPerSecond, secondsElapsed, maxOfflineTime = 3600) => {
    // Cap offline time to prevent abuse
    const cappedSeconds = Math.min(secondsElapsed, maxOfflineTime);
    return productionPerSecond * cappedSeconds;
};

// Check if player can afford something
export const canAfford = (cost, currency) => {
    return currency >= cost;
};

// Generate random emoji for particles
export const getRandomEmoji = () => {
    const emojis = ['💎', '✨', '⭐', '🌟', '💫', '🎉', '🎊', '🔥', '💰', '🏆'];
    return emojis[Math.floor(Math.random() * emojis.length)];
};

// Calculate combo multiplier
export const calculateComboMultiplier = (comboCount) => {
    if (comboCount < 5) return 1;
    if (comboCount < 10) return 1.5;
    if (comboCount < 20) return 2;
    if (comboCount < 50) return 3;
    return 5;
};

// Format time duration
export const formatTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
};
