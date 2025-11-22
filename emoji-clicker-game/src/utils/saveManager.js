const SAVE_KEY = 'emoji_clicker_save';
const AUTO_SAVE_INTERVAL = 10000; // 10 seconds

// Save game state to localStorage
export const saveGame = (state) => {
    try {
        const saveData = {
            ...state,
            lastSaved: Date.now(),
            version: '1.0.0'
        };
        localStorage.setItem(SAVE_KEY, JSON.stringify(saveData));
        return true;
    } catch (error) {
        console.error('Failed to save game:', error);
        return false;
    }
};

// Load game state from localStorage
export const loadGame = () => {
    try {
        const savedData = localStorage.getItem(SAVE_KEY);
        if (!savedData) return null;

        const parsed = JSON.parse(savedData);

        // Migration logic can go here
        // if (parsed.version === '1.0.0') { ... }

        return parsed;
    } catch (error) {
        console.error('Failed to load game:', error);
        return null;
    }
};

// Export save data as string
export const exportSave = () => {
    const saveData = localStorage.getItem(SAVE_KEY);
    if (!saveData) return null;

    return btoa(saveData); // Encode to base64
};

// Import save data from string
export const importSave = (saveString) => {
    try {
        const decoded = atob(saveString); // Decode from base64
        const parsed = JSON.parse(decoded);

        // Validate save data
        if (!parsed.version) {
            throw new Error('Invalid save data');
        }

        localStorage.setItem(SAVE_KEY, decoded);
        return true;
    } catch (error) {
        console.error('Failed to import save:', error);
        return false;
    }
};

// Clear save data
export const deleteSave = () => {
    try {
        localStorage.removeItem(SAVE_KEY);
        return true;
    } catch (error) {
        console.error('Failed to delete save:', error);
        return false;
    }
};

// Check if save exists
export const hasSave = () => {
    return localStorage.getItem(SAVE_KEY) !== null;
};

// Get time since last save
export const getTimeSinceLastSave = () => {
    const savedData = loadGame();
    if (!savedData || !savedData.lastSaved) return 0;

    return Math.floor((Date.now() - savedData.lastSaved) / 1000);
};

export { AUTO_SAVE_INTERVAL };
