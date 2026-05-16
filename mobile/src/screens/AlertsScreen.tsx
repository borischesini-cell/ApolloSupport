import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, RefreshControl } from 'react-native';
import { getAlerts } from '../api';
import { AlertCircle, AlertTriangle, ShieldCheck } from 'lucide-react-native';

export default function AlertsScreen() {
    const [alerts, setAlerts] = useState<any>({});
    const [refreshing, setRefreshing] = useState(false);

    const loadData = async () => {
        const data = await getAlerts();
        setAlerts(data);
    };

    const onRefresh = async () => {
        setRefreshing(true);
        await loadData();
        setRefreshing(false);
    };

    useEffect(() => {
        loadData();
    }, []);

    const allAlerts = Object.entries(alerts).flatMap(([id, list]: any) =>
        list.map((msg: string) => ({ id, msg }))
    );

    return (
        <View style={styles.container}>
            <View style={styles.header}>
                <Text style={styles.headerSub}>SISTEMA PROACTIVO</Text>
                <Text style={styles.headerTitle}>Alertas Críticas</Text>
            </View>

            <ScrollView
                contentContainerStyle={styles.scrollContent}
                refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
            >
                {allAlerts.length === 0 ? (
                    <View style={styles.emptyState}>
                        <ShieldCheck size={64} color="#10b981" />
                        <Text style={styles.emptyText}>Todo bajo control. No se detectan anomalías en la flota.</Text>
                    </View>
                ) : (
                    allAlerts.map((alert: any, idx) => (
                        <View key={idx} style={styles.alertCard}>
                            <AlertCircle size={24} color="#ef4444" />
                            <View style={{ flex: 1, marginLeft: 16 }}>
                                <Text style={styles.alertTitle}>PC #{alert.id}</Text>
                                <Text style={styles.alertMsg}>{alert.msg}</Text>
                            </View>
                            <AlertTriangle size={18} color="#f59e0b" />
                        </View>
                    ))
                )}
            </ScrollView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#ffffff',
    },
    header: {
        paddingTop: 60,
        paddingHorizontal: 24,
        paddingBottom: 24,
    },
    headerSub: {
        fontSize: 10,
        fontWeight: '900',
        color: '#ef4444',
        letterSpacing: 2,
    },
    headerTitle: {
        fontSize: 28,
        fontWeight: '900',
        color: '#0f172a',
    },
    scrollContent: {
        paddingHorizontal: 24,
    },
    alertCard: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 24,
        backgroundColor: '#fef2f2',
        borderRadius: 24,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: '#fee2e2',
    },
    alertTitle: {
        fontSize: 12,
        fontWeight: '900',
        color: '#991b1b',
        textTransform: 'uppercase',
    },
    alertMsg: {
        fontSize: 16,
        fontWeight: '700',
        color: '#b91c1c',
        marginTop: 4,
    },
    emptyState: {
        alignItems: 'center',
        paddingVertical: 100,
    },
    emptyText: {
        marginTop: 20,
        fontSize: 14,
        color: '#64748b',
        textAlign: 'center',
        fontWeight: '600',
    }
});
