import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, RefreshControl } from 'react-native';
import { getTickets } from '../api';
import { Ticket, Clock, CheckCircle, ChevronRight } from 'lucide-react-native';

export default function TicketsScreen() {
    const [tickets, setTickets] = useState<any[]>([]);
    const [refreshing, setRefreshing] = useState(false);

    const loadData = async () => {
        const data = await getTickets();
        setTickets(data);
    };

    const onRefresh = async () => {
        setRefreshing(true);
        await loadData();
        setRefreshing(false);
    };

    useEffect(() => {
        loadData();
    }, []);

    const getStatusStyle = (status: string) => {
        switch (status.toLowerCase()) {
            case 'resuelto': return { color: '#10b981', bg: '#f0fdf4' };
            case 'en_curso': return { color: '#f59e0b', bg: '#fffbeb' };
            case 'escalado_a_dev': return { color: '#8b5cf6', bg: '#f5f3ff' };
            default: return { color: '#3b82f6', bg: '#eff6ff' };
        }
    };

    return (
        <View style={styles.container}>
            <View style={styles.header}>
                <Text style={styles.headerSub}>SOPORTE TÉCNICO</Text>
                <Text style={styles.headerTitle}>Incidentes Activos</Text>
            </View>

            <ScrollView
                contentContainerStyle={styles.scrollContent}
                refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
            >
                {tickets.length === 0 ? (
                    <View style={styles.emptyState}>
                        <CheckCircle size={64} color="#e2e8f0" />
                        <Text style={styles.emptyText}>Bandeja vacía. No hay requerimientos pendientes.</Text>
                    </View>
                ) : (
                    tickets.map((t: any) => {
                        const style = getStatusStyle(t.estado);
                        return (
                            <TouchableOpacity key={t.id} style={styles.ticketCard}>
                                <View style={styles.ticketHeader}>
                                    <View style={[styles.statusBadge, { backgroundColor: style.bg }]}>
                                        <Text style={[styles.statusText, { color: style.color }]}>{t.estado.toUpperCase()}</Text>
                                    </View>
                                    <Text style={styles.priorityText}>PRIORIDAD {t.prioridad.toUpperCase()}</Text>
                                </View>

                                <Text style={styles.asunto}>{t.asunto}</Text>
                                <Text style={styles.descripcion} numberOfLines={2}>{t.descripcion}</Text>

                                <View style={styles.ticketFooter}>
                                    <View style={styles.footerInfo}>
                                        <Clock size={12} color="#94a3b8" />
                                        <Text style={styles.footerText}>ID #{t.id}</Text>
                                    </View>
                                    <ChevronRight size={16} color="#cbd5e1" />
                                </View>
                            </TouchableOpacity>
                        );
                    })
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
        color: '#3b82f6',
        letterSpacing: 2,
    },
    headerTitle: {
        fontSize: 28,
        fontWeight: '900',
        color: '#0f172a',
    },
    scrollContent: {
        paddingHorizontal: 24,
        paddingBottom: 40,
    },
    ticketCard: {
        backgroundColor: '#ffffff',
        borderRadius: 24,
        padding: 20,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: '#f1f5f9',
        elevation: 2,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.05,
        shadowRadius: 8,
    },
    ticketHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16,
    },
    statusBadge: {
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: 8,
    },
    statusText: {
        fontSize: 10,
        fontWeight: '900',
    },
    priorityText: {
        fontSize: 9,
        fontWeight: '800',
        color: '#94a3b8',
        letterSpacing: 0.5,
    },
    asunto: {
        fontSize: 17,
        fontWeight: '800',
        color: '#1e293b',
        marginBottom: 4,
    },
    descripcion: {
        fontSize: 13,
        color: '#64748b',
        lineHeight: 18,
        marginBottom: 20,
    },
    ticketFooter: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingTop: 16,
        borderTopWidth: 1,
        borderTopColor: '#f1f5f9',
    },
    footerInfo: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
    },
    footerText: {
        fontSize: 11,
        color: '#94a3b8',
        fontWeight: '700',
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
