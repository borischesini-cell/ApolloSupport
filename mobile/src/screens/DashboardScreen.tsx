import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, RefreshControl, TouchableOpacity, ActivityIndicator } from 'react-native';
import { getActiveCentinelas } from '../api';
import { Monitor, Cpu, HardDrive, ShieldCheck, ArrowRight, Bell } from 'lucide-react-native';

export default function DashboardScreen({ navigation }: any) {
    const [centinelas, setCentinelas] = useState<any>({});
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const loadData = async () => {
        const data = await getActiveCentinelas();
        setCentinelas(data);
        setLoading(false);
    };

    const onRefresh = async () => {
        setRefreshing(true);
        await loadData();
        setRefreshing(false);
    };

    useEffect(() => {
        loadData();
        const interval = setInterval(loadData, 5000); // Actualizar cada 5s
        return () => clearInterval(interval);
    }, []);

    return (
        <View style={styles.container}>
            <View style={styles.header}>
                <View>
                    <Text style={styles.headerSub}>CENTRO DE COMANDO</Text>
                    <Text style={styles.headerTitle}>Terminal de Vuelo</Text>
                </View>
                <TouchableOpacity style={styles.notificationButton} onPress={() => navigation.navigate('Alertas')}>
                    <Bell size={20} color="#0f172a" />
                    <View style={styles.badge} />
                </TouchableOpacity>
            </View>

            <ScrollView
                contentContainerStyle={styles.scrollContent}
                refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={['#f59e0b']} />}
            >
                <View style={styles.statsOverview}>
                    <View style={styles.statBox}>
                        <Text style={styles.statVal}>{Object.keys(centinelas).length}</Text>
                        <Text style={styles.statLab}>PCS ONLINE</Text>
                    </View>
                    <View style={[styles.statBox, { borderColor: '#10b981' }]}>
                        <Text style={[styles.statVal, { color: '#10b981' }]}>100%</Text>
                        <Text style={styles.statLab}>UPTIME</Text>
                    </View>
                </View>

                <Text style={styles.sectionTitle}>Servidores en Tiempo Real</Text>

                {loading ? (
                    <ActivityIndicator color="#f59e0b" style={{ marginTop: 40 }} />
                ) : Object.keys(centinelas).length === 0 ? (
                    <View style={styles.emptyState}>
                        <ShieldCheck size={48} color="#e2e8f0" />
                        <Text style={styles.emptyText}>No hay agentes Centinela activos ahora.</Text>
                    </View>
                ) : (
                    Object.entries(centinelas).map(([id, data]: any) => (
                        <TouchableOpacity key={id} style={styles.card}>
                            <View style={styles.cardHeader}>
                                <View style={styles.pcIcon}>
                                    <Monitor size={20} color="#f59e0b" />
                                </View>
                                <View style={{ flex: 1, marginLeft: 12 }}>
                                    <Text style={styles.pcName}>{data.hostname || 'Windows PC'}</Text>
                                    <Text style={styles.pcId}>ID: #{id} • {data.os}</Text>
                                </View>
                                <View style={styles.onlineBadge}>
                                    <View style={styles.onlineDot} />
                                    <Text style={styles.onlineText}>VIVO</Text>
                                </View>
                            </View>

                            <View style={styles.metricsContainer}>
                                <View style={styles.metricRow}>
                                    <View style={styles.metricHeader}>
                                        <Cpu size={14} color="#64748b" />
                                        <Text style={styles.metricLabel}>CARGA CPU</Text>
                                        <Text style={[styles.metricVal, data.cpu > 80 && { color: '#ef4444' }]}>{data.cpu}%</Text>
                                    </View>
                                    <View style={styles.progressBar}>
                                        <View style={[styles.progressFill, { width: `${data.cpu}%` }, data.cpu > 80 && { backgroundColor: '#ef4444' }]} />
                                    </View>
                                </View>

                                <View style={styles.metricRow}>
                                    <View style={styles.metricHeader}>
                                        <HardDrive size={14} color="#64748b" />
                                        <Text style={styles.metricLabel}>USO DE RAM</Text>
                                        <Text style={[styles.metricVal, data.ram > 85 && { color: '#ef4444' }]}>{data.ram}%</Text>
                                    </View>
                                    <View style={styles.progressBar}>
                                        <View style={[styles.progressFill, { width: `${data.ram}%`, backgroundColor: '#3b82f6' }, data.ram > 85 && { backgroundColor: '#ef4444' }]} />
                                    </View>
                                </View>
                            </View>

                            <View style={styles.cardFooter}>
                                <Text style={styles.footerInfo}>Sincronizado: Hace segundos</Text>
                                <ArrowRight size={14} color="#94a3b8" />
                            </View>
                        </TouchableOpacity>
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
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
    },
    headerSub: {
        fontSize: 10,
        fontWeight: '900',
        color: '#f59e0b',
        letterSpacing: 2,
    },
    headerTitle: {
        fontSize: 28,
        fontWeight: '900',
        color: '#0f172a',
        letterSpacing: -1,
    },
    notificationButton: {
        width: 48,
        height: 48,
        borderRadius: 16,
        backgroundColor: '#f1f5f9',
        alignItems: 'center',
        justifyContent: 'center',
    },
    badge: {
        position: 'absolute',
        top: 14,
        right: 14,
        width: 8,
        height: 8,
        borderRadius: 4,
        backgroundColor: '#ef4444',
        borderWidth: 2,
        borderColor: '#f1f5f9',
    },
    scrollContent: {
        paddingHorizontal: 24,
        paddingBottom: 40,
    },
    statsOverview: {
        flexDirection: 'row',
        gap: 12,
        marginBottom: 32,
    },
    statBox: {
        flex: 1,
        padding: 20,
        borderRadius: 24,
        backgroundColor: '#f8fafc',
        borderWidth: 1,
        borderColor: '#e2e8f0',
    },
    statVal: {
        fontSize: 24,
        fontWeight: '900',
        color: '#0f172a',
    },
    statLab: {
        fontSize: 10,
        fontWeight: '700',
        color: '#64748b',
        marginTop: 4,
    },
    sectionTitle: {
        fontSize: 18,
        fontWeight: '800',
        color: '#1e293b',
        marginBottom: 16,
    },
    card: {
        backgroundColor: '#ffffff',
        borderRadius: 28,
        padding: 24,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: '#f1f5f9',
        elevation: 4,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.05,
        shadowRadius: 12,
    },
    cardHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 24,
    },
    pcIcon: {
        width: 40,
        height: 40,
        borderRadius: 12,
        backgroundColor: '#fffbeb',
        alignItems: 'center',
        justifyContent: 'center',
    },
    pcName: {
        fontSize: 16,
        fontWeight: '800',
        color: '#0f172a',
    },
    pcId: {
        fontSize: 11,
        color: '#64748b',
        fontWeight: '600',
        marginTop: 2,
    },
    onlineBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#f0fdf4',
        paddingHorizontal: 8,
        paddingVertical: 4,
        borderRadius: 8,
    },
    onlineDot: {
        width: 6,
        height: 6,
        borderRadius: 3,
        backgroundColor: '#10b981',
        marginRight: 6,
    },
    onlineText: {
        fontSize: 10,
        fontWeight: '800',
        color: '#10b981',
    },
    metricsContainer: {
        gap: 20,
    },
    metricRow: {
        gap: 8,
    },
    metricHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
    },
    metricLabel: {
        flex: 1,
        fontSize: 10,
        fontWeight: '800',
        color: '#94a3b8',
        letterSpacing: 0.5,
    },
    metricVal: {
        fontSize: 12,
        fontWeight: '900',
        color: '#334155',
    },
    progressBar: {
        height: 6,
        backgroundColor: '#f1f5f9',
        borderRadius: 3,
        overflow: 'hidden',
    },
    progressFill: {
        height: '100%',
        backgroundColor: '#f59e0b',
        borderRadius: 3,
    },
    cardFooter: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: 24,
        paddingTop: 16,
        borderTopWidth: 1,
        borderTopColor: '#f1f5f9',
    },
    footerInfo: {
        fontSize: 11,
        color: '#94a3b8',
        fontWeight: '600',
    },
    emptyState: {
        alignItems: 'center',
        paddingVertical: 60,
    },
    emptyText: {
        marginTop: 16,
        fontSize: 14,
        color: '#94a3b8',
        textAlign: 'center',
        fontWeight: '600',
    }
});
