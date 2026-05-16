import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator, Alert } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as LocalAuthentication from 'expo-local-authentication';
import { login } from '../api';
import { Sparkles, ArrowRight, Fingerprint } from 'lucide-react-native';

export default function LoginScreen({ navigation }: any) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [isBiometricSupported, setIsBiometricSupported] = useState(false);
    const [hasSavedToken, setHasSavedToken] = useState(false);

    useEffect(() => {
        checkBiometrics();
    }, []);

    const checkBiometrics = async () => {
        try {
            const hasHardware = await LocalAuthentication.hasHardwareAsync();
            const isEnrolled = await LocalAuthentication.isEnrolledAsync();
            const token = await AsyncStorage.getItem('token');
            
            const supported = hasHardware && isEnrolled;
            setIsBiometricSupported(supported);
            setHasSavedToken(!!token);

            // Si es compatible y hay un token guardado, solicitar huella automáticamente
            if (supported && token) {
                setTimeout(() => {
                    handleBiometricAuth();
                }, 500);
            }
        } catch (err) {
            console.error("Error comprobando biometría:", err);
        }
    };

    const handleBiometricAuth = async () => {
        try {
            const result = await LocalAuthentication.authenticateAsync({
                promptMessage: 'Acceso Biométrico para ApolloSupport',
                cancelLabel: 'Cancelar',
                disableDeviceFallback: false,
            });

            if (result.success) {
                navigation.replace('Main');
            }
        } catch (err) {
            console.error("Biometric authentication error:", err);
            Alert.alert("Error", "Ocurrió un error al autenticar con huella dactilar.");
        }
    };

    const handleLogin = async () => {
        if (!email || !password) return;
        setLoading(true);
        const result = await login(email, password);
        setLoading(false);
        if (result) {
            navigation.replace('Main');
        } else {
            Alert.alert("Error", "Credenciales incorrectas o servidor no disponible.");
        }
    };

    return (
        <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.container}
        >
            <View className="flex-1 justify-center px-8 bg-white">
                <View style={styles.logoContainer}>
                    <View style={styles.logoIcon}>
                        <Text style={styles.logoLetter}>A</Text>
                    </View>
                    <Text style={styles.logoText}>
                        Apollo<Text style={{ color: '#f59e0b' }}>Support</Text>
                    </Text>
                </View>

                <View style={styles.formCard}>
                    <Text style={styles.title}>Motor de Asistencia</Text>
                    <Text style={styles.subtitle}>Inicie sesión para acceder al centro de comando móvil.</Text>

                    <View style={styles.inputGroup}>
                        <Text style={styles.label}>CORREO INSTITUCIONAL</Text>
                        <TextInput
                            style={styles.input}
                            placeholder="agente@apollo.com"
                            value={email}
                            onChangeText={setEmail}
                            autoCapitalize="none"
                            keyboardType="email-address"
                        />
                    </View>

                    <View style={styles.inputGroup}>
                        <Text style={styles.label}>CONTRASEÑA</Text>
                        <TextInput
                            style={styles.input}
                            placeholder="••••••••"
                            value={password}
                            onChangeText={setPassword}
                            secureTextEntry
                        />
                    </View>

                    <TouchableOpacity
                        style={[styles.loginButton, loading && { opacity: 0.7 }]}
                        onPress={handleLogin}
                        disabled={loading}
                    >
                        {loading ? (
                            <ActivityIndicator color="white" />
                        ) : (
                            <>
                                <Text style={styles.loginButtonText}>ACCEDER AL NÚCLEO</Text>
                                <ArrowRight size={18} color="white" />
                            </>
                        )}
                    </TouchableOpacity>

                    {isBiometricSupported && hasSavedToken && (
                        <TouchableOpacity
                            style={styles.biometricButton}
                            onPress={handleBiometricAuth}
                            disabled={loading}
                        >
                            <Fingerprint size={24} color="#f59e0b" />
                            <Text style={styles.biometricButtonText}>INGRESAR CON HUELLA</Text>
                        </TouchableOpacity>
                    )}
                </View>

                <View style={styles.footer}>
                    <Text style={styles.footerText}>
                        <Sparkles size={14} color="#f59e0b" /> ApolloGesCom ERP Ecosystem
                    </Text>
                </View>
            </View>
        </KeyboardAvoidingView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#ffffff',
    },
    logoContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 40,
    },
    logoIcon: {
        width: 44,
        height: 44,
        borderRadius: 12,
        backgroundColor: '#f59e0b',
        alignItems: 'center',
        justifyContent: 'center',
        elevation: 8,
        shadowColor: '#f59e0b',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 10,
    },
    logoLetter: {
        color: '#ffffff',
        fontSize: 24,
        fontWeight: '900',
    },
    logoText: {
        fontSize: 28,
        fontWeight: '900',
        marginLeft: 12,
        color: '#0f172a',
        letterSpacing: -1,
    },
    formCard: {
        backgroundColor: '#f8fafc',
        borderRadius: 32,
        padding: 32,
        borderWidth: 1,
        borderColor: '#f1f5f9',
    },
    title: {
        fontSize: 22,
        fontWeight: '800',
        color: '#0f172a',
        marginBottom: 8,
    },
    subtitle: {
        fontSize: 14,
        color: '#64748b',
        marginBottom: 32,
        lineHeight: 20,
    },
    inputGroup: {
        marginBottom: 20,
    },
    label: {
        fontSize: 10,
        fontWeight: '800',
        color: '#94a3b8',
        letterSpacing: 1,
        marginBottom: 8,
        marginLeft: 4,
    },
    input: {
        backgroundColor: '#ffffff',
        borderWidth: 1,
        borderColor: '#e2e8f0',
        borderRadius: 16,
        padding: 16,
        fontSize: 15,
        color: '#1e293b',
    },
    loginButton: {
        backgroundColor: '#0f172a',
        borderRadius: 18,
        padding: 20,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: 10,
        gap: 12,
    },
    loginButtonText: {
        color: '#ffffff',
        fontSize: 14,
        fontWeight: '900',
        letterSpacing: 0.5,
    },
    biometricButton: {
        borderColor: '#f59e0b',
        borderWidth: 1.5,
        borderRadius: 18,
        padding: 18,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: 15,
        gap: 12,
        backgroundColor: '#fffdf5',
    },
    biometricButtonText: {
        color: '#d97706',
        fontSize: 14,
        fontWeight: '900',
        letterSpacing: 0.5,
    },
    footer: {
        marginTop: 40,
        alignItems: 'center',
    },
    footerText: {
        fontSize: 12,
        fontWeight: '600',
        color: '#94a3b8',
    }
});
