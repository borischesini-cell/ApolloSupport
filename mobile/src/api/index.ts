import AsyncStorage from '@react-native-async-storage/async-storage';

export const API_URL = 'https://support.ultimate.net.ar/api';

const getAuthHeaders = async () => {
    const token = await AsyncStorage.getItem('token');
    return {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : ''
    };
};

export const login = async (email: string, pass: string) => {
    try {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', pass);

        const response = await fetch(`${API_URL}/token`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) return null;
        const data = await response.json();
        await AsyncStorage.setItem('token', data.access_token);
        await AsyncStorage.setItem('user', JSON.stringify(data.usuario));
        return data;
    } catch (err) {
        console.error("Login Error:", err);
        return null;
    }
};

export const getActiveCentinelas = async () => {
    try {
        const response = await fetch(`${API_URL}/centinelas/activos`, {
            headers: await getAuthHeaders()
        });
        if (!response.ok) return {};
        return await response.json();
    } catch {
        return {};
    }
};

export const getAlerts = async () => {
    try {
        const response = await fetch(`${API_URL}/centinelas/alertas`, {
            headers: await getAuthHeaders()
        });
        if (!response.ok) return {};
        return await response.json();
    } catch {
        return {};
    }
};

export const getTickets = async () => {
    try {
        const response = await fetch(`${API_URL}/tickets/`, {
            headers: await getAuthHeaders()
        });
        if (!response.ok) return [];
        return await response.json();
    } catch {
        return [];
    }
};

export const registerPushToken = async (token: string) => {
    try {
        const response = await fetch(`${API_URL}/users/push-token`, {
            method: 'POST',
            headers: await getAuthHeaders(),
            body: JSON.stringify({ token })
        });
        return response.ok;
    } catch {
        return false;
    }
};
